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

from django.conf import settings
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.template.context import RequestContext
from django.http import HttpResponseRedirect, HttpResponse
from notifications.forms import *
from ganeti.models import *
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from django.core.mail.message import EmailMessage

from gevent.pool import Pool

from util.client import GanetiApiError
from django.db import close_connection
from notifications.utils import get_mails, send_emails


@csrf_exempt
@login_required
def notify(request, instance=None):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        if instance:
            instance = Instance.objects.get(name=instance)
        users = []
        if request.method == 'POST':
            form = MessageForm(request.POST)
            if form.is_valid():
                rl = form.cleaned_data['recipient_list']
                rlist = rl.split(',')
                mail_list = get_mails(rlist)
                email = form.cleaned_data['message']
                if len(mail_list) > 0:
                    send_emails(
                        "%s%s" % (
                            settings.EMAIL_SUBJECT_PREFIX,
                            form.cleaned_data['subject']
                        ),
                        email,
                        mail_list,
                    )
                if request.is_ajax():
                    ret = {'result': 'success'}
                    return HttpResponse(
                        json.dumps(ret),
                        mimetype='application/json'
                    )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Mail sent to %s" % ','.join(mail_list)
                )
                return HttpResponseRedirect(reverse('user-instances'))
        else:
            if instance:
                for user in instance.users:
                    userd = {}
                    userd['text'] = user.username
                    userd['id'] = "u_%s" % user.pk
                    userd['type'] = "user"
                    users.append(userd)
                for group in instance.groups:
                    groupd = {}
                    groupd['text'] = group.name
                    groupd['id'] = "u_%s" % group.pk
                    groupd['type'] = "group"
                    users.append(groupd)
            form = MessageForm()
        if request.is_ajax():
            return render_to_response(
                'notifications/create_ajax.html',
                {
                    'form': form, 'users': users, 'ajax': 'true',
                },
                context_instance=RequestContext(request)
            )
        return render_to_response(
            'notifications/create.html',
            {
                'form': form,
                'users': users
            },
            context_instance=RequestContext(request)
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@login_required
def get_user_group_list(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        q_params = request.GET.get('q')
        type_of_search = request.GET.get('type')
        p = Pool(20)
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
        if q_params and type_of_search:
            ret_list = []
            if type_of_search == 'cluster':
                clusters = Cluster.objects.filter(slug__icontains=q_params)
                for cluster in clusters:
                    cld = {}
                    cld['text'] = cluster.slug
                    cld['id'] = "c_%s" % cluster.pk
                    cld['type'] = "cluster"
                    ret_list.append(cld)
            elif type_of_search == 'users':
                users = User.objects.filter(is_active=True, username__icontains=q_params)
                for user in users:
                    userd = {}
                    userd['text'] = user.username
                    userd['email'] = user.email
                    userd['id'] = "u_%s" % user.pk
                    userd['type'] = "user"
                    ret_list.append(userd)
            elif type_of_search == 'groups':
                groups = Group.objects.filter(name__icontains=q_params)
                for group in groups:
                    groupd = {}
                    groupd['text'] = group.name
                    groupd['id'] = "g_%s" % group.pk
                    groupd['type'] = "group"
                    ret_list.append(groupd)
            elif type_of_search == 'instances':
                instances = []
                instances = Instance.objects.filter(name__icontains=q_params)
                for instance in instances:
                    instd = {}
                    instd['text'] = instance.name
                    instd['id'] = "i_%s" % instance.name
                    instd['type'] = "vm"
                    ret_list.append(instd)
            elif type_of_search == 'nodes':
                for cluster in Cluster.objects.all():
                    for node in cluster.get_cluster_nodes():
                        if q_params in node.get('name'):
                            noded = {
                                'text': '%s - %s' % (cluster, node.get('name')),
                                'id': 'n_%s_c_%s' % (node.get('name'), cluster.id),
                                'type': 'node'
                            }
                            ret_list.append(noded)
            elif type_of_search == 'nodegroups':
                nodegroups = []
                for cluster in Cluster.objects.all():
                    nodegroups.append({cluster: cluster.get_node_groups()})
                for nodegroup_list in nodegroups:
                    for cluster, nodegroup in nodegroup_list.items():
                        for ng in nodegroup:
                            if q_params in ng.get('name'):
                                nodegroupsd = {
                                    'text': '%s - %s' % (cluster, ng.get('name')),
                                    'id': 'ng_%s_c_%s' % (ng.get('name'), cluster.id),
                                    'type': 'nodegroup'
                                }
                                ret_list.append(nodegroupsd)

        action = ret_list
        return HttpResponse(json.dumps(action), mimetype='application/json')
    else:
        action = {
            'error': "Permissions' violation. This action has been logged and our admins will be notified about it"
        }
        return HttpResponse(json.dumps(action), mimetype='application/json')




