from gevent.pool import Pool

from ganeti.models import Instance, Cluster
from util.client import GanetiApiError
from django.db import close_connection


def get_nodes_with_graphs(cluster_slug):
    cluster = Cluster.objects.get(slug=cluster_slug)
    instances = Instance.objects.filter(cluster=cluster)
    response = {}
    for i in instances:
        response.update({
            i.name: {
                'cluster': i.cluster.hostname,
            }
        })
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
