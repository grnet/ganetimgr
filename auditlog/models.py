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

from django.db import models
from django.contrib.auth.models import User


class AuditEntry(models.Model):
    requester = models.ForeignKey(User)
    ipaddress = models.CharField(max_length=255, null=True, blank=True)
    action = models.CharField(max_length=255)
    instance = models.CharField(max_length=255)
    cluster = models.CharField(max_length=50)
    job_id = models.IntegerField(null=True, blank=True)
    recorded = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    is_authorized = models.BooleanField(default=True)

    def __unicode__(self):
        return "%s %s %s" % (self.requester, self.action, self.instance)

    def update(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)
        self.save()
