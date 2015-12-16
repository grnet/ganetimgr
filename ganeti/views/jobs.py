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

import json
import pprint

from gevent.pool import Pool

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.contrib import messages as djmessages
from django.db import close_old_connections
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import PermissionDenied

from util.client import GanetiApiError
from ganeti.models import Cluster
from ganeti.utils import format_ganeti_api_error


@login_required
def job_details(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        if request.method == 'GET':
            cluster_slug = request.GET.get('cluster', None)
            jobid = request.GET.get('jobid', None)
            if not cluster_slug or not jobid:
                raise Http404
            cluster = get_object_or_404(Cluster, slug=cluster_slug)
            try:
                job = cluster.get_job(jobid)
            except Exception as e:
                try:
                    error = tuple(x for x in e.args[0][1:-1].split(","))[1]
                except:
                    error = _('Could not connect to api')
                return HttpResponse(error.replace('"', ''))
        return render_to_response(
            'jobs/job_details.html',
            {
                'job': pprint.pformat(job)
            },
            context_instance=RequestContext(request)
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@login_required
def jobs_index_json(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        cluster_slug = request.GET.get('cluster', None)
        messages = ""
        p = Pool(20)
        jobs = []
        bad_clusters = []

        def _get_jobs(cluster):
            try:
                jobs.extend(cluster.get_job_list())
            except GanetiApiError as e:
                bad_clusters.append((cluster, format_ganeti_api_error(e)))
            except Exception as e:
                bad_clusters.append((cluster, e))
            finally:
                close_old_connections()
        if not request.user.is_anonymous():
            # get only enabled clusters
            clusters = Cluster.objects.filter(disabled=False)
            if cluster_slug:
                clusters = clusters.filter(slug=cluster_slug)
            p.map(_get_jobs, clusters)
        if bad_clusters:
            messages = "Some instances may be missing because the" \
                " following clusters are unreachable: %s" \
                % (
                    ", ".join(
                        [
                            "%s: %s" % (
                                c[0].description or c[0].hostname,
                                c[1]
                            ) for c in bad_clusters
                        ]
                    )
                )
        jresp = {}
        clusters = list(set([j['cluster'] for j in jobs]))
        jresp['aaData'] = jobs
        if messages:
            djmessages.add_message(
                request,
                djmessages.WARNING,
                messages
            )
        jresp['clusters'] = clusters
        res = jresp
        return HttpResponse(json.dumps(res), content_type='application/json')
    else:
        raise PermissionDenied()


@login_required
def jobs(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        return render_to_response(
            'jobs/jobs.html',
            context_instance=RequestContext(request)
        )
    else:
        raise PermissionDenied()
