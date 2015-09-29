import json
from django.http import HttpResponse
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import permission_required

from ganeti.models import Network, Cluster
from ganeti.utils import prepare_cluster_node_group_stack
from util.client import GanetiApiError


@permission_required("apply.change_instanceapplication")
def get_nodegroups_fromnet(request):
    network_id = request.GET.get('network_id', '')
    try:
        cluster = Network.objects.get(pk=network_id).cluster
    except Network.DoesNotExist:
        cluster = None
    if cluster:
        nodegroups = cluster.get_node_groups()
    nodegroups_list = []
    for g in nodegroups:
        nodeg_dict = {}
        nodeg_dict['name'] = g['name']
        nodegroups_list.append(nodeg_dict)
    return HttpResponse(json.dumps(nodegroups_list), mimetype='application/json')


@permission_required("apply.change_instanceapplication")
def get_cluster_node_group_stack(request):
    cluster_id = request.GET.get('cluster_id', '')
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
    except Cluster.DoesNotExist:
        return HttpResponse(
            json.dumps(
                {
                    'response': 'Error. Cluster does not exist!'
                }
            ),
            mimetype='application/json'
        )
    try:
        res = prepare_cluster_node_group_stack(cluster)
    except GanetiApiError as e:
        try:
            error = tuple(x for x in e.message[1:-1].split(","))[1]
        except:
            error = _('Could not connect to api')
        return HttpResponse(json.dumps({'failed': True, 'reason': error.replace('"', '')}), mimetype='application/json')
    return HttpResponse(json.dumps(res), mimetype='application/json')
