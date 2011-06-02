import os
import sys
import urllib
import urllib2

from django.db import models
from django.core.cache import cache
from django.contrib.auth.models import User, Group
from simplejson import JSONEncoder, JSONDecoder
from time import sleep
from ganetimgr.util.portforwarder import forward_port
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from datetime import datetime
import vapclient
from socket import gethostbyname

from util.ganeti_client import GanetiRapiClient, GenericCurlConfig
from ganetimgr.settings import RAPI_CONNECT_TIMEOUT, RAPI_RESPONSE_TIMEOUT


dec = JSONDecoder()
enc = JSONEncoder()


class InstanceManager(object):
    def all(self):
        results = []
        for cluster in Cluster.objects.all():
            results.extend([Instance(cluster, info['name'], info)
                            for info in cluster.get_cluster_instances_detail()])
        return results

    def filter(self, **kwargs):
        if 'cluster' in kwargs:
            if isinstance(kwargs['cluster'], Cluster):
                cluster = kwargs['cluster']
            else:
                try:
                    cluster = Cluster.object.get(slug=kwargs['cluster'])
                except:
                    return []
            results = cluster.get_instances()
            del kwargs['cluster']
        else:
            results = self.all()

        for arg, val in kwargs.items():
            if arg == 'user':
                if not isinstance(val, User):
                    try:
                        val = User.objects.get(username__iexact=val)
                    except:
                        return []
                results = [result for result in results if val in result.users]
            elif arg == 'group':
                if not isinstance(val, Group):
                    try:
                        val = Group.objects.get(name__iexact=val)
                    except:
                        return []
                results = [result for result in results if val in result.groups]
            elif arg == 'name':
                results = [result for result in results if result.name == val]
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

    def __init__(self, cluster, name, info=None):
        self.cluster = cluster
        self.name = name
        self.users = []
        self.groups = []
        self._update(info)

    def _update(self, info=None):
        if not info:
            info = self.cluster.get_instance_info(self.name)
        for attr in info:
            self.__dict__[attr.replace(".", "_")] = info[attr]
        for tag in self.tags:
            if tag.startswith('group:'):
                group = tag.replace('group:','')
                try:
                    self.groups.append(Group.objects.get(name__iexact=group))
                except:
                    pass
            elif tag.startswith('user:'):
                user = tag.replace('user:','')
                try:
                    self.users.append(User.objects.get(username__iexact=user))
                except:
                    pass
        
        if getattr(self, 'ctime', None):
            self.ctime = datetime.fromtimestamp(self.ctime)
        if getattr(self, 'mtime', None):
            self.mtime = datetime.fromtimestamp(self.mtime)

    def set_params(self, **kwargs):
        self.cluster._client.ModifyInstance(self.name, **kwargs)

    def __repr__(self):
        return "<Instance: '%s'>" % self.name

    def __unicode__(self):
        return self.name

class Cluster(models.Model):
    hostname = models.CharField(max_length=128)
    slug = models.SlugField(max_length=50)
    port = models.PositiveIntegerField(default=5080)
    description = models.CharField(max_length=128, blank=True, null=True)
    username = models.CharField(max_length=64, blank=True, null=True)
    password = models.CharField(max_length=64, blank=True, null=True)

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        curl_config = GenericCurlConfig(connect_timeout=RAPI_CONNECT_TIMEOUT,
                                        timeout=RAPI_RESPONSE_TIMEOUT)
        self._client = GanetiRapiClient(host=self.hostname,
                                        username=self.username,
                                        password=self.password,
                                        curl_config_fn=curl_config)
        if self.id:
            self._update()

    def __unicode__(self):
        return self.hostname

    def _update(self):
        self._info = self.get_cluster_info()
        for attr in self._info:
            self.__dict__[attr] = self._info[attr]

    def _instance_cache_key(self, instance):
        return "cluster:%s:instance:%s" % (self.slug, instance)

    def get_instance(self, name):
        info = self.get_instance_info(name)
        return Instance(self, info["name"], info)

    def get_instances(self):
        instances = cache.get("cluster:%s:instances" % self.slug)
        if instances is None:
            instances = self._client.GetInstances(bulk=True)
            cache.set("cluster:%s:instances" % self.slug, instances, 30)

        return [Instance(self, info['name'], info) for info in instances]

    def get_user_instances(self, user):
        instances = self.get_instances()
        if user.is_superuser:
            return instances
        else:
            return [i for i in instances if (user in i.users or
                    user.groups.filter(id__in=[g.id for g in i.groups]))]

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

    def get_cluster_nodes(self):
        return self._client.GetNodes()

    def get_cluster_instances(self):
        return self._client.GetInstances()

    def get_cluster_instances_detail(self):
        return self._client.GetInstances(bulk=True)

    def get_node_info(self, node):
        return self._client.GetNode(node)

    def get_instance_info(self, instance):
        cache_key = self._instance_cache_key(instance)
        info = cache.get(cache_key)

        if info is None:
            info = self._client.GetInstance(instance)
            cache.set(cache_key, info, 3)

        return info
        
    def setup_vnc_forwarding(self, instance):
        password = User.objects.make_random_password(length=8)
        info = self.get_instance_info(instance)

        port = info['network_port']
        node = info['pnode']
        node_ip = gethostbyname(node)
        res = vapclient.request_forwarding(0, node_ip, port, password)
        return (res["source_port"], password)

    def shutdown_instance(self, instance):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        return self._client.ShutdownInstance(instance)

    def startup_instance(self, instance):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        return self._client.StartupInstance(instance)

    def reboot_instance(self, instance):
        cache_key = self._instance_cache_key(instance)
        cache.delete(cache_key)
        return self._client.RebootInstance(instance)
