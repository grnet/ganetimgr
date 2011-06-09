#!/usr/bin/env python

import time
import json

from gevent import monkey
monkey.patch_all()

from util import beanstalkc
import settings

from django.core.management import setup_environ
setup_environ(settings)

from apply.models import *
from django.utils.encoding import smart_str
from django.core.mail import mail_admins, send_mail
from django.core import urlresolvers
from django.template.loader import render_to_string

b = beanstalkc.Connection()

def run():
    while True:
        job = b.reserve()
        print job.body
        data = json.loads(job.body)
        assert data["type"] == "CREATE"

        application = InstanceApplication.objects.get(id=data["application_id"])
        
        while True:
            print "Checking"
            status = application.cluster.get_job_status(application.job_id)
            if status["end_ts"]:
                print "Done! Status: %s" % status["status"]
                if status["status"] == "error":
                    application.status = STATUS_FAILED
                    application.backend_message = smart_str(status["opresult"])
                    mail_admins("Instance creation failure for %s on %s" %
                                 (application.hostname, application.cluster),
                                 json.dumps(status, indent=2))
                else:
                    application.status = STATUS_SUCCESS
                    application.backend_message = None
                    mail_admins("Instance creation success for %s on %s" %
                                 (application.hostname, application.cluster),
                                str(status))
                    instance_url = "http://apollon.noc.grnet.gr"
                    instance_url += urlresolvers.reverse("instance-detail",
                                                        args=(application.cluster.slug,
                                                              application.hostname))
                    mail_body = render_to_string("instance_created_mail.txt",
                                                 {"application": application,
                                                  "instance_url": instance_url})
                    send_mail("Instance %s is ready" % application.hostname,
                              mail_body, 'apollon@noc.grnet.gr',
                              [application.applicant.email])
                application.save()
                job.delete()
                break

            job.touch()
            time.sleep(2)

if __name__ == "__main__":
    run()
