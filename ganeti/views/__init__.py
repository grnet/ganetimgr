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
from ganeti.decorators import check_instance_auth

# proxies
from graphs import *
from instances import *
from jobs import *
from clusters import *
from discovery import *


# TODO: Cleanup and separate to files

from gevent.pool import Pool
from gevent.timeout import Timeout

from time import mktime
import datetime

from ipaddr import *
from django import forms
from django.core.cache import cache
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponse, HttpResponseServerError
)
from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext
from django.template.loader import get_template
from django.core.urlresolvers import reverse
from django.conf import settings
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext as _
from django.core.mail import send_mail
from django.template.defaultfilters import filesizeformat
from django.template.loader import render_to_string

from operator import itemgetter
from auditlog.utils import auditlog_entry

from auditlog.models import *

from ganeti.models import *
from ganeti.utils import prepare_clusternodes
from ganeti.forms import *


from util.client import GanetiApiError


import pprint
try:
    import json
except ImportError:
    import simplejson as json

from ganetimgr.settings import GANETI_TAG_PREFIX

from django.contrib.messages import constants as msgs

MESSAGE_TAGS = {
    msgs.ERROR: '',
    50: 'danger',
}


def cluster_overview(request):
    clusters = Cluster.objects.all()
    return render_to_response(
        'index.html',
        {'object_list': clusters},
        context_instance=RequestContext(request)
    )


def news(request):
    return render_to_response(
        'news.html',
        context_instance=RequestContext(request)
    )


@login_required
def clear_cache(request):
    if request.user.is_superuser or request.user.has_perm(
        'ganeti.view_instances'
    ):
        username = request.user.username
        keys_pattern = [
            "user:%s:index:*" % username,
            "cluster:*",
            "pendingapplications",
            "allclusternodes",
            "bad*",
            "len*",
            "%s:ajax*" % username,
            "locked_instances",
            "*list",
        ]
        for key in keys_pattern:
            cache_keys = cache.keys(pattern=key)
            if cache_keys:
                for cache_key in cache_keys:
                    if not cache_key.endswith('lock'):
                        cache.delete(cache_key)
        result = {'result': "Success"}
    else:
        result = {'error': "Violation"}
    return HttpResponse(json.dumps(result), mimetype='application/json')



@csrf_exempt
@login_required
def tagInstance(request, instance):
    instance = Instance.objects.get(name=instance)
    cluster = instance.cluster
    cache_key = "cluster:%s:instance:%s:user:%s" % (
        cluster.slug, instance.name,
        request.user.username
    )
    res = cache.get(cache_key)
    if res is None:
        res = False
        if (
            request.user.is_superuser or
            request.user in instance.users or
            set.intersection(
                set(request.user.groups.all()),
                set(instance.groups)
            )
        ):
            res = True
        cache.set(cache_key, res, 60)
    if not res:
        t = get_template("403.html")
        return HttpResponseForbidden(content=t.render(RequestContext(request)))

    if request.method == 'POST':
        users = []
        for user in instance.users:
            users.append("u_%s" % user.pk)
        groups = []
        for group in instance.groups:
            groups.append("g_%s" % group.pk)
        existingugtags = users + groups
        form = tagsForm(request.POST)
        if form.is_valid():
            newtags = form.cleaned_data['tags']
            newtags = newtags.split(',')
            common = list(set(existingugtags).intersection(set(newtags)))
            deltags = list(set(existingugtags) - set(common))

            if len(deltags) > 0:
                #we have tags to delete
                oldtodelete = prepare_tags(deltags)
                instance.cluster.untag_instance(instance.name, oldtodelete)
            newtagstoapply = prepare_tags(newtags)

            if len(newtagstoapply) > 0:
                instance.cluster.tag_instance(instance.name, newtagstoapply)

            res = {'result': 'success'}
            return HttpResponse(json.dumps(res), mimetype='application/json')
        else:
            return render_to_response(
                'tagging/itags.html',
                {
                    'form': form,
                    'users': users,
                    'instance': instance
                },
                context_instance=RequestContext(request)
            )
    elif request.method == 'GET':
        form = tagsForm()
        users = []
        for user in instance.users:
            userd = {}
            userd['text'] = user.username
            userd['id'] = "u_%s" % user.pk
            userd['type'] = "user"
            users.append(userd)
        for group in instance.groups:
            groupd = {}
            groupd['text'] = group.name
            groupd['id'] = "g_%s" % group.pk
            groupd['type'] = "group"
            users.append(groupd)
        return render_to_response(
            'tagging/itags.html',
            {
                'form': form,
                'users': users,
                'instance': instance
            },
            context_instance=RequestContext(request)
        )


def prepare_tags(taglist):
    tags = []
    for i in taglist:
        #User
        if i.startswith('u'):
            tags.append(
                "%s:user:%s" % (
                    GANETI_TAG_PREFIX, User.objects.get(
                        pk=i.replace('u_', '')
                    ).username
                )
            )
        #Group
        if i.startswith('g'):
            tags.append("%s:group:%s" % (
                GANETI_TAG_PREFIX,
                Group.objects.get(pk=i.replace('g_','')).name
            ))
    return list(set(tags))




@login_required
def get_user_groups(request):
    q_params = None
    try:
        q_params = request.GET['q']
    except:
        pass
    users = User.objects.filter(is_active=True)
    groups = Group.objects.all()
    if q_params:
        users = users.filter(username__icontains=q_params)
        groups = groups.filter(name__icontains=q_params)
    ret_list = []
    for user in users:
        userd = {}
        userd['text'] = user.username
        if (
            request.user.is_superuser or
            request.user.has_perm('ganeti.view_instances')
        ):
            userd['email'] = user.email
        userd['id'] = "u_%s" % user.pk
        userd['type'] = "user"
        ret_list.append(userd)
    for group in groups:
        groupd = {}
        groupd['text'] = group.name
        groupd['id'] = "g_%s" % group.pk
        groupd['type'] = "group"
        ret_list.append(groupd)
    action = ret_list
    return HttpResponse(json.dumps(action), mimetype='application/json')


