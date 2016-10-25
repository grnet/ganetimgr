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
import re
import random
import hashlib
import base64
import os
import ipaddr

from datetime import datetime, timedelta
from gevent.pool import Pool
from socket import gethostbyname
from time import sleep
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.http import Http404
from django.core.cache import cache
from django.contrib.auth.models import User, Group
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.conf import settings

from util import vapclient
from util.client import GanetiRapiClient, GanetiApiError, GenericCurlConfig
from apply.models import Organization, InstanceApplication

GANETI_TAG_PREFIX = settings.GANETI_TAG_PREFIX

REQUEST_ACTIONS = (
    (1, 'reinstall'),
    (2, 'destroy'),
    (3, 'rename'),
    (4, 'mailchange')
)

RAPI_CONNECT_TIMEOUT = settings.RAPI_CONNECT_TIMEOUT
RAPI_RESPONSE_TIMEOUT = settings.RAPI_RESPONSE_TIMEOUT

SHA1_RE = re.compile('^[a-f0-9]{40}$')

if hasattr(settings, 'BEANSTALK_TUBE'):
    BEANSTALK_TUBE = settings.BEANSTALK_TUBE
else:
    BEANSTALK_TUBE = None

from util import beanstalkc

import json

from django.db import close_old_connections


class InstanceManager(object):

    def all(self):
        users, orgs, groups, instanceapps, networks = preload_instance_data()
        p = Pool(20)
        instances = []

        def _get_instances(cluster):
            try:
                instances.extend(cluster.get_instances())
            except (GanetiApiError, Exception):
                pass
            finally:
                close_old_connections()

        # get only enabled clusters
        clusters = Cluster.objects.filter(disabled=False)
        p.map(_get_instances, clusters)
        return instances

    def filter(self, **kwargs):
        users, orgs, groups, instanceapps, networks = preload_instance_data()
        if 'cluster' in kwargs:
            results = []
            if isinstance(kwargs['cluster'], Cluster):
                cluster = kwargs['cluster']
            else:
                try:
                    cluster = Cluster.objects.get(slug=kwargs['cluster'])
                except:
                    return []
            try:
                results = cluster.get_instances()
            except GanetiApiError:
                results = []
            del kwargs['cluster']
        else:
            results = self.all()

        for arg, val in kwargs.items():
            if arg == 'user':
                if not isinstance(val, User):
                    try:
                        val = users[val]
                    except:
                        return []
                results = [result for result in results if val in result.users]
            elif arg == 'group':
                if not isinstance(val, Group):
                    try:
                        val = groups[val]
                    except:
                        return []
                results = [result for result in results if val in result.groups]
            elif arg == 'name':
                results = [result for result in results if result.name == val]
            elif arg == 'name__icontains':
                valre = re.compile(val)
                results = [
                    result for result in results if valre.search(
                        result.name
                    ) is not None
                ]
            else:
                results = [result for result in results
                           if '%s:%s' % (arg, val) in result.tags]
        return results

    def get(self, **kwargs):
        results = self.filter(**kwargs)
        if len(results) == 1:
            return results[0]
        elif len(results) > 1:
            raise MultipleObjectsReturned("Multiple instances found")
        else:
            raise ObjectDoesNotExist("Could not find an instance")


