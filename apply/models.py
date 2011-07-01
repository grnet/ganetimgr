import re
import json
import base64

from django.db import models
from django.core.urlresolvers import reverse
from ganetimgr.ganeti.models import Cluster, Network
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from ganetimgr.settings import GANETI_TAG_PREFIX, OPERATING_SYSTEMS, \
                               OPERATING_SYSTEM_CHOICES

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
    email = models.EmailField(null=True, blank=True)
    tag = models.SlugField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=255, null=True, blank=True)
    users = models.ManyToManyField(User, blank=True, null=True)

    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")
        ordering = ["title"]

    def __unicode__(self):
        return self.title


class InstanceApplication(models.Model):
    hostname = models.CharField(max_length=255)
    memory = models.IntegerField()
    disk_size = models.IntegerField()
    vcpus = models.IntegerField()
    operating_system = models.CharField(_("operating system"),
                                        max_length=255,
                                        choices=OPERATING_SYSTEM_CHOICES)
    hosts_mail_server = models.BooleanField(default=False)
    comments = models.TextField(null=True, blank=True)
    admin_comments = models.TextField(null=True, blank=True)
    admin_contact_name = models.CharField(max_length=255, null=True, blank=True)
    admin_contact_phone = models.CharField(max_length=64, null=True, blank=True)
    admin_contact_email = models.EmailField(null=True, blank=True)
    organization = models.ForeignKey(Organization, null=True, blank=True)
    network = models.ForeignKey(Network, related_name=_("network"),
                                null=True, blank=True)
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

    @property
    def cluster(self):
        return self.network.cluster

    @cluster.setter
    def cluster(self, c):
        self.network = c.get_default_network()

    def is_pending(self):
        return self.status == STATUS_PENDING

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

        nic_dict = dict(link=self.network.link,
                        mode=self.network.mode)

        if self.network.mode == "routed":
            nic_dict.update(ip="pool")

        os = OPERATING_SYSTEMS[self.operating_system]
        provider = os["provider"]
        osparams = {}

        if "osparams" in os:
            osparams.update(os["osparams"])
        if "ssh_key_param" in os:
            fqdn = "http://" + Site.objects.get_current().domain
            key_url = self.get_ssh_keys_url(fqdn)
            osparams[os["ssh_key_param"]] = key_url

        job = self.cluster.create_instance(name=self.hostname,
                                           os=provider,
                                           vcpus=self.vcpus,
                                           memory=self.memory,
                                           disks=[{"size": self.disk_size * 1000}],
                                           nics=[nic_dict],
                                           tags=tags,
                                           osparams=osparams)
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
