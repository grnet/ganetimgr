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

# proxies
from graphs import *
from instances import *
from jobs import *
from clusters import *
from discovery import *
from nodegroup import *

from ganeti.utils import prepare_tags
# TODO: Cleanup and separate to files
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.template.context import RequestContext
from django.template.loader import get_template
from django.shortcuts import render

from django.contrib.messages import constants as msgs

MESSAGE_TAGS = {
    msgs.ERROR: '',
    50: 'danger',
}


def news(request):
    return render(
        request,
        'news.html'
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
            return render(
                request,
                'tagging/itags.html',
                {
                    'form': form,
                    'users': users,
                    'instance': instance
                }
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
        return render(
            request,
            'tagging/itags.html',
            {
                'form': form,
                'users': users,
                'instance': instance
            }
        )


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


