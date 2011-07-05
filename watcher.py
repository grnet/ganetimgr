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
from django.contrib.sites.models import Site
from django.utils.encoding import smart_str
from django.core.mail import mail_admins, send_mail
from django.core import urlresolvers
from django.template.loader import render_to_string


def monitor_jobs():
    b = beanstalkc.Connection()
    job = b.reserve()
    data = json.loads(job.body)
    assert data["type"] == "CREATE"

    application = InstanceApplication.objects.get(id=data["application_id"])

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
                mail_managers("Instance %s is ready" % application.hostname,
                              mail_body)
            application.save()
            job.delete()
            break
        job.touch()


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=logging.INFO)
    logging.info("Starting up")
    p = Pool(10)
    while True:
        p.spawn(monitor_jobs)
