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
from ganeti.decorators import check_instance_auth

# proxies
from graphs import *
from instances import *
from jobs import *
from clusters import *
from discovery import *


# TODO: Cleanup and separate to files

from gevent.pool import Pool
from gevent.timeout import Timeout

from time import mktime
import datetime

from ipaddr import *
from django import forms
from django.core.cache import cache
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponse, HttpResponseServerError
)
from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext
from django.template.loader import get_template
from django.core.urlresolvers import reverse
from django.conf import settings
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext as _
from django.core.mail import send_mail
from django.template.defaultfilters import filesizeformat
from django.template.loader import render_to_string

from operator import itemgetter
from auditlog.utils import auditlog_entry

from auditlog.models import *

from ganeti.models import *
from ganeti.utils import prepare_clusternodes
from ganeti.forms import *


from util.client import GanetiApiError


import pprint
try:
    import json
except ImportError:
    import simplejson as json

from ganetimgr.settings import GANETI_TAG_PREFIX

from django.contrib.messages import constants as msgs

MESSAGE_TAGS = {
    msgs.ERROR: '',
    50: 'danger',
}


def cluster_overview(request):
    clusters = Cluster.objects.all()
    return render_to_response(
        'index.html',
        {'object_list': clusters},
        context_instance=RequestContext(request)
    )


def news(request):
    return render_to_response(
        'news.html',
        context_instance=RequestContext(request)
    )


@login_required
def clear_cache(request):
    if request.user.is_superuser or request.user.has_perm(
        'ganeti.view_instances'
    ):
        username = request.user.username
        keys_pattern = [
            "user:%s:index:*" % username,
            "cluster:*",
            "pendingapplications",
            "allclusternodes",
            "bad*",
            "len*",
            "%s:ajax*" % username,
            "locked_instances",
            "*list",
        ]
        for key in keys_pattern:
            cache_keys = cache.keys(pattern=key)
            if cache_keys:
                for cache_key in cache_keys:
                    if not cache_key.endswith('lock'):
                        cache.delete(cache_key)
        result = {'result': "Success"}
    else:
        result = {'error': "Violation"}
    return HttpResponse(json.dumps(result), mimetype='application/json')


def clusterdetails_generator(slug):
    cluster_profile = {}
    cluster_profile['slug'] = slug
    cluster = Cluster.objects.get(slug=slug)
    cluster_profile['description'] = cluster.description
    cluster_profile['hostname'] = cluster.hostname
    # We want to fetch info about the cluster per se, networks,
    # nodes and nodegroups plus a really brief instances outline.
    # Nodegroups
    nodegroups = cluster.get_node_group_stack()
    nodes = cluster.get_cluster_nodes()
    # Networks
    networks = cluster.get_networks()
    # Instances later on...
    cluster_profile['clusterinfo'] = cluster.get_cluster_info()
    cluster_profile['clusterinfo']['mtime'] = str(cluster_profile['clusterinfo']['mtime'])
    cluster_profile['clusterinfo']['ctime'] = str(cluster_profile['clusterinfo']['ctime'])
    cluster_profile['nodegroups'] = nodegroups
    cluster_profile['nodes'] = nodes
    cluster_profile['networks'] = networks
    return cluster_profile


