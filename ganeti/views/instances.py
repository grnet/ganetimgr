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
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.messages import constants as msgs
from django.contrib import messages as djmessages
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.conf import settings
from django.db import close_old_connections
from django.http import HttpResponseRedirect, HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import authenticate

from django.http import JsonResponse

if 'oauth2_provider' in settings.INSTALLED_APPS:
    from oauth2_provider.decorators import protected_resource

from auditlog.utils import auditlog_entry

from util.client import GanetiApiError

from ganeti.utils import (
    generate_json,
    generate_json_light,
    clear_cluster_user_cache,
    notifyuseradvancedactions,
    get_os_details,
    get_user_instances,
    format_ganeti_api_error,
)

from ganeti.forms import (
    InstanceRenameForm,
    InstanceConfigForm,
    lockForm,
    isolateForm
)

from ganeti.models import *
from ganeti.decorators import (
    check_instance_auth,
    check_admin_lock,
    check_instance_readonly,
)


def user_index(request):
    if request.user.is_anonymous():
        return HttpResponseRedirect(reverse('login'))

    return render(
        request,
        'instances/user_instances_json.html',
        {}
    )


if 'oauth2_provider' in settings.INSTALLED_APPS:
    @protected_resource()
    def list_user_instances(request):
        '''
        This view a username and a password and
        returns the user's instances,
        if the credentials are valid.
        '''
        from oauth2_provider.models import AccessToken
        token = get_object_or_404(AccessToken, token=request.GET.get('access_token'))
        user = token.user
        # is the api user requests a specific tag we must filter the vms
        # by this tag
        tag = request.GET.get('tag')
        if tag:
            response = get_user_instances(
                user,
                admin=False,
                tag=tag
            )
        else:
            response = get_user_instances(user, admin=False)
        return HttpResponse(
            json.dumps(
                {
                    'user': {
                        'username': user.username,
                        'email': user.email,
                        'id': user.pk,
                    },
                    'response': response
                }
            ),
            content_type='application/json'
        )
else:
    def list_user_instances(request):
        raise NotImplementedError('Please install oauth2_toolkit. For more details take a look at admin section of the docs.')


@login_required
def user_index_json(request):
    cluster_slug = request.GET.get('cluster', None)
    if request.user.is_anonymous():
        action = {
            'error': _(
                "Permissions' violation. This action has been logged"
                " and our admins will be notified about it"
            )
        }
        return HttpResponse(json.dumps(action), content_type='application/json')
    p = Pool(20)
    instances = []
    bad_clusters = []
    bad_instances = []
    locked_clusters = []
    locked_nodes = []

    def _get_instances(cluster):
            try:
                cluster_locked_nodes = cluster.locked_nodes_from_nodegroup()
                if cluster_locked_nodes:
                    locked_clusters.append(str(cluster.description))
                    locked_nodes.extend(cluster_locked_node_groups)
                instances.extend(cluster.get_user_instances(request.user))
            except GanetiApiError as e:
                bad_clusters.append((cluster, format_ganeti_api_error(e)))
            except Exception as e:
                bad_clusters.append((cluster, e))
            finally:
                close_old_connections()
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
            instancedetails.extend(generate_json(instance, request.user, locked_nodes))
        except GanetiApiError as e:
            bad_clusters.append((cluster, format_ganeti_api_error(e)))
        except Exception as e:
                bad_clusters.append((cluster, e))
        finally:
            close_old_connections()
    if res is None:
        if not request.user.is_anonymous():
            if cluster_slug:
                clusters = Cluster.objects.filter(slug=cluster_slug)
            else:
                # get only enabled clusters
                clusters = Cluster.objects.filter(disabled=False)
            p.map(_get_instances, clusters)
        cache_timeout = 900
        if bad_clusters:
            if request.user.is_superuser:
                djmessages.add_message(
                    request,
                    msgs.WARNING,
                    "Some instances may be missing because the"
                    " following clusters are unreachable: %s"
                    % (
                        ", ".join(
                            [
                                "%s: %s" % (
                                    c[0].slug or c[0].hostname,
                                    c[1]
                                ) for c in bad_clusters
                            ]
                        )
                    )
                )
            else:
                djmessages.add_message(
                    request,
                    msgs.WARNING,
                    "Some instances may be missing because the"
                    " following clusters are unreachable: %s"
                    % (
                        ", ".join(
                            [c[0].description or c[0].hostname for c in bad_clusters]
                        )
                    )
                )
                pass

            cache_timeout = 30
        j.map(_get_instance_details, instances)
        if locked_clusters:
            djmessages.add_message(
                request,
                msgs.WARNING,
                'Some clusters are under maintenance: <br> %s' % ', '.join(locked_clusters)
            )
        if bad_instances:
            djmessages.add_message(
                request,
                msgs.WARNING,
                "Could not get details for %s instances: %s. Please try again later." % (
                    str(len(bad_instances)),
                    ', '.join([i.name for i in bad_instances])
                )
            )
            cache_timeout = 30

        jresp['aaData'] = instancedetails
        cache.set(cache_key, jresp, cache_timeout)
        res = jresp

    return HttpResponse(json.dumps(res), content_type='application/json')


