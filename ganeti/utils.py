from gevent.pool import Pool
from django.core.urlresolvers import reverse
from django.db import close_connection

from ganeti.models import Instance, Cluster
from util.client import GanetiApiError


def get_instance_data(instance, cluster, node=None):
    instance.cpu_url = reverse(
        'graph',
        args=(cluster.slug, instance.name, 'cpu-ts')
    )
    instance.net_url = []
    for (nic_i, link) in enumerate(instance.nic_links):
        instance.net_url.append(
            reverse(
                'graph',
                args=(
                    cluster.slug,
                    instance.name,
                    'net-ts',
                    '/eth%s' % nic_i
                )
            )
        )
    return {
        'node': instance.pnode,
        'name': instance.name,
        'cluster': instance.cluster.slug,
        'cpu': instance.cpu_url,
        'network': instance.net_url,
    }


def get_nodes_with_graphs(cluster_slug, nodes=None):
    cluster = Cluster.objects.get(slug=cluster_slug)
    instances = Instance.objects.filter(cluster=cluster)
    response = []
    for i in instances:
        # if we have set a nodes, then we should check if the
        # instance belongs to them
        if not nodes:
            response.append(get_instance_data(i, cluster))
        else:
            for node in nodes:
                if i.pnode == node:
                    response.append(get_instance_data(i, cluster, node))
    return response


def prepare_clusternodes(cluster=None):
    if not cluster:
        clusters = Cluster.objects.all()
    else:
        clusters = Cluster.objects.filter(slug=cluster)
    p = Pool(15)
    nodes = []
    bad_clusters = []
    bad_nodes = []

    def _get_nodes(cluster):
        try:
            for node in cluster.get_cluster_nodes():
                nodes.append(node)
                if node['offline'] is True:
                    bad_nodes.append(node['name'])
        except (GanetiApiError, Exception):
            cluster._client = None
            bad_clusters.append(cluster)
        finally:
            close_connection()
    p.imap(_get_nodes, clusters)
    p.join()
    return nodes, bad_clusters, bad_nodes
