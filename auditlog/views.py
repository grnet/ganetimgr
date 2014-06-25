#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2014 Greek Research and Technology Network (GRNET S.A.)
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

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, render_to_response
from django.core.context_processors import request
from django.core.urlresolvers import reverse
from django.template.context import RequestContext
from ganetimgr.auditlog.models import *
import json

@login_required
def auditlog(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        return render_to_response('auditlog.html',
                              context_instance=RequestContext(request))
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@login_required
def auditlog_json(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        al = AuditEntry.objects.all()
        entries = []
        for entry in al:
            entrydict = {}
            entrydict['user'] = entry.requester.username
            entrydict['user_id'] = entry.requester.id
            entrydict['user_href'] = "%s"%(reverse("user-info",
                        kwargs={'type': 'user', 'usergroup':request.user.username}
                        ))
            entrydict['job_id'] = entry.job_id
            entrydict['instance'] = entry.instance
            entrydict['cluster'] = entry.cluster
            entrydict['action'] = entry.action
            entrydict['last_upd'] = "%s" %entry.last_updated
            entrydict['name_href'] = "%s"%(reverse("instance-detail",
                        kwargs={'cluster_slug': entry.cluster, 'instance':entry.instance}
                        ))
            entries.append(entrydict)
        jresp = {}
        jresp['aaData'] = entries
        res = jresp
        return HttpResponse(json.dumps(res), mimetype='application/json')
    else:
        return HttpResponse(json.dumps({'error':"Unauthorized access"}), mimetype='application/json')