@login_required
def user_sum_stats(request):
    if request.user.is_anonymous():
        action = {
            'error': _(
                "Permissions' violation. This action has been"
                " logged and our admins will be notified about it"
            )
        }
        return HttpResponse(json.dumps(action), content_type='application/json')
    p = Pool(20)
    instances = []
    bad_clusters = []

    def _get_instances(cluster):
        try:
            instances.extend(cluster.get_user_instances(request.user))
        except GanetiApiError as e:
            bad_clusters.append((cluster, format_ganeti_api_error(e)))
        except Exception as e:
            bad_clusters.append((cluster, e))

        finally:
            close_old_connections()
    if not request.user.is_anonymous():
        # get only enabled clusters
        p.map(_get_instances, Cluster.objects.filter(disabled=False))

    if bad_clusters:
        for c in bad_clusters:
            if request.user.is_superuser:
                djmessages.add_message(
                    request,
                    msgs.WARNING,
                    "Some instances may be missing because the following clusters are unreachable: %s" % (
                        ", ".join(
                            [
                                "%s: %s" % (
                                    c[0].slug or c[0].hostname,
                                    c[1]
                                )
                            ]
                        )
                    )
                )
            else:
                djmessages.add_message(
                    request,
                    msgs.WARNING,
                    "Some instances may be missing because the following clusters are unreachable: %s" % (
                        ", ".join(
                            [
                                "%s" % (
                                    c[0].slug or c[0].hostname,
                                )
                            ]
                        )
                    )
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
            close_old_connections()
    if res is None:
        j.map(_get_instance_details, instances)
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
        cache.set(cache_key_stats, return_dict, 300)
        instances_stats = return_dict
    return HttpResponse(
        json.dumps(instances_stats),
        content_type='application/json'
    )


@login_required
def poll(request, cluster_slug, instance):
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        instance = cluster.get_instance_or_404(instance)
        if (
            request.user.is_superuser or
            request.user in instance.users or
            set.intersection(
                set(request.user.groups.all()), set(instance.groups)
            )
        ):
            try:
                instance.osname = instance.osparams['img_id']
            except Exception:
                instance.osname = instance.os
            instance.node_group_locked = instance.pnode in instance.cluster.locked_nodes_from_nodegroup()
            return render(
                request,
                'instances/instance_actions.html',
                {
                    'cluster': cluster,
                    'instance': instance,
                },
            )
        elif request.user.has_perm('ganeti.view_instances'):
            return render(
                request,
                'instances/includes/instance_status.html',
                {
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
        'instances/vnc.html',
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
        'instances/novnc.html',
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
    return HttpResponse(result, content_type='application/json')


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
@check_admin_lock
@check_instance_auth
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
            'instances/rename_instance.html',
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
                        configform.cleaned_data['cdrom_image_path'].startswith(
                            'https://'
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
    instance.node_group_locked = instance.pnode in instance.cluster.locked_nodes_from_nodegroup()
    for (nic_i, link) in enumerate(instance.nic_links):
        if instance.nic_ips[nic_i] is None:
            instance.netw.append("%s" % (instance.nic_links[nic_i]))
        else:
            instance.netw.append("%s@%s" % (
                instance.nic_ips[nic_i], instance.nic_links[nic_i])
            )
    if instance.isolate and instance.whitelistip is None:

        djmessages.add_message(
            request,
            msgs.ERROR,
            "Your instance is isolated from the network and" +
            " you have not set an \"Allowed From\" address." +
            " To access your instance from a specific network range," +
            " you can set it via the instance configuration form"
        )
    if instance.needsreboot:
        djmessages.add_message(
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
        'instances/instance.html',
        ret_dict
    )


@csrf_exempt
@login_required
@permission_required('ganeti.can_lock')
def lock(request, instance):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        if instance:
            try:
                instance = Instance.objects.get(name=instance)
            except ObjectDoesNotExist:
                raise Http404()
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
                    # set the cache for a week
                    cache.set('instances:%s' % (instance.name), True, 60 * 60 * 24 * 7)
                    jobid = instance.cluster.tag_instance(
                        instance.name,
                        ["%s:adminlock" % settings.GANETI_TAG_PREFIX]
                    )
                    auditlog.update(job_id=jobid)
                if adminlock is False:
                    cache.delete('instances:%s' % (instance.name))
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
                return HttpResponse(json.dumps(res), content_type='application/json')
            else:
                return render(
                    request,
                    'tagging/lock.html',
                    {
                        'form': form,
                        'instance': instance
                    }
                )
        elif request.method == 'GET':
            form = lockForm(initial={'lock': instance_adminlock})
            return render(
                request,
                'tagging/lock.html',
                {
                    'form': form,
                    'instance': instance
                }
            )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@csrf_exempt
@login_required
@permission_required('ganeti.can_isolate')
def isolate(request, instance):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        if instance:
            try:
                instance = Instance.objects.get(name=instance)
            except ObjectDoesNotExist:
                raise Http404
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
                    json.dumps(res), content_type='application/json'
                )
            else:
                return render(
                    request,
                    'tagging/isolate.html',
                    {
                        'form': form,
                        'instance': instance
                    }
                )
        elif request.method == 'GET':
            form = isolateForm(initial={'isolate': instance_isolate})
            return render(
                request,
                'tagging/isolate.html',
                {
                    'form': form,
                    'instance': instance
                }
            )
    else:
        return HttpResponseRedirect(reverse('user-instances'))
