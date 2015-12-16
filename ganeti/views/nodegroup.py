import json
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.contrib.auth.decorators import permission_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from ganeti.models import Network, Cluster
from ganeti.utils import prepare_cluster_node_group_stack, format_ganeti_api_error
from util.client import GanetiApiError


@permission_required("apply.change_instanceapplication")
def get_nodegroups_fromnet(request):
    network_id = request.GET.get('network_id')
    if network_id:
        try:
            cluster = Network.objects.get(pk=network_id).cluster
        except Network.DoesNotExist:
            raise Http404
    else:
        return HttpResponseBadRequest()
    nodegroups = cluster.get_node_groups()
    nodegroups_list = []
    for g in nodegroups:
        nodeg_dict = {}
        nodeg_dict['name'] = g['name']
        nodegroups_list.append(nodeg_dict)
    return HttpResponse(json.dumps(nodegroups_list), content_type='application/json')


@permission_required("apply.change_instanceapplication")
def get_cluster_node_group_stack(request):
    res = ''
    error = None
    cluster_id = request.GET.get('cluster_id', None)
    if cluster_id:
        cluster = get_object_or_404(Cluster, pk=cluster_id)
    else:
        return HttpResponseBadRequest()

    try:
        res = prepare_cluster_node_group_stack(cluster)
    except GanetiApiError as e:
        error = format_ganeti_api_error(e)
    except Exception as e:
        error = e
    if error:
        messages.add_message(request, messages.ERROR, error)
    return HttpResponse(json.dumps(res), content_type='application/json')
