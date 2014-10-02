# -*- coding: utf-8 -*-

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
import django.dispatch
from django.contrib.auth.models import User
from auditlog.models import AuditEntry
audit_entry = django.dispatch.Signal()


def store_audit_entry(sender, *args, **kwargs):
    if 'user' in kwargs.keys():
        user = kwargs['user']
    if 'ipaddress' in kwargs.keys():
        ipaddress = kwargs['ipaddress']
    if 'action' in kwargs.keys():
        action = kwargs['action']
    if 'instance' in kwargs.keys():
        instance = kwargs['instance']
    if 'cluster' in kwargs.keys():
        cluster = kwargs['cluster']
    auditlog = AuditEntry(
        requester=User.objects.get(pk=user),
        ipaddress=ipaddress,
        action=action,
        instance=instance,
        cluster=cluster
    )
    auditlog.save

audit_entry.connect(store_audit_entry)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
