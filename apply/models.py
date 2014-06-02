#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2012 Greek Research and Technology Network (GRNET S.A.)
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD
# TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
# OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF
# USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
# TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.

import re
import json
import base64

import django.dispatch
from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from ganetimgr.settings import GANETI_TAG_PREFIX, OPERATING_SYSTEMS, \
                               OPERATING_SYSTEM_CHOICES
try:
    from ganetimgr.settings import BEANSTALK_TUBE
except ImportError:
    BEANSTALK_TUBE = None

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

PENDING_CODES = [STATUS_PENDING, STATUS_APPROVED, STATUS_FAILED]

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
    network = models.ForeignKey('ganeti.Network', related_name=_("network"),
                                null=True, blank=True)
    applicant = models.ForeignKey(User)
    job_id = models.IntegerField(null=True, blank=True)
    status = models.IntegerField(choices=APPLICATION_CODES)
    backend_message = models.TextField(blank=True, null=True)
    cookie = models.CharField(max_length=255, editable=False,
                              default=generate_cookie)
    filed = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        permissions = (
            ("view_applications", "Can view all applications"),
        )


    def __unicode__(self):
        return self.hostname

    @property
    def cluster(self):
        return self.network.cluster

    @cluster.setter
    def cluster(self, c):
        self.network = c.get_default_network()

    def is_pending(self):
        return self.status in PENDING_CODES

    def approve(self):
        assert self.status < STATUS_APPROVED
        self.status = STATUS_APPROVED
        self.save()

    def submit(self):
        if self.status not in [STATUS_APPROVED, STATUS_FAILED]:
            raise ApplicationError("Invalid application status %d" %
                                   self.status)

        def map_ssh_user(user, group=None, path=None):
            if group is None:
                if user == "root":
                    group = ""   # snf-image will expand to root or wheel
                else:
                    group = user
            if path is None:
                if user == "root":
                    path = "/root/.ssh/authorized_keys"
                else:
                    path = "/home/%s/.ssh/authorized_keys" % user
            return user, group, path

        tags = []
        tags.append("%s:user:%s" %
                    (GANETI_TAG_PREFIX, self.applicant.username))

        tags.append("%s:application:%d" % (GANETI_TAG_PREFIX, self.id))

        if self.hosts_mail_server:
            tags.append("%s:service:mail" % GANETI_TAG_PREFIX)

        if self.organization:
            tags.append("%s:org:%s" % (GANETI_TAG_PREFIX,
                                       self.organization.tag))
        uses_gnt_network = self.network.cluster.use_gnt_network
        
        nic_dict = dict(link=self.network.link,
                        mode=self.network.mode)
        
        if ((self.network.mode == 'routed') and (uses_gnt_network)):
            nic_dict = dict(network=self.network.link)

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
            if os["ssh_key_param"]:
                osparams[os["ssh_key_param"]] = key_url
        # For snf-image: copy keys to ssh_key_users using img_personality
        if "ssh_key_users" in os and os["ssh_key_users"]:
            ssh_keys = self.applicant.sshpublickey_set.all()
            if ssh_keys:
                ssh_lines = [key.key_line() for key in ssh_keys]
                ssh_base64 = base64.b64encode("".join(ssh_lines))
                if "img_personality" not in osparams:
                    osparams["img_personality"] = []
                for user in os["ssh_key_users"].split():
                    # user[:group[:/path/to/authorized_keys]]
                    owner, group, path = map_ssh_user(*user.split(":"))
                    osparams["img_personality"].append({
                        "path":     path,
                        "contents": ssh_base64,
                        "owner":    owner,
                        "group":    group,
                        "mode":     0600,
                    })
        for (key, val) in osparams.iteritems():
            # Encode nested JSON. See
            # <https://code.google.com/p/ganeti/issues/detail?id=835>
            if not isinstance(val, str):
                osparams[key] = json.dumps(val)
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
        self.backend_message = None
        self.save()
        application_submitted.send(sender=self)

        b = beanstalkc.Connection()
        if BEANSTALK_TUBE:
            b.use(BEANSTALK_TUBE)
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

    class Meta:
        ordering = ["fingerprint"]

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
        line = " ".join((self.key_type, self.key))
        if self.comment is not None:
            line = " ".join((line, self.comment))
        return line + "\n"


application_submitted = django.dispatch.Signal()
