#!/usr/bin/env python

import json

from gevent import monkey
monkey.patch_all()

import logging

from gevent import sleep
from gevent.pool import Pool

from util import beanstalkc
import settings

from django.core.management import setup_environ
setup_environ(settings)

from apply.models import *
from ganeti.models import Cluster
from django.core.cache import cache
from django.contrib.sites.models import Site
from django.utils.encoding import smart_str
from django.core.mail import mail_admins, mail_managers, send_mail
from django.core import urlresolvers
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist


POLL_INTERVALS = [0.5, 1, 1, 2, 2, 2, 5]
def next_poll_interval():
    for t in POLL_INTERVALS:
        yield t

    while True:
        yield POLL_INTERVALS[-1]


def monitor_jobs():
    b = beanstalkc.Connection()
    try:
        b.watch(settings.BEANSTALK_TUBE)
        b.ignore("default")
    except AttributeError:
        # We are watching "default" anyway
        pass

    job = b.reserve()
    data = json.loads(job.body)

    assert data["type"] in DISPATCH_TABLE
    DISPATCH_TABLE[data["type"]](job)


def handle_job_lock(job):
    data = json.loads(job.body)
    lock_key = data["lock_key"]
    job_id = int(data["job_id"])
    logging.info("Handling lock key %s (job %d)" % (lock_key, job_id))

    try:
        cluster = Cluster.objects.get(slug=data["cluster"])
    except ObjectDoesNotExist:
        logging.warn("Got lock key %s for unknown cluster %s, burying" %
                     (data["lock_key"], data["cluster"]))
        job.bury()
        return

    pi = next_poll_interval()
    while True:
        logging.info("Checking lock key %s (job: %d)" % (lock_key, job_id))
        reason = cache.get(lock_key)
        if reason is None:
            logging.info("Lock key %s vanished, forgetting it" % lock_key)
            job.delete()
            return

        try:
            status = cluster.get_job_status(job_id)
        except:
            sleep(pi.next())
            continue

        if status["end_ts"]:
            logging.info("Job %d finished, removing lock %s" %
                         (job_id, lock_key))
            if "flush_keys" in data:
                for key in data["flush_keys"]:
                    cache.delete(key)

            cache.delete(lock_key)
            job.delete()
            return
        # Touch the key
        cache.set(lock_key, reason, 30)
        sleep(pi.next())


def handle_creation(job):
    data = json.loads(job.body)

    try:
        application = InstanceApplication.objects.get(id=data["application_id"])
    except ObjectDoesNotExist:
        logging.warn("Unable to find application #%d, burying" %
                     data["application_id"])
        mail_admins("Burying job #%d" % job.jid,
                    "Please inspect job #%d (application %d) manually" %
                    (job.jid, data["application_id"]))
        job.bury()
        return

    logging.info("Handling %s (job: %d)",
                 application.hostname, application.job_id)
    while True:
        sleep(15)
        logging.info("Checking %s (job: %d)",
                     application.hostname, application.job_id)
        status = application.cluster.get_job_status(application.job_id)
        if status["end_ts"]:
            logging.info("%s (job: %d) done. Status: %s", application.hostname,
                         application.job_id, status["status"])
            if status["status"] == "error":
                application.status = STATUS_FAILED
                application.backend_message = smart_str(status["opresult"])
                logging.warn("%s (job: %d) failed. Notifying admins",
                             application.hostname, application.job_id)
                mail_admins("Instance creation failure for %s on %s" %
                             (application.hostname, application.cluster),
                             json.dumps(status, indent=2))
            else:
                application.status = STATUS_SUCCESS
                application.backend_message = None
                logging.info("Mailing %s about %s",
                             application.applicant.email, application.hostname)

                fqdn = Site.objects.get_current().domain
                instance_url = "https://%s%s" % \
                               (fqdn, urlresolvers.reverse("instance-detail",
                                                args=(application.cluster.slug,
                                                      application.hostname)))
                mail_body = render_to_string("instance_created_mail.txt",
                                             {"application": application,
                                              "instance_url": instance_url})
                send_mail(settings.EMAIL_SUBJECT_PREFIX +
                          "Instance %s is ready" % application.hostname,
                          mail_body, settings.SERVER_EMAIL,
                          [application.applicant.email])
                logging.info("Mailing managers about %s" %
                             application.hostname)
                mail_managers("Instance %s is ready" % application.hostname,
                              mail_body)
            application.save()
            job.delete()
            break
        job.touch()


DISPATCH_TABLE = {
    "CREATE": handle_creation,
    "JOB_LOCK": handle_job_lock,
}


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=logging.INFO)
    logging.info("Starting up")
    p = Pool(10)
    while True:
        p.spawn(monitor_jobs)
