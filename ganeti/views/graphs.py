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
import urllib2

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

from ganeti.decorators import check_instance_auth
from ganeti.forms import GraphForm
from ganeti.models import *
from ganeti.utils import get_nodes_with_graphs


@login_required
@check_instance_auth
def graph(
    request,
    cluster_slug,
    instance,
    graph_type,
    start=None,
    end=None,
    nic=None
):
    if not start:
        start = "-1d"
    start = str(start)
    if not end:
        end = "-20s"
    end = str(end)
    try:
        url = "%s/%s/%s.png/%s,%s" % (
            settings.COLLECTD_URL,
            instance,
            graph_type,
            start,
            end
        )
        if nic and graph_type == "net-ts":
            url = "%s/%s" % (url, nic)
        req = urllib2.Request(url)
        response = urllib2.urlopen(req)
    except urllib2.HTTPError:
        response = open(settings.NODATA_IMAGE, "r")
    except urllib2.URLError:
        response = open(settings.NODATA_IMAGE, "r")
    except Exception:
        response = open(settings.NODATA_IMAGE, "r")
    return HttpResponse(response.read(), content_type="image/png")


@login_required
def cluster_nodes_graphs(request, cluster_slug=None):
    nodes_string = request.GET.get('nodes', None)
    if nodes_string:
        nodes = nodes_string.split(',')
    else:
        nodes = None
    form = GraphForm(request.POST or None)
    if (
        request.user.is_superuser
        or
        request.user.has_perm('ganeti.view_instances')
    ):
        if form.is_valid():
            cluster = form.cleaned_data['cluster']
            nodes_from_form = form.cleaned_data['nodes']
            keyword_args = False
            if cluster:
                keyword_args = {'cluster_slug': cluster.slug}
            if nodes_from_form:
                get_data = '?nodes=%s' % (nodes_from_form)
            else:
                get_data = ''
            if keyword_args:
                return HttpResponseRedirect(
                    '%s%s' % (
                        reverse(
                            'cluster-get-nodes-graphs',
                            kwargs=keyword_args
                        ), get_data
                    )
                )
            else:
                return HttpResponseRedirect(
                    reverse('cluster-get-nodes-graphs')
                )

        elif cluster_slug:
            cluster = get_object_or_404(Cluster, slug=cluster_slug)
            initial_data = {}
            if cluster:
                initial_data.update({'cluster': cluster})
            if nodes:
                initial_data.update({'nodes': nodes_string})
            form.initial = initial_data
            res = get_nodes_with_graphs(
                cluster_slug=cluster_slug, nodes=nodes
            )
            return render(
                request,
                'graphs/nodes-graphs.html',
                {
                    'form': form,
                    'results': res
                }
            )
        else:
            return render(
                request,
                'graphs/nodes-graphs.html',
                {'form': form}
            )
    else:
        raise PermissionDenied
