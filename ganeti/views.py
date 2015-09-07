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
import re
import socket

from gevent.pool import Pool
from gevent.timeout import Timeout

from time import mktime


from ipaddr import *
from django import forms
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
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

from auditlog.models import *

from ganeti.models import *
from ganeti.utils import prepare_clusternodes, get_nodes_with_graphs
from ganeti.forms import *

import datetime

from apply.utils import get_os_details
from util.client import GanetiApiError


import pprint
try:
    import json
except ImportError:
    import simplejson as json

from ganetimgr.settings import GANETI_TAG_PREFIX

from django.contrib.messages import constants as msgs
from django.contrib import messages
from django.db import close_connection

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
def user_info(request, type, usergroup):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        if type == 'user':
            usergroup_info = User.objects.get(username=usergroup)
        if type == 'group':
            usergroup_info = Group.objects.get(name=usergroup)
        return render_to_response(
            'user_info.html',
            {'usergroup': usergroup_info, 'type': type},
            context_instance=RequestContext(request)
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


def check_admin_lock(view_fn):
    def check_lock(request, *args, **kwargs):
        try:
            instance_name = kwargs["instance"]
        except KeyError:
            instance_name = args[0]
        instance = Instance.objects.get(name=instance_name)
        res = instance.adminlock
        if request.user.is_superuser:
                res = False
        if not res:
            return view_fn(request, *args, **kwargs)
        else:
            t = get_template("403.html")
            return HttpResponseForbidden(content=t.render(RequestContext(request)))
    return check_lock


def check_instance_auth(view_fn):
    def check_auth(request, *args, **kwargs):
        try:
            cluster_slug = kwargs["cluster_slug"]
            instance_name = kwargs["instance"]
        except KeyError:
            cluster_slug = args[0]
            instance_name = args[1]

        cache_key = "cluster:%s:instance:%s:user:%s" % (
            cluster_slug,
            instance_name,
            request.user.username
        )
        res = cache.get(cache_key)
        if res is None:
            cluster = get_object_or_404(Cluster, slug=cluster_slug)
            instance = cluster.get_instance_or_404(instance_name)
            res = False

            if (
                request.user.is_superuser or
                request.user in instance.users or
                set.intersection(
                    set(request.user.groups.all()), set(instance.groups)
                )
            ):
                res = True

            cache.set(cache_key, res, 60)

        if not res:
            t = get_template("403.html")
            return HttpResponseForbidden(content=t.render(RequestContext(request)))
        else:
            return view_fn(request, *args, **kwargs)
    return check_auth


def check_instance_readonly(view_fn):
    def check_auth(request, *args, **kwargs):
        try:
            cluster_slug = kwargs["cluster_slug"]
            instance_name = kwargs["instance"]
        except KeyError:
            cluster_slug = args[0]
            instance_name = args[1]

        cache_key = "cluster:%s:instance:%s:user:%s" % (cluster_slug, instance_name,
                                                        request.user.username)
        res = cache.get(cache_key)
        if res is None:
            cluster = get_object_or_404(Cluster, slug=cluster_slug)
            instance = cluster.get_instance_or_404(instance_name)
            res = False

            if (
                request.user.is_superuser or
                request.user in instance.users or
                request.user.has_perm('ganeti.view_instances') or
                set.intersection(
                    set(request.user.groups.all()), set(instance.groups)
                )
            ):
                res = True

            cache.set(cache_key, res, 60)

        if not res:
            t = get_template("403.html")
            return HttpResponseForbidden(
                content=t.render(RequestContext(request))
            )
        else:
            return view_fn(request, *args, **kwargs)
    return check_auth


def user_index(request):
    if request.user.is_anonymous():
        return HttpResponseRedirect(reverse('login'))
    return render_to_response(
        'user_instances_json.html',
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


@login_required
def job_details(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        if request.method == 'GET':
            if 'cluster' in request.GET:
                cluster_slug = request.GET.get('cluster')
            if 'jobid' in request.GET:
                jobid = request.GET.get('jobid')
            cluster = get_object_or_404(Cluster, slug=cluster_slug)
            job = cluster.get_job(jobid)
        return render_to_response(
            'job_details.html',
            {"job": pprint.pformat(job)},
            context_instance=RequestContext(request)
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


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
    locked_nodes = []

    def _get_instances(cluster):
        cluster_locked_nodes = cluster.locked_nodes_from_nodegroup()
        if cluster_locked_nodes:
            locked_nodes.extend(cluster_locked_node_groups)
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
            instancedetails.extend(generate_json(instance, user, locked_nodes))
        except (GanetiApiError, Exception) as e:
            raise Exception(e)
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
        messages.add_message(request, messages.WARNING,
                             "Some instances may be missing because the"
                             " following clusters are unreachable: " +
                             ", ".join([c.description for c in bad_clusters]))
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
            user_stats_dict['user_href'] = "%s"%(reverse("user-info",
                        kwargs={'type': 'user', 'usergroup':u}
                        ))
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


def generate_json(instance, user, locked_nodes=[]):
    jresp_list = []
    i = instance
    inst_dict = {}
    if not i.admin_view_only:
        inst_dict['name_href'] = "%s" % (
            reverse(
                'instance-detail',
                kwargs={
                    'cluster_slug': i.cluster.slug, 'instance': i.name
                }
            )
        )
    inst_dict['name'] = i.name
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['cluster'] = i.cluster.slug
        inst_dict['pnode'] = i.pnode
    else:
        inst_dict['cluster'] = i.cluster.description
        inst_dict['clusterslug'] = i.cluster.slug
    inst_dict['node_group_locked'] = i.pnode in locked_nodes
    inst_dict['memory'] = memsize(i.beparams['maxmem'])
    inst_dict['disk'] = ", ".join(disksizes(i.disk_sizes))
    inst_dict['vcpus'] = i.beparams['vcpus']
    inst_dict['ipaddress'] = [ip for ip in i.nic_ips if ip]
    if not user.is_superuser and not user.has_perm('ganeti.view_instances'):
        inst_dict['ipv6address'] = [ip for ip in i.ipv6s if ip]
    #inst_dict['status'] = i.nic_ips[0] if i.nic_ips[0] else "-"
    if i.admin_state == i.oper_state:
        if i.admin_state:
            inst_dict['status'] = "Running"
            inst_dict['status_style'] = "success"
        else:
            inst_dict['status'] = "Stopped"
            inst_dict['status_style'] = "important"
    else:
        if i.oper_state:
            inst_dict['status'] = "Running"
        else:
            inst_dict['status'] = "Stopped"
        if i.admin_state:
            inst_dict['status'] = "%s, should be running" % inst_dict['status']
        else:
            inst_dict['status'] = "%s, should be stopped" % inst_dict['status']
        inst_dict['status_style'] = "warning"
    if i.status == 'ERROR_nodedown':
        inst_dict['status'] = "Generic cluster error"
        inst_dict['status_style'] = "important"

    if i.adminlock:
        inst_dict['adminlock'] = True

    if i.isolate:
        inst_dict['isolate'] = True

    if i.needsreboot:
        inst_dict['needsreboot'] = True

    # When renaming disable clicking on instance for everyone
    if hasattr(i, 'admin_lock'):
        if i.admin_lock:
            try:
                del inst_dict['name_href']
            except KeyError:
                pass

    if i.joblock:
        inst_dict['locked'] = True
        inst_dict['locked_reason'] = "%s" % ((i.joblock).capitalize())
        if inst_dict['locked_reason'] in ['Deleting', 'Renaming']:
            try:
                del inst_dict['name_href']
            except KeyError:
                pass
    if 'cdrom_image_path' in i.hvparams.keys():
        if i.hvparams['cdrom_image_path'] and i.hvparams['boot_order'] == 'cdrom':
            inst_dict['cdrom'] = True
    inst_dict['nic_macs'] = ', '.join(i.nic_macs)
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['nic_links'] = ', '.join(i.nic_links)
        inst_dict['network'] = []
        for (nic_i, link) in enumerate(i.nic_links):
            if i.nic_ips[nic_i] is None:
                inst_dict['network'].append("%s" % (i.nic_links[nic_i]))
            else:
                inst_dict['network'].append(
                    "%s@%s" % (i.nic_ips[nic_i], i.nic_links[nic_i])
                )
        inst_dict['users'] = [
            {
                'user': user_item.username,
                'email': user_item.email,
                'user_href': "%s" % (
                    reverse(
                        "user-info",
                        kwargs={
                            'type': 'user',
                            'usergroup': user_item.username
                        }
                    )
                )
            } for user_item in i.users]
        inst_dict['groups'] = [
            {
                'group': group.name,
                'groupusers': [
                    "%s,%s" % (u.username, u.email) for u in group.userset
                ],
                'group_href':"%s" % (
                    reverse(
                        "user-info",
                        kwargs={
                            'type': 'group',
                            'usergroup': group.name
                        }
                    )
                )
            } for group in i.groups
        ]
    jresp_list.append(inst_dict)
    return jresp_list


def generate_json_light(instance, user):

    jresp_list = []
    i = instance
    inst_dict = {}
    if not i.admin_view_only:
        inst_dict['name_href'] = "%s" % (
            reverse(
                "instance-detail",
                kwargs={
                    'cluster_slug': i.cluster.slug,
                    'instance': i.name
                }
            )
        )
    inst_dict['name'] = i.name
    inst_dict['clusterslug'] = i.cluster.slug
    inst_dict['memory'] = i.beparams['maxmem']
    inst_dict['vcpus'] = i.beparams['vcpus']
    inst_dict['disk'] = sum(i.disk_sizes)
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['users'] = [
            {
                'user': user_item.username
            } for user_item in i.users
        ]
    jresp_list.append(inst_dict)
    return jresp_list


@login_required
@check_instance_auth
def vnc(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    port, password = cluster.setup_vnc_forwarding(instance)

    return render_to_response(
        "vnc.html",
        {
            'cluster': cluster,
            'instance': instance,
            'host': request.META['HTTP_HOST'],
            'port': port,
            'password': password
        },
        context_instance=RequestContext(request)
    )


@login_required
@check_instance_auth
def novnc(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    use_tls = settings.NOVNC_USE_TLS
    return render_to_response(
        "novnc.html",
        {
            'cluster': cluster,
            'instance': instance,
            'use_tls': use_tls,
        },
        context_instance=RequestContext(request)
    )


@login_required
@check_instance_auth
def novnc_proxy(request, cluster_slug, instance):
    use_tls = False
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    use_tls = settings.NOVNC_USE_TLS
    result = json.dumps(cluster.setup_novnc_forwarding(instance, tls=use_tls))
    return HttpResponse(result, mimetype="application/json")


@login_required
@csrf_exempt
@check_instance_auth
@check_admin_lock
def shutdown(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    auditlog = auditlog_entry(request, "Shutdown", instance, cluster_slug)
    jobid = cluster.shutdown_instance(instance)
    auditlog.update(
        job_id=jobid
    )
    action = {'action': _("Please wait... shutting-down")}
    clear_cluster_user_cache(request.user.username, cluster_slug)
    return HttpResponse(json.dumps(action))


@login_required
@csrf_exempt
@check_instance_auth
@check_admin_lock
def rename_instance(
    request,
    cluster_slug,
    instance,
    action_id,
    action_value=None
):
    user = request.user
    if request.method == 'POST':
        form = InstanceRenameForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            action_value = data['hostname']
            action = notifyuseradvancedactions(
                user,
                cluster_slug,
                instance,
                action_id,
                action_value,
                None
            )
            return HttpResponse(json.dumps(action))
        else:
            return render_to_response(
                'rename_instance.html',
                {
                    'form': form,
                    'instance': instance,
                    'cluster_slug': cluster_slug
                },
                context_instance=RequestContext(request)
            )
    elif request.method == 'GET':
        form = InstanceRenameForm()
        return render_to_response(
            'rename_instance.html',
            {
                'form': form,
                'instance': instance,
                'cluster_slug': cluster_slug
            },
            context_instance=RequestContext(request)
        )


@login_required
@csrf_exempt
@check_instance_auth
@check_admin_lock
@require_http_methods(['POST'])
def reinstalldestroy(
    request,
    cluster_slug,
    instance,
    action_id,
    action_value=None
):
    new_operating_system = request.POST.get('operating_system', 'none') or None
    user = request.user
    action = notifyuseradvancedactions(
        user,
        cluster_slug,
        instance,
        action_id,
        action_value,
        new_operating_system
    )
    return HttpResponse(json.dumps(action))


def notifyuseradvancedactions(user, cluster_slug, instance, action_id, action_value, new_operating_system):
    action_id = int(action_id)
    if action_id not in [1, 2, 3]:
        action = {'action': _("Not allowed action")}
        return action
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    instance = cluster.get_instance_or_404(instance)
    reinstalldestroy_req = InstanceAction.objects.create_action(user, instance, cluster, action_id, action_value, new_operating_system)
    fqdn = Site.objects.get_current().domain
    url = "https://%s%s" % \
        (
            fqdn,
            reverse(
                "reinstall-destroy-review",
                kwargs={
                    'application_hash': reinstalldestroy_req.activation_key,
                    'action_id': action_id
                }
            )
        )
    email = render_to_string(
        "reinstall_mail.txt",
        {
            "instance": instance,
            "user": user,
            "action": reinstalldestroy_req.get_action_display(),
            "action_value": reinstalldestroy_req.action_value,
            "url": url,
            "operating_system": reinstalldestroy_req.operating_system
        }
    )
    if action_id == 1:
        action_mail_text = _("re-installation")
    if action_id == 2:
        action_mail_text = _("destruction")
    if action_id == 3:
        action_mail_text = _("rename")
    try:
        send_mail(
            _("%(pref)sInstance %(action)s requested: %(instance)s") % {
                "pref": settings.EMAIL_SUBJECT_PREFIX,
                "action": action_mail_text,
                "instance": instance.name
            },
            email, settings.SERVER_EMAIL, [user.email]
        )
    # if anything goes wrong do nothing.
    except:
        # remove entry
        reinstalldestroy_req.delete()
        action = {'action': _("Could not send email")}
    else:
        action = {'action': _("Mail sent")}
    return action


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


@login_required
@csrf_exempt
@check_instance_auth
@check_admin_lock
def startup(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    auditlog = auditlog_entry(request, "Start", instance, cluster_slug)
    jobid = cluster.startup_instance(instance)
    auditlog.update(job_id=jobid)
    action = {
        'action': _("Please wait... starting-up")
    }
    clear_cluster_user_cache(request.user.username, cluster_slug)
    return HttpResponse(json.dumps(action))


@login_required
@csrf_exempt
@check_instance_auth
@check_admin_lock
def reboot(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    auditlog = auditlog_entry(request, "Reboot", instance, cluster_slug)
    jobid = cluster.reboot_instance(instance)
    auditlog.update(
        job_id=jobid
    )
    action = {'action': _("Please wait... rebooting")}
    clear_cluster_user_cache(request.user.username, cluster_slug)
    return HttpResponse(json.dumps(action))


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


class InstanceConfigForm(forms.Form):
    nic_type = forms.ChoiceField(label=ugettext_lazy("Network adapter model"),
                                 choices=(('paravirtual', 'Paravirtualized'),
                                          ('rtl8139', 'Realtek 8139+'),
                                          ('e1000', 'Intel PRO/1000'),
                                          ('ne2k_pci', 'NE2000 PCI')))

    disk_type = forms.ChoiceField(label=ugettext_lazy("Hard disk type"),
                                  choices=(('paravirtual', 'Paravirtualized'),
                                           ('scsi', 'SCSI'),
                                           ('ide', 'IDE')))

    boot_order = forms.ChoiceField(label=ugettext_lazy("Boot device"),
                                   choices=(('disk', 'Hard disk'),
                                            ('cdrom', 'CDROM')))

    cdrom_type = forms.ChoiceField(label=ugettext_lazy("CD-ROM Drive"),
                                   choices=(('none', 'Disabled'),
                                            ('iso',
                                             'ISO Image over HTTP (see below)')),
                                   widget=forms.widgets.RadioSelect())

    cdrom_image_path = forms.CharField(required=False,
                                       label=ugettext_lazy("ISO Image URL (http)"))

    use_localtime = forms.BooleanField(
        label=ugettext_lazy(
            "Hardware clock uses local time"
            " instead of UTC"
        ),
        required=False
    )
    whitelist_ip = forms.CharField(
        required=False,
        label=ugettext_lazy("Allow From"),
        help_text="If isolated, allow access from v4/v6 address/network"
    )

    def clean_cdrom_image_path(self):
        data = self.cleaned_data['cdrom_image_path']
        if data:
            if not (data == 'none' or re.match(r'(https?|ftp)://', data)):
                raise forms.ValidationError(_('Only HTTP URLs are allowed'))

            elif data != 'none':
                # Check if the image is there
                oldtimeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(5)
                try:
                    urllib2.urlopen(data)
                    socket.setdefaulttimeout(oldtimeout)
                except ValueError:
                    socket.setdefaulttimeout(oldtimeout)
                    raise forms.ValidationError(
                        _('%(url)s is not a valid URL') % {'url': data}
                    )
                except:  # urllib2 HTTP errors
                    socket.setdefaulttimeout(oldtimeout)
                    raise forms.ValidationError(_('Invalid URL'))
        return data

    def clean_whitelist_ip(self):
        data = self.cleaned_data['whitelist_ip']
        if data:
            try:
                address = IPNetwork(data)
                if address.version == 4:
                    if address.prefixlen < settings.WHITELIST_IP_MAX_SUBNET_V4:
                        error = _(
                            "Currently no prefix lengths < %s are allowed"
                        ) % settings.WHITELIST_IP_MAX_SUBNET_V4
                        raise forms.ValidationError(error)
                if address.version == 6:
                    if address.prefixlen < settings.WHITELIST_IP_MAX_SUBNET_V6:
                        error = _(
                            "Currently no prefix lengths < %s are allowed"
                        ) % settings.WHITELIST_IP_MAX_SUBNET_V6
                        raise forms.ValidationError(error)
                if address.is_unspecified:
                    raise forms.ValidationError('Address is unspecified')
            except ValueError:
                raise forms.ValidationError(
                    _(
                        '%(address)s is not a valid address'
                    ) % {'address': data}
                )
            data = address.compressed
        return data


@login_required
@check_instance_readonly
def instance(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    instance = cluster.get_instance_or_404(instance)
    if request.method == 'POST':
        configform = InstanceConfigForm(request.POST)
        if configform.is_valid():
            needs_reboot = False
            # The instance needs reboot if any of the hvparams have changed.
            if configform.cleaned_data['cdrom_type'] == 'none':
                configform.cleaned_data['cdrom_image_path'] = ""
            for key, val in configform.cleaned_data.items():
                if key == "cdrom_type":
                    continue
                if key == "whitelist_ip":
                    continue
                if configform.cleaned_data[key] != instance.hvparams[key]:
                    if instance.admin_state:
                        needs_reboot = True
            if configform.cleaned_data['cdrom_type'] == 'none':
                configform.cleaned_data['cdrom_image_path'] = ""
            elif (configform.cleaned_data['cdrom_image_path'] !=
                  instance.hvparams['cdrom_image_path']):
                # This should be an http URL
                if (
                    not (
                        configform.cleaned_data['cdrom_image_path'].startswith(
                            'http://'
                        ) or
                        configform.cleaned_data['cdrom_image_path'] == ""
                    )
                ):
                    # Remove this, we don't want them to
                    # be able to read local files
                    del configform.cleaned_data['cdrom_image_path']
            data = {}
            whitelistip = None
            for key, val in configform.cleaned_data.items():
                if key == "cdrom_type":
                    continue
                if key == "whitelist_ip":
                    whitelistip = val
                    if len(val) == 0:
                        whitelistip = None
                    continue
                data[key] = val
            auditlog = auditlog_entry(
                request,
                "Setting %s" % (
                    ", ".join(
                        [
                            "%s:%s" % (key, value) for key, value in data.iteritems()
                        ]
                    )
                ),
                instance,
                cluster_slug
            )
            jobid = instance.set_params(hvparams=data)
            auditlog.update(job_id=jobid)
            if needs_reboot:
                instance.cluster.tag_instance(
                    instance.name,
                    ["%s:needsreboot" % (GANETI_TAG_PREFIX)]
                )
            if instance.whitelistip and whitelistip is None:
                auditlog = auditlog_entry(
                    request,
                    "Remove whitelist %s" % instance.whitelistip,
                    instance,
                    cluster_slug
                )
                jobid = instance.cluster.untag_instance(
                    instance.name,
                    ["%s:whitelist_ip:%s" % (
                        GANETI_TAG_PREFIX,
                        instance.whitelistip
                    )]
                )
                auditlog.update(job_id=jobid)
                instance.cluster.migrate_instance(instance.name)
            if whitelistip:
                if instance.whitelistip:
                    auditlog = auditlog_entry(
                        request,
                        "Remove whitelist %s" % instance.whitelistip,
                        instance,
                        cluster_slug
                    )
                    jobid = instance.cluster.untag_instance(
                        instance.name,
                        ["%s:whitelist_ip:%s" % (
                            GANETI_TAG_PREFIX,
                            instance.whitelistip
                        )])
                    auditlog.update(job_id=jobid)
                auditlog = auditlog_entry(
                    request,
                    "Add whitelist %s" % whitelistip, instance, cluster_slug
                )
                jobid = instance.cluster.tag_instance(
                    instance.name,
                    ["%s:whitelist_ip:%s" % (GANETI_TAG_PREFIX, whitelistip)]
                )
                auditlog.update(job_id=jobid)
                instance.cluster.migrate_instance(instance.name)
            # Prevent form re-submission via browser refresh
            return HttpResponseRedirect(
                reverse(
                    'instance-detail',
                    kwargs={'cluster_slug': cluster_slug, 'instance': instance}
                )
            )
    else:
        if 'cdrom_image_path' in instance.hvparams.keys():
            if instance.hvparams['cdrom_image_path']:
                instance.hvparams['cdrom_type'] = 'iso'
            else:
                instance.hvparams['cdrom_type'] = 'none'
        else:
            instance.hvparams['cdrom_type'] = 'none'
        if instance.whitelistip:
            instance.hvparams['whitelist_ip'] = instance.whitelistip
        else:
            instance.hvparams['whitelist_ip'] = ''
        configform = InstanceConfigForm(instance.hvparams)
    instance.cpu_url = reverse(
        graph,
        args=(cluster.slug, instance.name, 'cpu-ts')
    )
    instance.net_url = []
    for (nic_i, link) in enumerate(instance.nic_links):
        instance.net_url.append(
            reverse(
                graph,
                args=(cluster.slug, instance.name, 'net-ts', '/eth%s' % nic_i)
            )
        )

    instance.netw = []
    try:
        instance.osname = get_os_details(
            instance.osparams['img_id']).get(
            'description', instance.osparams['img_id']
        )
    except Exception:
        try:
            instance.osname = instance.osparams['img_id']
        except Exception:
            instance.osname = instance.os
    instance.node_group_locked = instance.pnode in instance.cluster.locked_nodes_from_nodegroup()
    for (nic_i, link) in enumerate(instance.nic_links):
        if instance.nic_ips[nic_i] is None:
            instance.netw.append("%s" % (instance.nic_links[nic_i]))
        else:
            instance.netw.append("%s@%s" % (
                instance.nic_ips[nic_i], instance.nic_links[nic_i])
            )
    if instance.isolate and instance.whitelistip is None:
        messages.add_message(
            request,
            messages.ERROR,
            "Your instance is isolated from the network and" +
            " you have not set an \"Allowed From\" address." +
            " To access your instance from a specific network range," +
            " you can set it via the instance configuration form"
        )
    if instance.needsreboot:
        messages.add_message(
            request,
            messages.ERROR,
            "You have modified one or more of your instance's core " +
            "configuration components  (any of network adapter, hard" +
            " disk type, boot device, cdrom). In order for these changes " +
            "to take effect, you need to <strong>Reboot</strong>" +
            " your instance.",
            extra_tags='safe'
        )
    ret_dict = {'cluster': cluster,
                'instance': instance
                }
    if not request.user.has_perm('ganeti.view_instances') or (
        request.user.is_superuser or
        request.user in instance.users or
        set.intersection(set(request.user.groups.all()), set(instance.groups))
    ):
            ret_dict['configform'] = configform
    return render_to_response("instance.html",
                              ret_dict,
                              context_instance=RequestContext(request))


@login_required
def instance_popup(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        if request.method == 'GET':
            if 'cluster' in request.GET:
                cluster_slug = request.GET.get('cluster')
            if 'instance' in request.GET:
                instance = request.GET.get('instance')
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        instance = cluster.get_instance_or_404(instance)

        return render_to_response("instance_popup.html",
                                  {'cluster': cluster,
                                   'instance': instance},
                                  context_instance=RequestContext(request))
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@login_required
@check_instance_auth
def poll(request, cluster_slug, instance):
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        instance = cluster.get_instance_or_404(instance)
        try:
            instance.osname = instance.osparams['img_id']
        except Exception:
            instance.osname = instance.os
        instance.node_group_locked = instance.pnode in instance.cluster.locked_nodes_from_nodegroup()
        return render_to_response(
            "instance_actions.html",
            {
                'cluster': cluster,
                'instance': instance,
            },
            context_instance=RequestContext(request)
        )


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


@login_required
def get_clusternodes(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        nodes = cache.get('allclusternodes')
        bad_clusters = cache.get('badclusters')
        bad_nodes = cache.get('badnodes')
        if nodes is None:
            nodes, bad_clusters, bad_nodes = prepare_clusternodes()
            cache.set('allclusternodes', nodes, 90)
        if bad_clusters:
            messages.add_message(
                request,
                msgs.WARNING,
                "Some nodes may be missing because the" +
                " following clusters are unreachable: " +
                ", ".join([c.description for c in bad_clusters])
            )
            cache.set('badclusters', bad_clusters, 90)
        if bad_nodes:
            messages.add_message(
                request,
                msgs.ERROR,
                "Some nodes appear to be offline: " +
                ", ".join(bad_nodes)
            )
            cache.set('badnodes', bad_nodes, 90)
        if settings.SERVER_MONITORING_URL:
            servermon_url = settings.SERVER_MONITORING_URL
        status_dict = {}
        status_dict['offline'] = 0
        status_dict['regular'] = 0
        status_dict['drained'] = 0
        status_dict['master'] = 0
        status_dict['candidate'] = 0
        for n in nodes:
            if n['role'] == 'O':
                status_dict['offline'] += 1
            if n['role'] == 'D':
                status_dict['drained'] += 1
            if n['role'] == 'R':
                status_dict['regular'] += 1
            if n['role'] == 'C':
                status_dict['candidate'] += 1
            if n['role'] == 'M':
                status_dict['master'] += 1
        clusters = list(set([n['cluster'] for n in nodes]))
        return render_to_response(
            'cluster_nodes.html',
            {
                'nodes': nodes,
                'clusters': clusters,
                'statuses': status_dict,
                'servermon': servermon_url
            },
            context_instance=RequestContext(request)
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


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
            cluster = Cluster.objects.get(slug=cluster_slug)
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
                'nodes-graphs.html',
                {
                    'form': form,
                    'results': res
                }
            )
        else:
            return render(
                request,
                'nodes-graphs.html',
                {'form': form}
            )
    else:
        raise PermissionDenied


@login_required
def clusternodes_json(request, cluster=None):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        nodedetails = []
        jresp = {}
        nodes = None
        nodes = cache.get('allclusternodes')
        bad_clusters = cache.get('badclusters')
        bad_nodes = cache.get('badnodes')
        if nodes is None:
            nodes, bad_clusters, bad_nodes = prepare_clusternodes()
            cache.set('allclusternodes', nodes, 90)
        if bad_clusters:
            messages.add_message(
                request,
                messages.WARNING,
                "Some nodes may be missing because the" +
                " following clusters are unreachable: " +
                ", ".join([c.description for c in bad_clusters])
            )
            cache.set('badclusters', bad_clusters, 90)
        if bad_nodes:
            messages.add_message(
                request,
                messages.ERROR,
                "Some nodes appear to be offline: " +
                ", ".join(bad_nodes)
            )
            cache.set('badnodes', bad_nodes, 90)
        if cluster:
            try:
                cluster = Cluster.objects.get(hostname=cluster)
            except Cluster.DoesNotExist:
                cluster = None
        for node in nodes:
            if not cluster or (cluster and node['cluster'] == cluster.slug):
                node_dict = {}
                node_dict['name'] = node['name']
                # node_dict['node_group'] = node['node_group']
                node_dict['mem_used'] = node['mem_used']
                node_dict['mfree'] = node['mfree']
                node_dict['mtotal'] = node['mtotal']
                node_dict['shared_storage'] = node['shared_storage']
                node_dict['disk_used'] = node['disk_used']
                node_dict['dfree'] = node['dfree']
                node_dict['dtotal'] = node['dtotal']
                node_dict['ctotal'] = node['ctotal']
                node_dict['pinst_cnt'] = node['pinst_cnt']
                node_dict['pinst_list'] = node['pinst_list']
                node_dict['role'] = node['role']
                if cluster:
                    node_dict['cluster'] = cluster.hostname
                else:
                    node_dict['cluster'] = node['cluster']
                nodedetails.append(node_dict)
        jresp['aaData'] = nodedetails
        res = jresp
        return HttpResponse(json.dumps(res), mimetype='application/json')
    else:
        return HttpResponse(
            json.dumps({'error': 'Unauthorized access'}),
            mimetype='application/json'
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
def stats(request):
    clusters = Cluster.objects.all()
    exclude_pks = []
    if (request.user.is_superuser or request.user.has_perm('ganeti.view_instances')):
        instances = cache.get('leninstances')
        if instances is None:
            p = Pool(20)
            instances = []

            def _get_instances(cluster):
                try:
                    instances.extend(cluster.get_user_instances(request.user))
                except (GanetiApiError, Exception):
                    exclude_pks.append(cluster.pk)
                finally:
                    close_connection()
            if not request.user.is_anonymous():
                p.imap(_get_instances, clusters)
                p.join()
            instances = len(instances)
            cache.set('leninstances', instances, 90)
        users = cache.get('lenusers')
        if users is None:
            users = len(User.objects.all())
            cache.set('lenusers', users, 90)
        groups = cache.get('lengroups')
        if groups is None:
            groups = len(Group.objects.all())
            cache.set('lengroups', groups, 90)
        instance_apps = cache.get('leninstapps')
        if instance_apps is None:
            instance_apps = len(InstanceApplication.objects.all())
            cache.set('leninstapps', instance_apps, 90)
        orgs = cache.get('lenorgs')
        if orgs is None:
            orgs = len(Organization.objects.all())
            cache.set('lenorgs', orgs, 90)
        if exclude_pks:
            clusters = clusters.exclude(pk__in=exclude_pks)
        return render_to_response(
            'statistics.html',
            {
                'clusters': clusters,
                'instances': instances,
                'users': users,
                'groups': groups,
                'instance_apps': instance_apps,
                'orgs': orgs
            },
            context_instance=RequestContext(request)
        )
    else:
        return render_to_response(
            'statistics.html',
            {'clusters': clusters},
            context_instance=RequestContext(request)
        )


@login_required
def stats_ajax_instances(request):
    username = request.user.username
    cluster_list = cache.get('%s:ajaxinstances' % username)
    if cluster_list is None:
        clusters = Cluster.objects.all()
        i = 0
        cluster_list = []
        for cluster in clusters:
            cinstances = []
            i = 0
            cluster_dict = {}
            if (
                request.user.is_superuser or
                request.user.has_perm('ganeti.view_instances')
            ):
                cluster_dict['name'] = cluster.slug
            else:
                cluster_dict['name'] = cluster.description
            cluster_dict['instances'] = []
            try:
                cinstances.extend(cluster.get_user_instances(request.user))
            except (GanetiApiError, Timeout):
                cinstances = []
            for instance in cinstances:
                inst_dict = {}
                inst_dict['time'] = (1000 * mktime(instance.ctime.timetuple()))
                inst_dict['name'] = instance.name
                cluster_dict['instances'].append(inst_dict)
            cluster_dict['instances'] = sorted(
                cluster_dict['instances'],
                key=itemgetter('time')
            )
            for item in cluster_dict['instances']:
                i = i + 1
                item['count'] = i
            if len(cinstances) > 0:
                cluster_list.append(cluster_dict)
        cache.set('%s:ajaxinstances' % username, cluster_list, 90)
    return HttpResponse(json.dumps(cluster_list), mimetype='application/json')


@login_required
def stats_ajax_vms_per_cluster(request, cluster_slug):
    cluster_dict = cache.get('%s:ajaxvmscluster:%s' % (
        request.user.username,
        cluster_slug)
    )
    if cluster_dict is None:
        cluster = Cluster.objects.get(slug=cluster_slug)
        cluster_dict = {}
        cluster_dict['name'] = cluster.slug
        cluster_dict['instances'] = {'up': 0, 'down': 0}
        cinstances = []
        try:
            cinstances.extend(cluster.get_user_instances(request.user))
        except (GanetiApiError, Timeout):
            return HttpResponse(json.dumps([]), mimetype='application/json')
        for instance in cinstances:
            if instance.admin_state:
                cluster_dict['instances']['up'] = cluster_dict['instances']['up'] + 1
            else:
                cluster_dict['instances']['down'] = cluster_dict['instances']['down'] + 1
        cache.set(
            '%s:ajaxvmscluster:%s' % (
                request.user.username,
                cluster_slug
            ),
            cluster_dict,
            90
        )
    return HttpResponse(json.dumps(cluster_dict), mimetype='application/json')


@login_required
def stats_ajax_applications(request):
    username = request.user.username
    app_list = cache.get('%s:ajaxapplist' % username)
    if app_list is None:
        applications = InstanceApplication.objects.all().order_by('filed')
        if not (
            request.user.is_superuser or
            request.user.has_perm('ganeti.view_instances')
        ):
            applications = applications.filter(applicant=request.user)
        app_list = []
        i = 0
        for app in applications:
            appd = {}
            appd['instance'] = app.hostname
            i = i + 1
            appd['count'] = i
            appd['user'] = app.applicant.username
            appd['time'] = (1000 * mktime(app.filed.timetuple()))
            app_list.append(appd)
        cache.set('%s:ajaxapplist' % username, app_list, 90)
    return HttpResponse(json.dumps(app_list), mimetype='application/json')


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
        if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
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


def disksizes(value):
    return [filesizeformat(v * 1024 ** 2) for v in value]


def memsize(value):
    return filesizeformat(value * 1024 ** 2)


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
    return HttpResponse(response.read(), mimetype="image/png")


@login_required
def idle_accounts(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        idle_users = []
        idle_users.extend([
            u for u in User.objects.filter(
                is_active=True,
                last_login__lte=datetime.datetime.now() - datetime.timedelta(
                    days=int(settings.IDLE_ACCOUNT_NOTIFICATION_DAYS)
                )
            ) if u.email
        ])
        idle_users = list(set(idle_users))
        return render_to_response('idle_accounts.html', {'users': idle_users},
                                  context_instance=RequestContext(request))


def clear_cluster_user_cache(username, cluster_slug):
    cache.delete("user:%s:index:instances" % username)
    cache.delete("cluster:%s:instances" % cluster_slug)


def refresh_cluster_cache(cluster, instance):
    cluster.force_cluster_cache_refresh(instance)
    for u in User.objects.all():
        cache.delete("user:%s:index:instances" % u.username)
    nodes, bc, bn = prepare_clusternodes()
    cache.set('allclusternodes', nodes, 90)
    cache.set('badclusters', bc, 90)
    cache.set('badnodes', bn, 90)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def auditlog_entry(request, action, instance, cluster, save=True):
    entry = AuditEntry(
        requester=User.objects.get(pk=request.user.id),
        ipaddress=get_client_ip(request),
        action=action,
        instance=instance,
        cluster=cluster
    )
    if save:
        entry.save()
    return entry

