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

from gevent.pool import Pool

from django.contrib.auth.decorators import login_required
from django.contrib.messages import constants as msgs
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.db import close_connection
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.utils.translation import ugettext_lazy as _

from util.client import GanetiApiError

from ganeti.utils import generate_json, generate_json_light
from ganeti.models import Cluster


def user_index(request):
    if request.user.is_anonymous():
        return HttpResponseRedirect(reverse('login'))
    return render_to_response(
        'user_instances_json.html',
        context_instance=RequestContext(request)
    )


@login_required
def user_index_json(request):
    messages = ""
    cluster_slug = request.GET.get('cluster', None)
    if request.user.is_anonymous():
        action = {
            'error': _(
                "Permissions' violation. This action has been logged"
                " and our admins will be notified about it"
            )
        }
        return HttpResponse(json.dumps(action), mimetype='application/json')
    p = Pool(20)
    instances = []
    bad_clusters = []
    bad_instances = []
    locked_clusters = []

    def _get_instances(cluster):
        locked = cluster.has_locked_nodes()
        if locked:
            locked_clusters.append(str(cluster))
        try:
            instances.extend(cluster.get_user_instances(request.user))
        except (GanetiApiError, Exception):
            bad_clusters.append(cluster)
        finally:
            close_connection()
    jresp = {}
    cache_key = "user:%s:index:instances" % request.user.username
    if cluster_slug:
        cache_key = "user:%s:%s:instances" % (
            request.user.username,
            cluster_slug
        )
    res = cache.get(cache_key)
    instancedetails = []
    j = Pool(80)
    user = request.user
    locked_instances = cache.get('locked_instances')

    def _get_instance_details(instance):
        try:
            if (
                locked_instances is not None and
                instance.name in locked_instances
            ):
                instance.joblock = locked_instances['%s' % instance.name]
            else:
                instance.joblock = False
            instancedetails.extend(generate_json(instance, user))
        except (GanetiApiError, Exception):
            bad_instances.append(instance)
        finally:
            close_connection()

    if res is None:
        if not request.user.is_anonymous():
            clusters = Cluster.objects.all()
            if cluster_slug:
                clusters = clusters.filter(slug=cluster_slug)
            p.imap(_get_instances, clusters)
            p.join()
        cache_timeout = 90
        if bad_clusters:
            messages = "Some instances may be missing because the" \
                " following clusters are unreachable: %s" \
                % (", ".join([c.description for c in bad_clusters]))
            cache_timeout = 30
        j.imap(_get_instance_details, instances)
        j.join()

        if locked_clusters:
            messages += 'Some clusters are under maintenance: <br>'
            messages += ', '.join(locked_clusters)
            messages += '.'
        if bad_instances:
            bad_inst_text = "Could not get details for " + \
                str(len(bad_instances)) + \
                " instances.<br> %s. Please try again later." % bad_instances
            if messages:
                messages = messages + "<br>" + bad_inst_text
            else:
                messages = bad_inst_text
            cache_timeout = 30

        jresp['aaData'] = instancedetails
        if messages:
            jresp['messages'] = messages
        cache.set(cache_key, jresp, cache_timeout)
        res = jresp

    return HttpResponse(json.dumps(res), mimetype='application/json')


@login_required
def user_sum_stats(request):
    if request.user.is_anonymous():
        action = {
            'error': _(
                "Permissions' violation. This action has been"
                " logged and our admins will be notified about it"
            )
        }
        return HttpResponse(json.dumps(action), mimetype='application/json')
    p = Pool(20)
    instances = []
    bad_clusters = []

    def _get_instances(cluster):
        try:
            instances.extend(cluster.get_user_instances(request.user))
        except (GanetiApiError, Exception):
            bad_clusters.append(cluster)
        finally:
            close_connection()
    if not request.user.is_anonymous():
        p.imap(_get_instances, Cluster.objects.all())
        p.join()

    if bad_clusters:
        msgs.add_message(
            request,
            msgs.WARNING,
            'Some instances may be missing because the'
            ' following clusters are unreachable: ' +
            ', '.join([c.description for c in bad_clusters])
        )
    jresp = {}
    cache_key = "user:%s:index:instance:light" % request.user.username
    res = cache.get(cache_key)
    instancedetails = []
    j = Pool(80)
    user = request.user

    def _get_instance_details(instance):
        try:
            instancedetails.extend(generate_json_light(instance, user))
        except (GanetiApiError, Exception):
            pass
        finally:
            close_connection()
    if res is None:
        j.imap(_get_instance_details, instances)
        j.join()
        jresp['aaData'] = instancedetails
        cache.set(cache_key, jresp, 125)
        res = jresp

    instances_stats = []
    user_dict = {}
    cache_key_stats = "user:%s:index:users:instance:stats" % \
        request.user.username
    instances_stats = cache.get(cache_key_stats)
    if instances_stats is None:
        for i in res['aaData']:
            if not 'users' in i:
                i['users'] = [{'user': request.user.username}]
            for useritem in i['users']:
                if not useritem['user'] in user_dict:
                    user_dict[useritem['user']] = {
                        'instances': 0,
                        'disk': 0,
                        'cpu': 0,
                        'memory': 0
                    }
                user_dict[useritem['user']]['instances'] = user_dict[
                    useritem['user']
                ]['instances'] + 1
                user_dict[useritem['user']]['disk'] = user_dict[
                    useritem['user']
                ]['disk'] + int(i['disk'])
                user_dict[useritem['user']]['cpu'] = user_dict[
                    useritem['user']
                ]['cpu'] + int(i['vcpus'])
                user_dict[useritem['user']]['memory'] = user_dict[
                    useritem['user']
                ]['memory'] + int(i['memory'])
        #TODO: Must implement that in a more efficient way
        instances_stats_list = []
        for u in user_dict.keys():
            user_stats_dict = {}
            user_stats_dict['user_href'] = '%s' % (
                reverse(
                    'user-info',
                    kwargs={
                        'type': 'user',
                        'usergroup': u
                    }
                )
            )
            user_stats_dict['user'] = u
            user_stats_dict['instances'] = user_dict[u]['instances']
            user_stats_dict['disk'] = user_dict[u]['disk']
            user_stats_dict['cpu'] = user_dict[u]['cpu']
            user_stats_dict['memory'] = user_dict[u]['memory']
            instances_stats_list.append(user_stats_dict)
        return_dict = {'aaData': instances_stats_list}
        cache.set(cache_key_stats, return_dict, 120)
        instances_stats = return_dict
    return HttpResponse(
        json.dumps(instances_stats),
        mimetype='application/json'
    )

