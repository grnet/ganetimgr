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
from django.conf import settings
from django.db import close_connection
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, render
from django.template.context import RequestContext
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from auditlog.utils import auditlog_entry

from util.client import GanetiApiError


from ganeti.utils import (
    generate_json,
    generate_json_light,
    clear_cluster_user_cache,
    notifyuseradvancedactions,
    get_os_details,
)
from ganeti.forms import (
    InstanceRenameForm,
    InstanceConfigForm,
    lockForm,
    isolateForm
)

from ganeti.models import Cluster, Instance
from ganeti.decorators import (
    check_instance_auth,
    check_admin_lock,
    check_instance_readonly,
)


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


@login_required
@check_instance_auth
def poll(request, cluster_slug, instance):
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        instance = cluster.get_instance_or_404(instance)
        try:
            instance.osname = instance.osparams['img_id']
        except Exception:
            instance.osname = instance.os
        instance.node_group_locked = instance.cluster.check_node_group_lock_by_node(
            instance.pnode
        )
        return render(
            request,
            'instance_actions.html',
            {
                'cluster': cluster,
                'instance': instance,
            },
        )


@login_required
@check_instance_auth
def vnc(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    port, password = cluster.setup_vnc_forwarding(instance)

    return render(
        request,
        'vnc.html',
        {
            'cluster': cluster,
            'instance': instance,
            'host': request.META['HTTP_HOST'],
            'port': port,
            'password': password
        }
    )


@login_required
@check_instance_auth
def novnc(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    use_tls = settings.NOVNC_USE_TLS
    return render(
        request,
        'novnc.html',
        {
            'cluster': cluster,
            'instance': instance,
            'use_tls': use_tls,
        }
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
    action = {'action': _('Please wait... shutting-down')}
    clear_cluster_user_cache(request.user.username, cluster_slug)
    return HttpResponse(json.dumps(action))


@login_required
@csrf_exempt
@check_instance_auth
@check_admin_lock
def startup(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    auditlog = auditlog_entry(request, 'Start', instance, cluster_slug)
    jobid = cluster.startup_instance(instance)
    auditlog.update(job_id=jobid)
    action = {
        'action': _('Please wait... starting-up')
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
    form = InstanceRenameForm(request.POST or None)
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
        return render(
            request,
            'rename_instance.html',
            {
                'form': form,
                'instance': instance,
                'cluster_slug': cluster_slug
            }
        )


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
                    ["%s:needsreboot" % (settings.GANETI_TAG_PREFIX)]
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
                        settings.GANETI_TAG_PREFIX,
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
                            settings.GANETI_TAG_PREFIX,
                            instance.whitelistip
                        )])
                    auditlog.update(job_id=jobid)
                auditlog = auditlog_entry(
                    request,
                    "Add whitelist %s" % whitelistip, instance, cluster_slug
                )
                jobid = instance.cluster.tag_instance(
                    instance.name,
                    ["%s:whitelist_ip:%s" % (settings.GANETI_TAG_PREFIX, whitelistip)]
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
        'graph',
        args=(cluster.slug, instance.name, 'cpu-ts')
    )
    instance.net_url = []
    for (nic_i, link) in enumerate(instance.nic_links):
        instance.net_url.append(
            reverse(
                'graph',
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
    instance.node_group_locked = instance.\
        cluster.check_node_group_lock_by_node(instance.pnode)
    for (nic_i, link) in enumerate(instance.nic_links):
        if instance.nic_ips[nic_i] is None:
            instance.netw.append("%s" % (instance.nic_links[nic_i]))
        else:
            instance.netw.append("%s@%s" % (
                instance.nic_ips[nic_i], instance.nic_links[nic_i])
            )
    if instance.isolate and instance.whitelistip is None:
        msgs.add_message(
            request,
            msgs.ERROR,
            "Your instance is isolated from the network and" +
            " you have not set an \"Allowed From\" address." +
            " To access your instance from a specific network range," +
            " you can set it via the instance configuration form"
        )
    if instance.needsreboot:
        msgs.add_message(
            request,
            msgs.ERROR,
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
    return render(
        request,
        'instance.html',
        ret_dict
    )


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
                        ["%s:adminlock" % settings.GANETI_TAG_PREFIX]
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
                        ["%s:adminlock" % settings.GANETI_TAG_PREFIX]
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
                        ["%s:isolate" % settings.GANETI_TAG_PREFIX]
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
                        ["%s:isolate" % settings.GANETI_TAG_PREFIX]
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