class Instance(object):
    objects = InstanceManager()

    def __init__(
        self,
        cluster,
        name,
        info=None,
        listusers=None,
        listorganizations=None,
        listgroups=None,
        listinstanceapplications=None,
        networks=None
    ):
        self.cluster = cluster
        self.name = name
        self.listusers = listusers
        self.listorganizations = listorganizations
        self.listgroups = listgroups
        self.listinstanceapplications = listinstanceapplications
        self.networks = networks
        self.organization = None
        self.application = None
        self.services = []
        self.users = []
        self.groups = []
        self.links = []
        self.ipv6s = []
        self.admin_view_only = False
        self.adminlock = False
        self.isolate = False
        self.needsreboot = False
        self.whitelistip = None
        self.joblock = False
        self._update(info)

    def _update(self, info=None):
        user_cache = {}
        group_cache = {}
        org_cache = {}
        app_cache = {}
        serv_cache = {}
        if not info:
            info = self.cluster.get_instance_info(self.name)
        for attr in info:
            self.__dict__[attr.replace(".", "_")] = info[attr]
        for tag in self.tags:
            group_pfx = "%s:group:" % GANETI_TAG_PREFIX
            user_pfx = "%s:user:" % GANETI_TAG_PREFIX
            org_pfx = "%s:org:" % GANETI_TAG_PREFIX
            app_pfx = "%s:application:" % GANETI_TAG_PREFIX
            serv_pfx = "%s:service:" % GANETI_TAG_PREFIX
            adminlock_tag = "%s:adminlock" % GANETI_TAG_PREFIX
            isolate_tag = "%s:isolate" % GANETI_TAG_PREFIX
            needsreboot_tag = "%s:needsreboot" % GANETI_TAG_PREFIX
            whitelist_pfx = "%s:whitelist_ip:" % GANETI_TAG_PREFIX
            if tag.startswith(group_pfx):
                group = tag.replace(group_pfx, '')
                if group not in group_cache:
                    try:
                        g = self.listgroups[group]
                    except:
                        g = None
                    group_cache[group] = g
                if group_cache[group] is not None:
                    self.groups.append(group_cache[group])
            elif tag.startswith(user_pfx):
                user = tag.replace(user_pfx, '')
                if user not in user_cache:
                    try:
                        u = self.listusers[user]
                    except:
                        u = None
                    user_cache[user] = u
                if user_cache[user] is not None:
                    self.users.append(user_cache[user])
            elif tag.startswith(org_pfx):
                org = tag.replace(org_pfx, '')
                if org not in org_cache:
                    try:
                        o = self.listorganizations[org]
                    except:
                        o = None
                    org_cache[org] = o
                if org_cache[org] is not None:
                    self.organization = org_cache[org]
            elif tag.startswith(app_pfx):
                app = tag.replace(app_pfx, '')
                if app not in app_cache:
                    try:
                        a = self.listinstanceapplications[app]
                    except:
                        a = None
                    app_cache[app] = a
                if app_cache[app] is not None:
                    self.application = app_cache[app]
            elif tag.startswith(serv_pfx):
                serv = tag.replace(serv_pfx, '')
                if serv not in serv_cache:
                    serv_cache[serv] = serv
                if serv_cache[serv] is not None:
                    self.services.append(serv_cache[serv])
            elif tag == adminlock_tag:
                self.adminlock = True
            elif tag == isolate_tag:
                self.isolate = True
            elif tag == needsreboot_tag:
                self.needsreboot = True
            elif tag.startswith(whitelist_pfx):
                self.whitelistip = tag.replace(whitelist_pfx, '')
        if getattr(self, 'ctime', None):
            self.ctime = datetime.fromtimestamp(self.ctime)
        if getattr(self, 'mtime', None):
            self.mtime = datetime.fromtimestamp(self.mtime)
        for nlink in self.nic_links:
            try:
                self.links.append(self.networks[nlink])
            except Exception:
                pass
        for i in range(len(self.nic_modes)):
            if self.nic_modes[i] == 'bridged':
                self.nic_ips[i] = None
        for i in range(len(self.links)):
            try:
                ipv6addr = self.generate_ipv6(self.links[i], self.nic_macs[i])
                if not ipv6addr:
                    continue
                self.ipv6s.append("%s" % (ipv6addr))
            except Exception:
                pass
        if self.admin_state == 'up':
            self.admin_state = True
        if self.admin_state == 'down':
            self.admin_state = False

    def generate_ipv6(self, prefix, mac):
        try:
            prefix = ipaddr.IPv6Network(prefix)
            mac_parts = mac.split(":")
            prefix_parts = prefix.network.exploded.split(':')
            eui64 = mac_parts[:3] + ["ff", "fe"] + mac_parts[3:]
            eui64[0] = "%02x" % (int(eui64[0], 16) ^ 0x02)
            ip = ":".join(prefix_parts[:4])
            for l in range(0, len(eui64), 2):
                ip += ":%s" % "".join(eui64[l:l + 2])
            ip = ipaddr.IPAddress(ip).compressed
            return ip
        except:
            return False

    def get_state(self):
        if self.oper_state == self.admin_state:
            return _('Running') if self.oper_state else _('Stopped')
        else:
            return _('Running, should be stopped') if self.oper_state else _('Stopped, should be running')

    def set_params(self, **kwargs):
        job_id = self.cluster._client.ModifyInstance(self.name, **kwargs)
        self.lock(reason=_("modifying"), job_id=job_id)
        return job_id

    def __repr__(self):
        return "<Instance: '%s'>" % self.name

    def __unicode__(self):
        return self.name

    def get_lock_key(self):
        return self.cluster._instance_lock_key(self.name)

    def lock(self, reason="locked", timeout=30, job_id=None):
        self.cluster._lock_instance(self.name, reason, timeout, job_id)

    def is_locked(self):
        return cache.get(self.get_lock_key())

    def set_admin_view_only_True(self):
        self.admin_view_only = True

    def get_disk_template(self):
        info = self.cluster.get_instance_info(self.name)
        return info.get('disk_template')

    def _pending_action_request(self, action):
        '''This should return either 1 or 0 instance actions'''
        actions = []
        pending_actions = InstanceAction.objects.filter(
            instance=self.name,
            cluster=self.cluster,
            action=action
        )
        for pending in pending_actions:
            if pending.activation_key_expired():
                continue
            actions.append(pending)
        if len(actions) == 0:
            return False
        elif len(actions) == 1:
            return True
        else:
            for action in actions:
                action.expire_now()
            return False

    def pending_reinstall(self):
        return self._pending_action_request(1)

    def pending_destroy(self):
        return self._pending_action_request(2)

    def pending_rename(self):
        return self._pending_action_request(3)

    class Meta:
        permissions = (
            ("can_isolate", "Can Isolate"),
            ("can_lock", "Can Lock"),
        )


