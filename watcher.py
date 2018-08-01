#!/usr/bin/env python
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import json

from gevent import monkey
monkey.patch_all()

import atexit
import daemon
import logging
import daemon.pidfile
import setproctitle
from lockfile import LockError
from signal import SIGINT, SIGTERM

from gevent import sleep, signal
from gevent import reinit as gevent_reinit
from gevent.pool import Pool

import beanstalkc
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ganetimgr.settings")
from django.conf import settings
import django
django.setup()

from ganeti.models import Cluster
from apply.models import InstanceApplication, STATUS_FAILED, STATUS_SUCCESS
from django.core.cache import cache
from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.utils.encoding import smart_str
from django.core.mail import mail_admins, mail_managers, send_mail
from django.core import urlresolvers
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist
from django.db import close_old_connections

logger = None

POLL_INTERVALS = [0.5, 1, 1, 2, 2, 2, 5]
DEFAULT_WORKERS = 10
DEFAULT_PID_FILE = "/var/run/ganetimgr-watcher.pid"
DEFAULT_LOG_FILE = "/var/log/ganetimgr/watcher.log"
RESERVE_ERROR_THRESHOLD = 30


def next_poll_interval():
    for t in POLL_INTERVALS:
        yield t

    while True:
        yield POLL_INTERVALS[-1]


def try_log(fn, *args, **kwargs):
    global logger
    try:
        fn(*args, **kwargs)
    except StandardError as e:
        logger.error("%s: %s" % (fn.__name__, str(e)))


def monitor_jobs():
    # We have to open one socket per Greenlet, as currently socket sharing is
    # not allowed
    try:
        b = beanstalkc.Connection()
    except Exception, err:
        logger.error("Error connecting to beanstalkd: %s" % str(err))
        sleep(5)
        return

    try:
        b.watch(settings.BEANSTALK_TUBE)
        b.ignore("default")
    except AttributeError:
        # We are watching "default" anyway
        pass

    while True:
        job = b.reserve()
        stats = job.stats()

        # Check for erratic jobs and bury them
        if stats["reserves"] > RESERVE_ERROR_THRESHOLD:
            logger.error("Job %d reserved %d (> %d) times, burying" %
                         (job.jid, stats["reserves"], RESERVE_ERROR_THRESHOLD))
            job.bury()
            continue

        try:
            data = json.loads(job.body)
        except ValueError:
            logger.error("Job %d has malformed body '%s', burying" %
                         (job.jid, job.body))
            job.bury()
            continue

        if "type" in data and data["type"] in DISPATCH_TABLE:
            DISPATCH_TABLE[data["type"]](job)

def clear_cluster_users_cache(cluster_slug):
    for user in User.objects.all():
        cache.delete("user:%s:index:instances" %user.username)
    cache.delete("cluster:%s:instances" % cluster_slug)
    close_old_connections()

def handle_job_lock(job):
    global logger
    data = json.loads(job.body)
    lock_key = data["lock_key"]
    instance = data["instance"]
    job_id = int(data["job_id"])
    logger.info("Handling lock key %s (job %d)" % (lock_key, job_id))

    try:
        cluster = Cluster.objects.get(slug=data["cluster"])
    except ObjectDoesNotExist:
        logger.warn("Got lock key %s for unknown cluster %s, burying" %
                     (data["lock_key"], data["cluster"]))
        job.bury()
        close_old_connections()
        return
    finally:
        close_old_connections()

    pi = next_poll_interval()
    while True:
        logger.debug("Checking lock key %s (job: %d)" % (lock_key, job_id))
        reason = cache.get(lock_key)
        if reason is None:
            logger.info("Lock key %s vanished, forgetting it" % lock_key)
            job.delete()
            return

        logger.debug("Polling job %d" % job_id)
        try:
            status = cluster.get_job_status(job_id)
        except Exception, err:
            logger.warn("Error polling job: %s" % str(err))
            close_old_connections()
            sleep(pi.next())
            continue
        finally:
            close_old_connections()
        logger.debug("Done")

        if status["end_ts"]:
            logger.info("Job %d finished, removing lock %s" %
                         (job_id, lock_key))
            if "flush_keys" in data:
                for key in data["flush_keys"]:
                    cache.delete(key)

            cache.delete(lock_key)
            locked_instances = cache.get('locked_instances')
            # This should contain at least 1 instance
            if locked_instances is not None:
                try:
                    locked_instances.pop("%s"%instance)
                except KeyError:
                    pass
                if len(locked_instances.items()) == 0:
                    cache.delete('locked_instances')
                else:
                    cache.set('locked_instances', locked_instances, 90)
            else:
                # This could be due to a cache fail or restart. For the time log it
                logger.warn("Unable to find instance %s in locked instances cache key" %instance)
            clear_cluster_users_cache(cluster.slug)
            job.delete()
            return
        # Touch the key
        cache.set(lock_key, reason, 30)
        job.touch()
        sleep(pi.next())


