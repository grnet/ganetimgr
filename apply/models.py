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

import re
import json
import base64

import django.dispatch
from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

GANETI_TAG_PREFIX = settings.GANETI_TAG_PREFIX

try:
    from ganetimgr.settings import BEANSTALK_TUBE
except ImportError:
    BEANSTALK_TUBE = None

from util import beanstalkc
from paramiko import RSAKey, DSSKey
from binascii import hexlify

#  from ganeti.fields.jsonfield import JSONField
from jsonfield import JSONField

(STATUS_PENDING,
 STATUS_APPROVED,
 STATUS_SUBMITTED,
 STATUS_PROCESSING,
 STATUS_FAILED,
 STATUS_SUCCESS,
 STATUS_REFUSED,
 STATUS_DISCARDED) = range(100, 108)

APPLICATION_CODES = (
    (STATUS_PENDING, "pending"),
    (STATUS_APPROVED, "approved"),
    (STATUS_SUBMITTED, "submitted"),
    (STATUS_PROCESSING, "processing"),
    (STATUS_FAILED, "failed"),
    (STATUS_SUCCESS, "created successfully"),
    (STATUS_REFUSED, "refused"),
    (STATUS_DISCARDED, "discarded"),            # this indicates application
                                                # has been discarded silently
                                                # by an admin
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
    users = models.ManyToManyField(User, blank=True)

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
    operating_system = models.CharField(_("operating system"), max_length=255)
    hosts_mail_server = models.BooleanField(default=False)
    comments = models.TextField(null=True, blank=True)
    admin_comments = models.TextField(null=True, blank=True)
    admin_contact_name = models.CharField(max_length=255, null=True, blank=True)
    admin_contact_phone = models.CharField(max_length=64, null=True, blank=True)
    admin_contact_email = models.EmailField(null=True, blank=True)
    organization = models.ForeignKey(Organization, null=True, blank=True)
    instance_params = JSONField(blank=True, null=True)
    applicant = models.ForeignKey(User)
    job_id = models.IntegerField(null=True, blank=True)
    status = models.IntegerField(choices=APPLICATION_CODES)
    backend_message = models.TextField(blank=True, null=True)
    cookie = models.CharField(max_length=255, editable=False,
                              default=generate_cookie)
    filed = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    reviewer = models.ForeignKey(
        User, null=True, blank=True, default=None,
        related_name='application_reviewer')

    class Meta:
        permissions = (
            ("view_applications", "Can view all applications"),
        )

    def __unicode__(self):
        return self.hostname

    @property
    def cluster(self):
        from ganeti.models import Cluster
        try:
            return Cluster.objects.get(slug=self.instance_params['cluster'])
        except:
            return None

    @cluster.setter
    def cluster(self, c):
        self.instance_params = {
            'network': c.get_default_network().link,
            'mode': c.get_default_network().mode,
            'cluster': c.slug
        }

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
        import sys
        if sys.argv[1:2] == ['test']:
            return None

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
        if 'vgs' in self.instance_params.keys():
            if self.instance_params['vgs'] != 'default':
                tags.append("%s:vg:%s" % (
                    GANETI_TAG_PREFIX,
                    self.instance_params['vgs'])
                )
        uses_gnt_network = self.cluster.use_gnt_network
        nic_dict = dict(link=self.instance_params['network'],
                        mode=self.instance_params['mode'])

        if ((self.instance_params['mode'] == 'routed') and (uses_gnt_network)):
            nic_dict = dict(network=self.instance_params['network'])

        if self.instance_params['mode'] == "routed":
            nic_dict.update(ip="pool")

        from ganeti.utils import operating_systems
        fetch_op_systems = operating_systems()
        op_systems = json.loads(fetch_op_systems).get('operating_systems')
        op_systems_dict = dict(op_systems)
        sel_os = self.operating_system
        if self.operating_system == 'noop':
            sel_os = "none"
        os = op_systems_dict.get(sel_os)
        # Os shoul have been found. There are two cases that could cause
        # Ganetimgr is not configured properly (500 ImproperlyConfigured)
        if os is None:
            raise ImproperlyConfigured(
                'OPERATING_SYSTEMS is not configured properly (key must be same as img_id)'
            )
        provider = os.get('provider')
        osparams = {}

        if "osparams" in os:
            osparams.update(os["osparams"])
        if "ssh_key_param" in os:
            fqdn = "https://" + Site.objects.get_current().domain
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
                    osparams["img_personality"].append(
                        {
                            "path": path,
                            "contents": ssh_base64,
                            "owner": owner,
                            "group": group,
                            "mode": 0600,
                        }
                    )
        for (key, val) in osparams.iteritems():
            # Encode nested JSON. See
            # <https://code.google.com/p/ganeti/issues/detail?id=835>
            if not isinstance(val, basestring):
                osparams[key] = json.dumps(val)
        disk_template = self.instance_params['disk_template']
        nodes = None
        disks = [{"size": self.disk_size * 1024}]
        if self.instance_params['node_group'] != 'default':
            if self.instance_params['disk_template'] == 'drbd':
                nodes = self.cluster.get_available_nodes(
                    self.instance_params['node_group'],
                    2
                )
            else:
                nodes = self.cluster.get_available_nodes(
                    self.instance_params['node_group'],
                    1
                )
            # We should select the two first non offline nodes
        if self.instance_params['disk_template'] in ['drbd', 'plain']:
            if self.instance_params['vgs'] != 'default':
                disks[0]['vg'] = self.instance_params['vgs']
        job = self.cluster.create_instance(
            name=self.hostname,
            os=provider,
            vcpus=self.vcpus,
            memory=self.memory,
            disks=disks,
            nics=[nic_dict],
            tags=tags,
            osparams=osparams,
            nodes=nodes,
            disk_template=disk_template,
        )
        self.status = STATUS_SUBMITTED
        self.job_id = job
        self.backend_message = None
        self.save()
        application_submitted.send(sender=self)

        b = beanstalkc.Connection()
        if BEANSTALK_TUBE:
            b.use(BEANSTALK_TUBE)
        b.put(json.dumps({
            "type": "CREATE",
            "application_id": self.id
        }))

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