class Cluster(models.Model):
    hostname = models.CharField(max_length=128)
    slug = models.SlugField(max_length=50)
    port = models.PositiveIntegerField(default=5080)
    description = models.CharField(max_length=128, blank=True, null=True)
    username = models.CharField(max_length=64, blank=True, null=True)
    password = models.CharField(max_length=64, blank=True, null=True)
    fast_create = models.BooleanField(
        default=False,
        verbose_name="Enable fast instance creation",
        help_text="Allow fast instance creations on this cluster using the"
        " admin interface"
    )
    use_gnt_network = models.BooleanField(
        default=True,
        verbose_name="Cluster uses gnt-network",
        help_text="Set to True only if you use gnt-network."
    )
    disable_instance_creation = models.BooleanField(
        default=False,
        verbose_name="Disable Instance Creation",
        help_text="True disables setting a network at the application review form and blocks instance creation"
    )
    disabled = models.BooleanField(default=False)

    class Meta:
        permissions = (
            ("view_instances", "Can view all instances"),
        )

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        curl_conf = GenericCurlConfig(
            connect_timeout=RAPI_CONNECT_TIMEOUT,
            timeout=RAPI_RESPONSE_TIMEOUT
        )
        self._client = GanetiRapiClient(
            host=self.hostname,
            username=self.username,
            password=self.password,
            curl_config_fn=curl_conf
        )

    def __unicode__(self):
        return self.hostname

    def _instance_cache_key(self, instance):
        return "cluster:%s:instance:%s" % (self.slug, instance)

    def _instance_lock_key(self, instance):
        return "cluster:%s:instance:%s:lock" % (self.slug, instance)

    def _lock_instance(self, instance, reason="locked",
                       timeout=30, job_id=None):
        lock_key = self._instance_lock_key(instance)
        cache.set(lock_key, reason, timeout)
        locked_instances = cache.get('locked_instances')
        if locked_instances is not None:
            locked_instances["%s" % instance] = reason
            cache.set('locked_instances', locked_instances, 90)
        else:
            cache.set('locked_instances', {'%s' % instance: "%s" % reason}, 90)
        if job_id is not None:
            b = None
            for i in range(5):
                try:
                    b = beanstalkc.Connection()
                    break
                except Exception:
                    sleep(1)
            if b is None:
                return

            if BEANSTALK_TUBE:
                b.use(BEANSTALK_TUBE)
            b.put(json.dumps({
                "type": "JOB_LOCK",
                "cluster": self.slug,
                "instance": instance,
                "job_id": job_id,
                "lock_key": lock_key,
                "flush_keys": [self._instance_cache_key(instance)]
            }))

    @classmethod
    def get_all_instances(cls):
        instances = []
        for cluster in cls.objects.all():
            instances.extend(cluster.get_instances())
        return instances

    def get_instance(self, name):
        info = self.get_instance_info(name)
        if info is None:
            raise Http404()
        users, orgs, groups, instanceapps, networks = preload_instance_data()
        return Instance(
            self,
            info["name"],
            info,
            listusers=users,
            listorganizations=orgs,
            listgroups=groups,
            listinstanceapplications=instanceapps,
            networks=networks
        )

    def get_instance_or_404(self, name):
        try:
            return self.get_instance(name)
        except GanetiApiError, err:
            if err.code == 404:
                raise Http404()
            else:
                raise

    def get_instances(self):
        retinstances = []
        instances = cache.get("cluster:%s:instances" % self.slug)
        if instances is None:
            instances = parseQuery(
                self._client.Query(
                    'instance',
                    [
                        'name',
                        'tags',
                        'pnode',
                        'snodes',
                        'disk.sizes',
                        'nic.modes',
                        'nic.ips',
                        'nic.links',
                        'status',
                        'admin_state',
                        'beparams',
                        'oper_state',
                        'hvparams',
                        'nic.macs',
                        'ctime',
                        'mtime'
                    ]))
            cache.set("cluster:%s:instances" % self.slug, instances, 180)
        users, orgs, groups, instanceapps, networks = preload_instance_data()
        retinstances = [
            Instance(
                self,
                info['name'],
                info,
                listusers=users,
                listorganizations=orgs,
                listgroups=groups,
                listinstanceapplications=instanceapps,
                networks=networks
            ) for info in instances
        ]
        return retinstances

    def force_cluster_cache_refresh(self, instance):
        '''Used in cases of actions that could potentially lock the cluster
        thus preventing users from listing, even for some seconds, their
        instances and delay node listing for admins
        '''
        retinstances = []
        instances = self._client.GetInstances(bulk=True)
        for i in instances:
            if i['name'] == instance:
                i['action_lock'] = True
        cache.set("cluster:%s:instances" % self.slug, instances, 45)
        users, orgs, groups, instanceapps, networks = preload_instance_data()
        retinstances = [
            Instance(
                self,
                info['name'],
                info,
                listusers=users,
                listorganizations=orgs,
                listgroups=groups,
                listinstanceapplications=instanceapps,
                networks=networks
            ) for info in instances
        ]
        return retinstances

    def get_user_instances(self, user, admin=True):
        instances = self.get_instances()
        if (user.is_superuser or user.has_perm('ganeti.view_instances')) and admin:
            return instances
        else:
            user = User.objects.filter(pk=user.pk).select_related(
                'groups'
            ).get()
            ugroups = []
            for ug in user.groups.all():
                ugroups.append(ug.pk)
            return [
                i for i in instances if (
                    user in i.users or
                    len(
                        list(set(ugroups).intersection(
                            set([g.id for g in i.groups]))
                        )
                    ) > 0
                )
            ]

    def get_cluster_info(self):
        info = cache.get("cluster:%s:info" % self.slug)

        if info is None:
            info = self._client.GetInfo()
            if 'ctime' in info and info['ctime']:
                info['ctime'] = datetime.fromtimestamp(info['ctime'])
            if 'mtime' in info and info['mtime']:
                info['mtime'] = datetime.fromtimestamp(info['mtime'])
            cache.set("cluster:%s:info" % self.slug, info, 180)

        return info

    def list_cluster_nodes(self):
        nodes = cache.get("cluster:%s:listnodes" % self.slug)
        if nodes is None:
            nodes = self._client.GetNodes()
            cache.set("cluster:%s:listnodes" % self.slug, nodes, 180)
        return nodes

    def get_cluster_nodes(self):
        nodes = cache.get("cluster:%s:nodes" % self.slug)
        if nodes is None:
            cachenodes = []
            nodes = parseQuery(
                self._client.Query(
                    'node',
                    [
                        'name',
                        'role',
                        'mfree',
                        'mtotal',
                        'dtotal',
                        'dfree',
                        'ctotal',
                        'group',
                        'pinst_cnt',
                        'offline',
                        'vm_capable',
                        'pinst_list'
                    ]))
            for info in nodes:
                info['cluster'] = self.slug
                if info['mfree'] is None:
                    info['mfree'] = 0
                if info['mtotal'] is None:
                    info['mtotal'] = 0
                if info['dtotal'] is None:
                    info['dtotal'] = 0
                if info['dfree'] is None:
                    info['dfree'] = 0
                try:
                    info['mem_used'] = 100 * (
                        info['mtotal'] - info['mfree']
                    ) / info['mtotal']
                except ZeroDivisionError:
                    '''this is the case where the node is offline and reports
                    none, thus it is 0'''
                    info['mem_used'] = 0
                try:
                    info['disk_used'] = 100 * (
                        info['dtotal'] - info['dfree']
                    ) / info['dtotal']
                except ZeroDivisionError:
                    '''this is the case where the node is offline and reports
                    none, thus it is 0'''
                    info['disk_used'] = 0
                info['shared_storage'] = False
                cachenodes.append(info)
            nodes = cachenodes
            cache.set("cluster:%s:nodes" % self.slug, nodes, 180)
        return nodes

    def get_available_nodes(self, node_group, number_of_nodes):
        ret_nodes = []
        nodes = self.get_cluster_nodes()
        for n in nodes:
            if n['role'] in ['D', 'O']:
                continue
            if n['group'] != node_group:
                continue
            if n['vm_capable'] is False:
                continue
            ret_nodes.append(n['name'])
        return ret_nodes[0:number_of_nodes]

    def get_node_groups(self):
        info = cache.get('cluster:%s:nodegroups' % self.slug)
        if info is None:
            #info = parseQuery(self._client.Query('group',['name', 'tags']))
            info = self._client.GetGroups(bulk=True)
            cache.set('cluster:%s:nodegroups' % self.slug, info, 180)
        return info

    def get_networks(self):
        info = cache.get('cluster:%s:networks' % self.slug)
        if info is None:
            info = self._client.GetNetworks(bulk=True)
            cache.set('cluster:%s:networks' % self.slug, info, 180)
        return info

    def get_node_group_networks(self, nodegroup):
        # This gets networks per nodegroup as received via a GetNetworks RAPI
        # callWe then perform a check for the existing networks in database
        # and add the bridged networks
        nodegroupsnets = []
        networks = self.get_networks()
        brnets = self.network_set.filter(mode="bridged")
        for net in networks:
            for group in net['group_list']:
                group_dict = {}
                if group[0] == nodegroup:
                    #Let's try to link with database saved networks.
                    # Get the description
                    try:
                        nd = Network.objects.get(
                            cluster=self, link=group[2]
                        ).description
                    except Network.DoesNotExist:
                        nd = net['name']
                    group_dict['defaultnet'] = False
                    # TODO: For the time get the default network from the
                    # database. Later on we can get it from the cluster.
                    if self.network_set.filter(
                        cluster_default=True, link=group[2]
                    ):
                        group_dict['defaultnet'] = True
                    group_dict['network'] = nd
                    group_dict['link'] = group[2]
                    group_dict['type'] = group[1]
                    group_dict['free_count'] = None
                    group_dict['reserved_count'] = None
                    if group_dict['type'] == 'routed':
                        group_dict['free_count'] = net['free_count']
                        group_dict['reserved_count'] = net['reserved_count']
                    nodegroupsnets.append(group_dict)
        for brnet in brnets:
            brnet_dict = {}
            brnet_dict['network'] = brnet.description
            brnet_dict['link'] = brnet.link
            brnet_dict['type'] = brnet.mode
            brnet_dict['free_count'] = None
            brnet_dict['reserved_count'] = None
            brnet_dict['defaultnet'] = False
            # TODO: For the time get the default network from the database.
            # Later on we can get it from the cluster.
            if self.network_set.filter(cluster_default=True, link=brnet.link):
                brnet_dict['defaultnet'] = True
            nodegroupsnets.append(brnet_dict)
        nodegroupsnets = sorted(nodegroupsnets, key=lambda k: k['network'])
        return nodegroupsnets

    def get_node_group_stack(self):
        groups = self.get_node_groups()
        group_stack = []
        for group in groups:
            group_dict = {}
            group_dict['name'] = group['name']
            group_dict['alloc_policy'] = group['alloc_policy']
            group_dict['networks'] = self.get_node_group_networks(
                group['name']
            )
            group_dict['nodes'] = group['node_list']
            group_dict['vgs'] = []
            group_tags = group['tags']
            for tag in group_tags:
                if tag.startswith("vg:"):
                    group_dict['vgs'].append(tag.replace('vg:', ''))
            group_stack.append(group_dict)
        return group_stack

    def get_cluster_instances(self):
        return self._client.GetInstances()

    def get_job_list(self):
        info = self._client.GetJobs(bulk=True)
        for i in info:
            i['cluster'] = self.slug
            if i.get('start_ts'):
                i['start_time'] = "%s" % (
                    datetime.fromtimestamp(
                        int(i['start_ts'][0])
                    ).strftime('%Y-%m-%d %H:%M:%S')
                )
            else:
                i['start_time'] = ''
            i['ops'][0]['OP_ID'] = i['ops'][0]['OP_ID'].replace(
                "OP_", ''
            ).replace("_", ' ').lower().capitalize()
        return info

    def get_job(self, job_id):
        return self._client.GetJobStatus(job_id)

    def get_cluster_instances_detail(self):
        return self._client.GetInstances(bulk=True)

    def get_node_group_info(self, nodegroup):
        info = cache.get("cluster:%s:nodegroup:%s" % (self.slug, nodegroup))
        if info is None:
            info = self._client.GetGroup(nodegroup)
            info['cluster'] = self.slug
            cache.set("cluster:%s:nodegroup:%s" % (
                self.slug,
                nodegroup
            ), info, 180)
        return info

    def get_node_info(self, node):
        info = cache.get("cluster:%s:node:%s" % (self.slug, node))
        if info is None:
            for info in self.get_cluster_nodes():
                if info['name'] == node:
                    cache.set("cluster:%s:node:%s" % (
                        self.slug,
                        node
                    ), info, 180)
                    return info
        return info

    def get_instance_info(self, instance):
        cache_key = self._instance_cache_key(instance)
        info = cache.get(cache_key)

        if info is None:
            try:
                info = parseQuery(
                    self._client.Query(
                        'instance',
                        [
                            'name',
                            'tags',
                            'pnode',
                            'snodes',
                            'disk.sizes',
                            'nic.modes',
                            'nic.ips',
                            'nic.links',
                            'status',
                            'admin_state',
                            'beparams',
                            'oper_state',
                            'hvparams',
                            'nic.macs',
                            'ctime',
                            'mtime',
                            'osparams',
                            'os',
                            'network_port',
                            'disk_template'
                        ],
                        ["|", ["=", "name", "%s" % instance]]
                    ))[0]
                cache.set(cache_key, info, 60)
            except GanetiApiError:
                info = None
        return info

    def setup_vnc_forwarding(self, instance):
        password = User.objects.make_random_password(length=8)
        info = self.get_instance_info(instance)

        port = info['network_port']
        node = info['pnode']
        node_ip = gethostbyname(node)
        res = vapclient.request_forwarding(0, node_ip, port, password)
        return (res["source_port"], password)

    def setup_novnc_forwarding(self, instance, sport=0, tls=False):
        password = User.objects.make_random_password(length=8)
        info = self.get_instance_info(instance)
        port = info['network_port']
        node = info['pnode']
        node_ip = gethostbyname(node)
        proxy_server = settings.NOVNC_PROXY.split(":")
        res = vapclient.request_novnc_forwarding(
            proxy_server,
            node_ip,
            port,
            password,
            sport=sport, tls=tls
        )
        return proxy_server[0], int(res), password

    def shutdown_instance(self, instance):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        job_id = self._client.ShutdownInstance(instance)
        self._lock_instance(instance, reason="shutting down", job_id=job_id)
        return job_id

    def reinstall_instance(self, instance, action):
        from ganeti.utils import get_os_details

        def map_ssh_user(user, group=None, path=None):
            if group is None:
                if user == "root":
                    group = ""   # snf-image will expand to root or wheel
                else:
                    group = user
            if path is None:
                if user == "root":
                    path = "/root/.ssh/authorized_keys"
                else:
                    path = "/home/%s/.ssh/authorized_keys" % user
            return user, group, path

        action_os = action.operating_system
        if action.operating_system == 'noop':
            action_os = "none"
        details = get_os_details(action_os)
        if details:
            cache_key = self._instance_cache_key(instance)
            cache.delete(cache_key)
            osparams = {}
            if "ssh_key_param" in details:
                fqdn = "https://" + Site.objects.get_current().domain
                try:
                    key_url = self.get_instance_or_404(
                        instance
                    ).application.get_ssh_keys_url(fqdn)
                    if details["ssh_key_param"]:
                        osparams[details["ssh_key_param"]] = key_url
                except:
                    pass
            if "ssh_key_users" in details and details["ssh_key_users"]:
                ssh_keys = None
                try:
                    ssh_keys = self.get_instance_or_404(
                        instance
                    ).application.applicant.sshpublickey_set.all()
                except:
                    pass
                if ssh_keys:
                    ssh_lines = [key.key_line() for key in ssh_keys]
                    ssh_base64 = base64.b64encode("".join(ssh_lines))
                    if "img_personality" not in osparams:
                        osparams["img_personality"] = []
                    for user in details["ssh_key_users"].split():
                        # user[:group[:/path/to/authorized_keys]]
                        owner, group, path = map_ssh_user(*user.split(":"))
                        osparams["img_personality"].append({
                            "path": path,
                            "contents": ssh_base64,
                            "owner": owner,
                            "group": group,
                            "mode": 0600,
                        })
            osparams.update(details.get('osparams'))
            for (key, val) in osparams.iteritems():
            # Encode nested JSON. See
            # <https://code.google.com/p/ganeti/issues/detail?id=835>
                if not isinstance(val, basestring):
                    osparams[key] = json.dumps(val)
            job_id = self._client.ReinstallInstance(
                instance,
                os=details.get('provider'),
                osparams=osparams
            )
            # manually change os params because client has a bug
            self._client.ModifyInstance(instance, osparams=osparams)
            self._lock_instance(instance, reason="reinstalling", job_id=job_id)
            return job_id
        else:
            return False

    def locked_nodes_from_nodegroup(self):
        '''
        gets all locked nodegroups and finds all their nodes.
        '''
        locked = cache.get('cluster:%s:lockednodegroups:nodes')
        if locked:
            return locked
        locked = []
        groups = self.get_node_groups()
        for group in groups:
            if 'locked' in group.get('tags'):
                locked.extend(group.get('node_list'))
        cache.set('cluster:%s:lockednodegroups:nodes' % self.slug, locked)
        return locked

    def destroy_instance(self, instance):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        job_id = self._client.DeleteInstance(instance)
        self._lock_instance(instance, reason="deleting", job_id=job_id)
        return job_id

    def rename_instance(self, instance, newname):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        job_id = self._client.RenameInstance(
            instance,
            newname,
            ip_check=False,
            name_check=False
        )
        self._lock_instance(instance, reason="renaming", job_id=job_id)
        return job_id

    def startup_instance(self, instance):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        job_id = self._client.StartupInstance(instance)
        self._lock_instance(instance, reason="starting up", job_id=job_id)
        return job_id

    def reboot_instance(self, instance):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        job_id = self._client.RebootInstance(instance)
        self._lock_instance(instance, reason="rebooting", job_id=job_id)
        instanceObj = self.get_instance_or_404(instance)
        if instanceObj.needsreboot:
            self.untag_instance(
                instance,
                ["%s:needsreboot" % GANETI_TAG_PREFIX]
            )
        return job_id

    def tag_instance(self, instance, tags):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        try:
            job_id = self._client.AddInstanceTags(instance, tags)
        except Exception as e:
            return e
        else:
            self._lock_instance(instance, reason="tagging", job_id=job_id)
            return job_id

    def untag_instance(self, instance, tags):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        job_id = self._client.DeleteInstanceTags(instance, tags)
        self._lock_instance(instance, reason="untagging", job_id=job_id)
        return job_id

    def migrate_instance(self, instance):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        job_id = self._client.MigrateInstance(instance)
        self._lock_instance(instance, reason="migrating", job_id=job_id)
        return job_id

    def create_instance(
        self,
        name=None,
        disk_template=None,
        disks=None,
        nics=None,
        os=None,
        memory=None,
        vcpus=None,
        tags=None,
        osparams=None, nodes=None
    ):
        beparams = {}
        if memory is not None:
            beparams["memory"] = memory
        if vcpus is not None:
            beparams["vcpus"] = vcpus

        if nics is None:
            nics = []

        if tags is None:
            tags = []

        if osparams is None:
            osparams = {}

        if disk_template is None:
            disk_template = self.default_disk_template

        nodesdict = {}
        if nodes is not None and len(nodes) > 0:
            nodesdict['pnode'] = nodes[0]
            if len(nodes) == 2:
                nodesdict['snode'] = nodes[1]
        job_id = self._client.CreateInstance(
            mode="create",
            name=name,
            os=os,
            disk_template=disk_template,
            disks=disks, nics=nics,
            start=False, ip_check=False,
            name_check=False,
            beparams=beparams,
            tags=tags, osparams=osparams,
            wait_for_sync=False, **nodesdict
        )
        self._lock_instance(name, reason=_("creating"), job_id=job_id)
        return job_id

    def get_job_status(self, job_id):
        return self._client.GetJobStatus(job_id)

    def get_default_network(self):
        try:
            return self.network_set.get(cluster_default=True)
        except Network.DoesNotExist:
            return None


