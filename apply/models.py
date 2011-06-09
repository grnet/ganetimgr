import re
import json
import base64

from django.db import models
from django.core.urlresolvers import reverse
from ganetimgr.ganeti.models import Cluster
from django.contrib.auth.models import User
from ganetimgr.settings import GANETI_TAG_PREFIX, OPERATING_SYSTEMS

from util import beanstalkc
from paramiko import RSAKey, DSSKey
from paramiko.util import hexlify


(STATUS_PENDING,
 STATUS_APPROVED,
 STATUS_SUBMITTED,
 STATUS_PROCESSING,
 STATUS_FAILED,
 STATUS_SUCCESS,
 STATUS_REFUSED) = range(100, 107)

APPLICATION_CODES = (
    (STATUS_PENDING, "pending"),
    (STATUS_APPROVED, "approved"),
    (STATUS_SUBMITTED, "submitted"),
    (STATUS_PROCESSING, "processing"),
    (STATUS_FAILED, "failed"),
    (STATUS_SUCCESS, "created successfully"),
    (STATUS_REFUSED, "refused"),
)


def generate_cookie():
    """Generate a randomized cookie"""
    return User.objects.make_random_password(length=10)


class ApplicationError(Exception):
    pass


class Organization(models.Model):
    title = models.CharField(max_length=255)
    website = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=255, null=True, blank=True)
    users = models.ManyToManyField(User, blank=True, null=True)

    def __unicode__(self):
        return self.title


class InstanceApplication(models.Model):
    hostname = models.CharField(max_length=255)
    memory = models.IntegerField()
    disk_size = models.IntegerField()
    vcpus = models.IntegerField()
    operating_system = models.CharField(max_length=255,
                                        choices=OPERATING_SYSTEMS)
    hosts_mail_server = models.BooleanField(default=False)
    comments = models.TextField(null=True, blank=True)
    admin_contact_name = models.CharField(max_length=255, null=True, blank=True)
    admin_contact_phone = models.CharField(max_length=64, null=True, blank=True)
    admin_contact_email = models.EmailField(null=True, blank=True)
    organization = models.ForeignKey(Organization)
    cluster = models.ForeignKey(Cluster, null=True, blank=True)
    applicant = models.ForeignKey(User)
    job_id = models.IntegerField(null=True, blank=True)
    status = models.IntegerField(choices=APPLICATION_CODES)
    backend_message = models.TextField(blank=True, null=True)
    cookie = models.CharField(max_length=255, editable=False,
                              default=generate_cookie)
    filed = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.hostname

    def approve(self):
        assert self.status < STATUS_APPROVED
        self.status = STATUS_APPROVED
        self.save()

    def submit(self):
        if self.status != STATUS_APPROVED:
            raise ApplicationError("Invalid application status %d" %
                                   self.status)

        tags = []
        tags.append("%s:user:%s" %
                    (GANETI_TAG_PREFIX, self.applicant.username))

        job = self.cluster.create_instance(name=self.hostname,
                                           os="debootstrap+default",
                                           vcpus=self.vcpus,
                                           memory=self.memory,
                                           disk_template="sharedfile",
                                           disks=[{"size": self.disk_size * 1000}],
                                           nics=[{"ip": "pool"}],
                                           tags=tags)
        self.status = STATUS_SUBMITTED
        self.job_id = job
        self.save()

        b = beanstalkc.Connection()
        b.put(json.dumps({"type": "CREATE",
               "application_id": self.id}))

    def get_ssh_keys_url(self, prefix=None):
        if prefix is None:
            prefix = ""
        return prefix.rstrip("/") + reverse("instance-ssh-keys",
                                            kwargs={"application_id": self.id,
                                                    "cookie": self.cookie})


class SshPublicKey(models.Model):
    key_type = models.CharField(max_length=12)
    key = models.TextField()
    comment = models.CharField(max_length=255, null=True, blank=True)
    owner = models.ForeignKey(User)
    fingerprint = models.CharField(max_length=255, null=True, blank=True)

    def __unicode__(self):
        return "%s: %s" % (self.fingerprint, self.owner.username)

    def compute_fingerprint(self):
        data = base64.b64decode(self.key)
        if self.key_type == "ssh-rsa":
            pkey = RSAKey(data=data)
        elif self.key_type == "ssh-dss":
            pkey = DSSKey(data=data)

        return ":".join(re.findall(r"..", hexlify(pkey.get_fingerprint())))

    def key_line(self):
        return " ".join((self.key_type, self.key, self.comment)) + "\n"
