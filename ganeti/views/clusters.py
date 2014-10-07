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

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.contrib.messages import constants as msgs
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apply.utils import get_os_details

from auditlog.utils import auditlog_entry
from ganeti.forms import InstanceConfigForm
from ganeti.decorators import (
    check_instance_auth,
    check_admin_lock,
    check_instance_readonly
)
from ganeti.forms import InstanceRenameForm

from ganeti.utils import (
    prepare_clusternodes,
    clear_cluster_user_cache,
    notifyuseradvancedactions
)
from ganeti.models import Cluster


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
            msgs.add_message(
                request,
                msgs.WARNING,
                "Some nodes may be missing because the" +
                " following clusters are unreachable: " +
                ", ".join([c.description for c in bad_clusters])
            )
            cache.set('badclusters', bad_clusters, 90)
        if bad_nodes:
            msgs.add_message(
                request,
                msgs.ERROR,
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

        return render(
            request,
            'instance_popup.html',
            {
                'cluster': cluster,
                'instance': instance
            }
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


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
            msgs.add_message(
                request,
                msgs.WARNING,
                "Some nodes may be missing because the" +
                " following clusters are unreachable: " +
                ", ".join([c.description for c in bad_clusters])
            )
            cache.set('badclusters', bad_clusters, 90)
        if bad_nodes:
            msgs.add_message(
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
        return render(
            request,
            'cluster_nodes.html',
            {
                'nodes': nodes,
                'clusters': clusters,
                'statuses': status_dict,
                'servermon': servermon_url
            }
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))



