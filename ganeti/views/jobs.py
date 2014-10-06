import json

from gevent.pool import Pool

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db import close_connection
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template.context import RequestContext

from util.client import GanetiApiError
from ganeti.models import Cluster


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
            except (GanetiApiError, Exception):
                bad_clusters.append(cluster)
            finally:
                close_connection()
        if not request.user.is_anonymous():
            clusters = Cluster.objects.all()
            if cluster_slug:
                clusters = clusters.filter(slug=cluster_slug)
            p.imap(_get_jobs, clusters)
            p.join()
        if bad_clusters:
            messages = "Some jobs may be missing because the" \
                " following clusters are unreachable: %s" \
                % (", ".join([c.description for c in bad_clusters]))
        jresp = {}
        clusters = list(set([j['cluster'] for j in jobs]))
        jresp['aaData'] = jobs
        if messages:
            jresp['messages'] = messages
        jresp['clusters'] = clusters
        res = jresp
        return HttpResponse(json.dumps(res), mimetype='application/json')
    else:
        return HttpResponse(
            json.dumps({'error': "Unauthorized access"}),
            mimetype='application/json'
        )


@login_required
def jobs(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        return render_to_response(
            'jobs.html',
            context_instance=RequestContext(request)
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))
