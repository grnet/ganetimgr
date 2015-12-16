# -*- coding: utf-8 -*- vim:fileencoding=utf-8: # Copyright (C) 2010-2014 GRNET S.A.
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

import json
import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.conf import settings
from auditlog.models import AuditEntry


@login_required
def auditlog(request):
    '''
    In case "AUDIT_ENTRIES_LAST_X_DAYS" is set in settings.py
    we have to pass it to the template in order to show a warning to
    superusers.
    '''
    context = {}
    if (
        hasattr(settings, 'AUDIT_ENTRIES_LAST_X_DAYS')
        and settings.AUDIT_ENTRIES_LAST_X_DAYS > 0
        and request.user.is_superuser
    ):
            context['days'] = settings.AUDIT_ENTRIES_LAST_X_DAYS
    return render(request, 'auditlog/auditlog.html', context)


@login_required
def auditlog_json(request):
    '''
    Shows all the audit entries of the current user or of all
    users in case we are the superuser. There are limits depending on the
    usage of the service and the time it has been up, so there is an extra
    setting "AUDIT_ENTRIES_LAST_X_DAYS" which limits the results (only for
    the superusers).
    '''
    # age of the log entries that will be shown. We have to store it in order
    # to show it in the template
    days = None
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        days = 0
        al = AuditEntry.objects.all()
        if hasattr(settings, 'AUDIT_ENTRIES_LAST_X_DAYS'):
            days = settings.AUDIT_ENTRIES_LAST_X_DAYS
        if days > 0:
            al = al.filter(last_updated__gte=datetime.datetime.now() - datetime.timedelta(days=days))
    else:
        al = AuditEntry.objects.filter(requester=request.user)
    entries = []
    for entry in al:
        entrydict = {}
        entrydict['user'] = entry.requester.username
        entrydict['user_id'] = entry.requester.id
        entrydict['user_href'] = "%s" % (
            reverse(
                "user-info",
                kwargs={
                    'type': 'user',
                    'usergroup': entry.requester.username
                }
            )
        )
        entrydict['job_id'] = entry.job_id
        entrydict['instance'] = entry.instance
        entrydict['cluster'] = entry.cluster
        entrydict['action'] = entry.action
        entrydict['last_upd'] = "%s" % entry.last_updated
        entrydict['name_href'] = "%s" % (
            reverse(
                "instance-detail",
                kwargs={
                    'cluster_slug': entry.cluster,
                    'instance': entry.instance,
                }
            )
        )
        entrydict['is_authorized'] = entry.is_authorized
        entries.append(entrydict)
    jresp = {}
    jresp['aaData'] = entries
    res = jresp
    return HttpResponse(json.dumps(res), content_type='application/json')