class Network(models.Model):
    description = models.CharField(max_length=255)
    cluster = models.ForeignKey(Cluster)
    link = models.CharField(max_length=255)
    mode = models.CharField(max_length=64,
                            choices=(("bridged", "Bridged"),
                                     ("routed", "Routed")))
    cluster_default = models.BooleanField(default=False)
    ipv6_prefix = models.CharField(max_length=255, null=True, blank=True)
    groups = models.ManyToManyField(Group, blank=True)

    def __unicode__(self):
        return "%s (%s)" % (self.description, self.cluster.slug)

    def save(self, *args, **kwargs):
        # Ensure that only one cluster_default exists per cluster
        if self.cluster_default:
            try:
                other = Network.objects.get(cluster=self.cluster,
                                            cluster_default=True)
                if other != self:
                    other.cluster_default = False
                    other.save(*args, **kwargs)
            except Network.DoesNotExist:
                pass
        super(Network, self).save()


def preload_instance_data():
    networks = cache.get('networklist')
    if not networks:
        networks = Network.objects.select_related('cluster').all()
        networkdict = {}
        for network in networks:
            networkdict[network.link] = network.ipv6_prefix
        networks = networkdict
        cache.set('networklist', networks, 60)
    users = cache.get('userlist')
    if not users:
        users = User.objects.prefetch_related('groups').all()
        userdict = {}
        for user in users:
            userdict[user.username] = user
        users = userdict
        cache.set('userlist', users, 60)
    orgs = cache.get('orgslist')
    if not orgs:
        orgs = Organization.objects.all()
        orgsdict = {}
        for org in orgs:
            orgsdict[org.tag] = org
        orgs = orgsdict
        cache.set('orgslist', orgs, 60)
    groups = cache.get('groupslist')
    if not groups:
        groups = Group.objects.all()
        groupsdict = {}
        for group in groups:
            group.userset = group.user_set.all()
            groupsdict[group.name] = group
        groups = groupsdict
        cache.set('groupslist', groups, 60)
    instanceapps = cache.get('instaceapplist')
    if not instanceapps:
        instanceapps = InstanceApplication.objects.all()
        instappdict = {}
        for instapp in instanceapps:
            instappdict[str(instapp.pk)] = instapp
        instanceapps = instappdict
        cache.set('instaceapplist', instanceapps, 60)
    return users, orgs, groups, instanceapps, networks