def handle_creation(job):
    global logger
    data = json.loads(job.body)

    try:
        application = InstanceApplication.objects.get(id=data["application_id"])
    except ObjectDoesNotExist:
        logger.warn("Unable to find application #%d, burying" %
                     data["application_id"])
        try_log(mail_admins, "Burying job #%d" % job.jid,
                    "Please inspect job #%d (application %d) manually" %
                    (job.jid, data["application_id"]))
        job.bury()
        close_old_connections()
        return
    finally:
        close_old_connections()

    logger.info("Handling %s (job: %d)",
                 application.hostname, application.job_id)
    while True:
        sleep(15)
        logger.info("Checking %s (job: %d)",
                     application.hostname, application.job_id)
        status = application.cluster.get_job_status(application.job_id)
        if status["end_ts"]:
            logger.info("%s (job: %d) done. Status: %s", application.hostname,
                         application.job_id, status["status"])
            if status["status"] == "error":
                application.status = STATUS_FAILED
                application.backend_message = smart_str(status["opresult"])
                application.save()
                logger.warn("%s (job: %d) failed. Notifying admins",
                             application.hostname, application.job_id)
                try_log(mail_admins, "Instance creation failure for %s on %s" %
                             (application.hostname, application.cluster),
                             json.dumps(status, indent=2))
            else:
                application.status = STATUS_SUCCESS
                application.backend_message = None
                application.save()
                logger.info("Mailing %s about %s",
                             application.applicant.email, application.hostname)

                fqdn = Site.objects.get_current().domain
                instance_url = "https://%s%s" % \
                               (fqdn, urlresolvers.reverse("instance-detail",
                                                args=(application.cluster.slug,
                                                      application.hostname)))
                mail_body = render_to_string("instances/emails/instance_created_mail.txt",
                                             {"application": application,
                                              "instance_url": instance_url,
                                              "BRANDING": settings.BRANDING
                                            })
                mail_body_managers = render_to_string("instances/emails/instance_created_mail.txt",
                                             {"application": application,
                                              "reviewer": application.reviewer,
                                              "instance_url": instance_url,
                                              "BRANDING": settings.BRANDING
                                            })
                try_log(send_mail, settings.EMAIL_SUBJECT_PREFIX +
                          "Instance %s is ready" % application.hostname,
                          mail_body, settings.SERVER_EMAIL,
                          [application.applicant.email])
                logger.info("Mailing managers about %s" %
                             application.hostname)
                try_log(mail_managers, "Instance %s is ready" % application.hostname,
                              mail_body_managers)
            job.delete()
            close_old_connections()
            break
        job.touch()


DISPATCH_TABLE = {
    "CREATE": handle_creation,
    "JOB_LOCK": handle_job_lock,
}


def parse_arguments(args):
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-w", "--workers", dest="workers",
                      default=DEFAULT_WORKERS, metavar="NUM",
                      help="The number of workers monitoring jobs"
                           " simultaneously (default: %d)" % DEFAULT_WORKERS)
    parser.add_option("-d", "--debug", action="store_true", dest="debug")
    parser.add_option("-p", "--pid-file", dest="pid_file",
                      default=DEFAULT_PID_FILE, metavar="FILE",
                      help="Save PID to file (default: %s)" % DEFAULT_PID_FILE)
    parser.add_option("-l", "--log-file", dest="log_file",
                      default=DEFAULT_LOG_FILE, metavar="FILE",
                      help="Write log to FILE (default: %s)" %
                           DEFAULT_LOG_FILE)
    parser.add_option("-f", "--foreground", action="store_true",
                      dest="foreground", help="Do not daemonize")
    parser.add_option("-u", "--user", dest="user", metavar="USER",
                      help="User to run as")
    parser.add_option("-g", "--group", dest="group", metavar="GROUP",
                      help="Group to run as")
    return parser.parse_args(args)


class AllFilesDaemonContext(daemon.DaemonContext):
    """ DaemonContext class keeping all file descriptors open """
    def _get_exclude_file_descriptors(self):
        class All:
            def __contains__(self, value):
                return True
        return All()


def fatal_signal_handler(signame):
    logger.info("Caught %s, exiting" % signame)
    raise SystemExit


def main():
    opts, args = parse_arguments(sys.argv[1:])
    pidf = daemon.pidfile.TimeoutPIDLockFile(opts.pid_file, 3)

    lvl = logging.DEBUG if opts.debug else logging.INFO

    global logger
    logger = logging.getLogger("watcher")
    logger.setLevel(lvl)
    formatter = logging.Formatter("%(asctime)s %(message)s",
                                  "%m/%d/%Y %I:%M:%S %p")
    handler = logging.FileHandler(opts.log_file)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info("Starting up")

    context = None
    if not opts.foreground:
        # Currently, gevent uses libevent-dns for asynchornous DNS resolution,
        # which opens a socket upon initialization time. Since we can't get the fd
        # reliably, We have to maintain all file descriptors open (which won't harm
        # anyway)
        context = AllFilesDaemonContext(pidfile=pidf, umask=0022)
        if opts.user:
            try:
                context.uid = int(opts.user)
            except ValueError:
                import pwd
                try:
                    context.uid = pwd.getpwnam(opts.user).pw_uid
                except KeyError:
                    sys.stderr.write("User %s not found\n" % opts.user)
                    sys.exit(1)

        if opts.group:
            try:
                context.gid = int(opts.group)
            except ValueError:
                import grp
                try:
                    context.gid = grp.getgrnam(opts.group).gr_gid
                except KeyError:
                    sys.stderr.write("Group %s not found\n" % opts.group)
                    sys.exit(1)

        try:
            context.open()
        except LockError:
            sys.stderr.write("Unable to acquire PID file lock."
                             " Is another process running?\n")
            sys.exit(1)

        logger.info("Forked to background")
        # We must reinit gevent after forking
        gevent_reinit()

    else:
        try:
            pidf.__enter__()
        except LockError:
            sys.stderr.write("Unable to acquire PID file lock."
                             " Is another process running?\n")
            sys.exit(1)
        atexit.register(pidf.__exit__)

    signal(SIGINT, fatal_signal_handler, "SIGINT")
    signal(SIGTERM, fatal_signal_handler, "SIGTERM")

    # Set the process title
    setproctitle.setproctitle(sys.argv[0])

    logger.info("Initialization complete")
    p = Pool(opts.workers)
    while True:
        logger.debug("Spawning new worker")
        p.spawn(monitor_jobs)

    if opts.daemonize:
        context.close()

if __name__ == "__main__":
    main()
