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

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from django.template.context import RequestContext
from auditlog.models import AuditEntry
import json


@login_required
def auditlog(request):
    return render_to_response('auditlog.html',
                              context_instance=RequestContext(request))


@login_required
def auditlog_json(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        al = AuditEntry.objects.all()
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
                    'instance': entry.instance
                }
            )
        )
        entries.append(entrydict)
    jresp = {}
    jresp['aaData'] = entries
    res = jresp
    return HttpResponse(json.dumps(res), mimetype='application/json')