class InstanceActionManager(models.Manager):

    def activate_request(self, activation_key):

        if SHA1_RE.search(activation_key):
            try:
                instreq = self.get(activation_key=activation_key)
            except self.model.DoesNotExist:
                return False
            if not instreq.activation_key_expired():
                instreq.activation_key = self.model.ACTIVATED
                instreq.save()
                return instreq
        return False

    def create_action(
        self,
        user,
        instance,
        cluster,
        action,
        action_value=None,
        operating_system=None
    ):
        # create a new action and expireany older actions
        for oldaction in self.filter(
            applicant=user,
            instance=instance,
            cluster=cluster,
            action=action
        ).exclude(activation_key='ALREADY_ACTIVATED'):
            action.expire_now()
        salt = hashlib.sha1(str(random.random())).hexdigest()[:5]
        activation_key = hashlib.sha1(salt + user.username).hexdigest()
        return self.create(
            applicant=user,
            instance=instance,
            cluster=cluster,
            action=action,
            action_value=action_value,
            activation_key=activation_key,
            operating_system=operating_system
        )


class InstanceAction(models.Model):
    applicant = models.ForeignKey(User)
    instance = models.CharField(max_length=255, blank=True)
    cluster = models.ForeignKey(Cluster, null=True, blank=True)
    action = models.IntegerField(choices=REQUEST_ACTIONS)
    action_value = models.CharField(max_length=255, null=True)
    activation_key = models.CharField(max_length=40)
    filed = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    operating_system = models.CharField(max_length=255, null=True)

    ACTIVATED = u"ALREADY_ACTIVATED"
    objects = InstanceActionManager()

    def activation_key_expired(self):
        if self.has_expired():
            if self.activation_key != self.ACTIVATED:
                self.activation_key = self.ACTIVATED
                self.save()
        return self.has_expired()
    activation_key_expired.boolean = True

    def has_expired(self):

        expiration_date = timedelta(days=settings.INSTANCE_ACTION_ACTIVE_DAYS)
        return self.activation_key == self.ACTIVATED or \
            (self.filed + expiration_date <= datetime.now())
    has_expired.boolean = True

    def expire_now(self):
        self.activation_key = self.ACTIVATED
        self.save()

    def send_activation_email(self, site):

        ctx_dict = {'activation_key': self.activation_key,
                    'expiration_days': settings.INSTANCE_ACTION_ACTIVE_DAYS,
                    'site': site}
        subject = "test"
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        message = render_to_string(
            'instance_actions/action_mail.txt',
            ctx_dict
        )
        self.user.email_user(subject, message, settings.DEFAULT_FROM_EMAIL)


def parseQuery(response):
    field_dict = {}
    data = response['data']
    fields = response['fields']
    for i, field in enumerate(fields):
        field_dict[i] = field['name']
    reslist = []
    for datai in data:
        res_dict = {}
        for fieldnum, result in enumerate(datai):
            res_dict[field_dict[fieldnum]] = result[1]
        reslist.append(res_dict)
    return reslist


def parseQuerysimple(response):
    data = response['data']
    reslist = []
    for datai in data:
        res_list = []
        for result in datai:
            res_list.append(result[1])
        reslist.append(res_list)
    return reslist


@receiver(pre_save, sender=Cluster)
def check_if_cluster_is_disabled(sender, **kwargs):
    instance = kwargs.get('instance')
    # if instance is disabled
    # we need to clear cache
    if instance.disabled:
        cache.delete("cluster:%s:instances" % instance.slug)