@login_required
def clusterdetails_json(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        clusterlist = cache.get("cluster:allclusterdetails")
        if clusterlist is None:
            clusterlist = []
            errors = []
            p = Pool(10)

            def _get_cluster_details(cluster):
                try:
                    clusterlist.append(clusterdetails_generator(cluster.slug))
                except (GanetiApiError, Exception):
                    errors.append(Exception)
                finally:
                    close_connection()
            p.imap(_get_cluster_details, Cluster.objects.all())
            p.join()
            cache.set("clusters:allclusterdetails", clusterlist, 180)
        return HttpResponse(json.dumps(clusterlist), mimetype='application/json')
    else:
        return HttpResponse(
            json.dumps({'error': "Unauthorized access"}),
            mimetype='application/json'
        )


@login_required
def clusterdetails(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        return render_to_response(
            'clusters.html',
            context_instance=RequestContext(request)
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@login_required
@csrf_exempt
def reinstalldestreview(request, application_hash, action_id):
    action_id = int(action_id)
    instance = None
    if action_id not in [1, 2, 3, 4]:
        return HttpResponseRedirect(reverse('user-instances'))
    # Normalize before trying anything with it.
    activation_key = application_hash.lower()
    try:
        action = InstanceAction.objects.get(
            activation_key=activation_key,
            action=action_id
        )
    except InstanceAction.DoesNotExist:
        activated = True
        return render_to_response(
            'verify_action.html',
            {
                'action': action_id,
                'activated': activated,
                'instance': instance,
                'hash': application_hash
            },
            context_instance=RequestContext(request)
        )
    instance = action.instance
    cluster = action.cluster
    action_value = action.action_value
    activated = False
    try:
        instance_object = Instance.objects.get(name=instance)
    except ObjectDoesNotExist:
        # This should occur only when user changes email
        pass
    if action.activation_key_expired():
        activated = True
    if request.method == 'POST':
        if not activated:
            instance_action = InstanceAction.objects.activate_request(
                application_hash
            )
            if not instance_action:
                return render_to_response(
                    'verify_action.html',
                    {
                        'action': action_id,
                        'activated': activated,
                        'instance': instance,
                        'hash': application_hash
                    },
                    context_instance=RequestContext(request)
                )
            if action_id in [1, 2, 3]:
                auditlog = auditlog_entry(request, "", instance, cluster.slug, save=False)
            if action_id == 1:
                auditlog.update(action="Reinstall")
                jobid = cluster.reinstall_instance(instance, instance_action)
                # in case there is no selected os
                if jobid:
                    auditlog.update(job_id=jobid)
                else:
                    return HttpResponseServerError()
            if action_id == 2:
                auditlog.update(action="Destroy")
                jobid = cluster.destroy_instance(instance)
                auditlog.update(job_id=jobid)
            if action_id == 3:
                # As rename causes cluster lock we perform some cache
                # engineering on the cluster instances,
                # nodes and the users cache
                refresh_cluster_cache(cluster, instance)
                auditlog.update(action="Rename to %s" % action_value)
                jobid = cluster.rename_instance(instance, action_value)
                auditlog.update(job_id=jobid)
            if action_id == 4:
                user = User.objects.get(username=request.user)
                user.email = action_value
                user.save()
                return HttpResponseRedirect(reverse('profile'))
            activated = True
            return HttpResponseRedirect(reverse('user-instances'))
        else:
            return render_to_response(
                'verify_action.html',
                {
                    'action': action_id,
                    'activated': activated,
                    'instance': instance,
                    'instance_object': instance_object,
                    'hash': application_hash
                },
                context_instance=RequestContext(request)
            )
    elif request.method == 'GET':
        return render_to_response(
            'verify_action.html',
            {
                'instance': instance,
                'instance_object': instance_object,
                'action': action_id,
                'action_value': action_value,
                'cluster': cluster,
                'activated': activated,
                'hash': application_hash
            },
            context_instance=RequestContext(request)
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@csrf_exempt
@login_required
def lock(request, instance):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        if instance:
            instance = Instance.objects.get(name=instance)
        instance_adminlock = instance.adminlock
        if request.method == 'POST':
            form = lockForm(request.POST)
            if form.is_valid():
                adminlock = form.cleaned_data['lock']
                if adminlock:
                    auditlog = auditlog_entry(
                        request,
                        "Lock Instance",
                        instance, instance.cluster.slug
                    )
                    jobid = instance.cluster.tag_instance(
                        instance.name,
                        ["%s:adminlock" % GANETI_TAG_PREFIX]
                    )
                    auditlog.update(job_id=jobid)
                if adminlock is False:
                    auditlog = auditlog_entry(
                        request,
                        "Unlock Instance",
                        instance,
                        instance.cluster.slug
                    )
                    jobid = instance.cluster.untag_instance(
                        instance.name,
                        ["%s:adminlock" % GANETI_TAG_PREFIX]
                    )
                    auditlog.update(job_id=jobid)
                res = {
                    'result': 'success'
                }
                return HttpResponse(json.dumps(res), mimetype='application/json')
            else:
                return render_to_response(
                    'tagging/lock.html',
                    {
                        'form': form,
                        'instance': instance
                    },
                    context_instance=RequestContext(request)
                )
        elif request.method == 'GET':
            form = lockForm(initial={'lock': instance_adminlock})
            return render_to_response(
                'tagging/lock.html',
                {
                    'form': form,
                    'instance': instance
                },
                context_instance=RequestContext(request)
            )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@csrf_exempt
@login_required
def isolate(request, instance):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        if instance:
            instance = Instance.objects.get(name=instance)
        instance_isolate = instance.isolate
        if request.method == 'POST':
            form = isolateForm(request.POST)
            if form.is_valid():
                isolate = form.cleaned_data['isolate']
                if isolate:
                    auditlog = auditlog_entry(
                        request,
                        "Isolate",
                        instance,
                        instance.cluster.slug
                    )
                    jobid = instance.cluster.tag_instance(
                        instance.name,
                        ["%s:isolate" % GANETI_TAG_PREFIX]
                    )
                    auditlog.update(job_id=jobid)
                    instance.cluster.migrate_instance(instance.name)
                if not isolate:
                    auditlog = auditlog_entry(
                        request,
                        "De-Isolate",
                        instance,
                        instance.cluster.slug
                    )
                    jobid = instance.cluster.untag_instance(
                        instance.name,
                        ["%s:isolate" % GANETI_TAG_PREFIX]
                    )
                    auditlog.update(job_id=jobid)
                    instance.cluster.migrate_instance(instance.name)
                res = {'result': 'success'}
                return HttpResponse(
                    json.dumps(res), mimetype='application/json'
                )
            else:
                return render_to_response(
                    'tagging/isolate.html',
                    {
                        'form': form,
                        'instance': instance
                    },
                    context_instance=RequestContext(request)
                )
        elif request.method == 'GET':
            form = isolateForm(initial={'isolate': instance_isolate})
            return render_to_response(
                'tagging/isolate.html',
                {
                    'form': form,
                    'instance': instance
                },
                context_instance=RequestContext(request)
            )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@csrf_exempt
@login_required
def tagInstance(request, instance):
    instance = Instance.objects.get(name=instance)
    cluster = instance.cluster
    cache_key = "cluster:%s:instance:%s:user:%s" % (
        cluster.slug, instance.name,
        request.user.username
    )
    res = cache.get(cache_key)
    if res is None:
        res = False
        if (
            request.user.is_superuser or
            request.user in instance.users or
            set.intersection(
                set(request.user.groups.all()),
                set(instance.groups)
            )
        ):
            res = True
        cache.set(cache_key, res, 60)
    if not res:
        t = get_template("403.html")
        return HttpResponseForbidden(content=t.render(RequestContext(request)))

    if request.method == 'POST':
        users = []
        for user in instance.users:
            users.append("u_%s" % user.pk)
        groups = []
        for group in instance.groups:
            groups.append("g_%s" % group.pk)
        existingugtags = users + groups
        form = tagsForm(request.POST)
        if form.is_valid():
            newtags = form.cleaned_data['tags']
            newtags = newtags.split(',')
            common = list(set(existingugtags).intersection(set(newtags)))
            deltags = list(set(existingugtags) - set(common))

            if len(deltags) > 0:
                #we have tags to delete
                oldtodelete = prepare_tags(deltags)
                instance.cluster.untag_instance(instance.name, oldtodelete)
            newtagstoapply = prepare_tags(newtags)

            if len(newtagstoapply) > 0:
                instance.cluster.tag_instance(instance.name, newtagstoapply)

            res = {'result': 'success'}
            return HttpResponse(json.dumps(res), mimetype='application/json')
        else:
            return render_to_response(
                'tagging/itags.html',
                {
                    'form': form,
                    'users': users,
                    'instance': instance
                },
                context_instance=RequestContext(request)
            )
    elif request.method == 'GET':
        form = tagsForm()
        users = []
        for user in instance.users:
            userd = {}
            userd['text'] = user.username
            userd['id'] = "u_%s" % user.pk
            userd['type'] = "user"
            users.append(userd)
        for group in instance.groups:
            groupd = {}
            groupd['text'] = group.name
            groupd['id'] = "g_%s" % group.pk
            groupd['type'] = "group"
            users.append(groupd)
        return render_to_response(
            'tagging/itags.html',
            {
                'form': form,
                'users': users,
                'instance': instance
            },
            context_instance=RequestContext(request)
        )


def prepare_tags(taglist):
    tags = []
    for i in taglist:
        #User
        if i.startswith('u'):
            tags.append(
                "%s:user:%s" % (
                    GANETI_TAG_PREFIX, User.objects.get(
                        pk=i.replace('u_', '')
                    ).username
                )
            )
        #Group
        if i.startswith('g'):
            tags.append("%s:group:%s" % (
                GANETI_TAG_PREFIX,
                Group.objects.get(pk=i.replace('g_','')).name
            ))
    return list(set(tags))




@login_required
def get_user_groups(request):
    q_params = None
    try:
        q_params = request.GET['q']
    except:
        pass
    users = User.objects.filter(is_active=True)
    groups = Group.objects.all()
    if q_params:
        users = users.filter(username__icontains=q_params)
        groups = groups.filter(name__icontains=q_params)
    ret_list = []
    for user in users:
        userd = {}
        userd['text'] = user.username
        if (
            request.user.is_superuser or
            request.user.has_perm('ganeti.view_instances')
        ):
            userd['email'] = user.email
        userd['id'] = "u_%s" % user.pk
        userd['type'] = "user"
        ret_list.append(userd)
    for group in groups:
        groupd = {}
        groupd['text'] = group.name
        groupd['id'] = "g_%s" % group.pk
        groupd['type'] = "group"
        ret_list.append(groupd)
    action = ret_list
    return HttpResponse(json.dumps(action), mimetype='application/json')


def refresh_cluster_cache(cluster, instance):
    cluster.force_cluster_cache_refresh(instance)
    for u in User.objects.all():
        cache.delete("user:%s:index:instances" % u.username)
    nodes, bc, bn = prepare_clusternodes()
    cache.set('allclusternodes', nodes, 90)
    cache.set('badclusters', bc, 90)
    cache.set('badnodes', bn, 90)
