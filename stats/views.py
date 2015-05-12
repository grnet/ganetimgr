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
from time import mktime
import json
from gevent.timeout import Timeout
from gevent.pool import Pool
from operator import itemgetter

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.core.cache import cache
from django.db import close_connection
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.core.urlresolvers import reverse

from ganeti.models import Cluster
from apply.models import InstanceApplication, Organization

from util.client import GanetiApiError


def instance_owners(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        p = Pool(20)
        instancesall = []
        bad_clusters = []

        def _get_instances(cluster):
            try:
                instancesall.extend(cluster.get_user_instances(request.user))
            except (GanetiApiError, Exception):
                bad_clusters.append(cluster)
        if not request.user.is_anonymous():
            p.map(_get_instances, Cluster.objects.all())
        instances = [i for i in instancesall if i.users]

        def cmp_users(x, y):
            return cmp(",".join([u.username for u in x.users]),
                       ",".join([u.username for u in y.users]))
        instances.sort(cmp=cmp_users)

        return render(
            request,
            "instance_owners.html",
            {"instances": instances},
        )
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@login_required
def stats_ajax_applications(request):
    username = request.user.username
    app_list = cache.get('%s:ajaxapplist' % username)
    if app_list is None:
        applications = InstanceApplication.objects.all().order_by('filed')
        if not (
            request.user.is_superuser or
            request.user.has_perm('ganeti.view_instances')
        ):
            applications = applications.filter(applicant=request.user)
        app_list = []
        i = 0
        for app in applications:
            appd = {}
            appd['instance'] = app.hostname
            i = i + 1
            appd['count'] = i
            appd['user'] = app.applicant.username
            appd['time'] = (1000 * mktime(app.filed.timetuple()))
            app_list.append(appd)
        cache.set('%s:ajaxapplist' % username, app_list, 90)
    return HttpResponse(json.dumps(app_list), content_type='application/json')


@login_required
def stats_ajax_instances(request):
    username = request.user.username
    cluster_list = cache.get('%s:ajaxinstances' % username)
    if cluster_list is None:
        # get only enabled clusters
        clusters = Cluster.objects.filter(disabled=False)
        i = 0
        cluster_list = []
        for cluster in clusters:
            cinstances = []
            i = 0
            cluster_dict = {}
            if (
                request.user.is_superuser or
                request.user.has_perm('ganeti.view_instances')
            ):
                cluster_dict['name'] = cluster.slug
            else:
                cluster_dict['name'] = cluster.description
            cluster_dict['instances'] = []
            try:
                cinstances.extend(cluster.get_user_instances(request.user))
            except (GanetiApiError, Timeout):
                cinstances = []
            for instance in cinstances:
                inst_dict = {}
                inst_dict['time'] = (1000 * mktime(instance.ctime.timetuple()))
                inst_dict['name'] = instance.name
                cluster_dict['instances'].append(inst_dict)
            cluster_dict['instances'] = sorted(
                cluster_dict['instances'],
                key=itemgetter('time')
            )
            for item in cluster_dict['instances']:
                i = i + 1
                item['count'] = i
            if len(cinstances) > 0:
                cluster_list.append(cluster_dict)
        cache.set('%s:ajaxinstances' % username, cluster_list, 90)
    return HttpResponse(json.dumps(cluster_list), content_type='application/json')


@login_required
def stats_ajax_vms_per_cluster(request, cluster_slug):
    cluster_dict = cache.get('%s:ajaxvmscluster:%s' % (
        request.user.username,
        cluster_slug)
    )
    if cluster_dict is None:
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        cluster_dict = {}
        cluster_dict['name'] = cluster.slug
        cluster_dict['instances'] = {'up': 0, 'down': 0}
        cinstances = []
        try:
            cinstances.extend(cluster.get_user_instances(request.user))
        except (GanetiApiError, Timeout):
            return HttpResponse(json.dumps([]), content_type='application/json')
        for instance in cinstances:
            if instance.admin_state:
                cluster_dict['instances']['up'] = cluster_dict['instances']['up'] + 1
            else:
                cluster_dict['instances']['down'] = cluster_dict['instances']['down'] + 1
        cache.set(
            '%s:ajaxvmscluster:%s' % (
                request.user.username,
                cluster_slug
            ),
            cluster_dict,
            90
        )
    return HttpResponse(json.dumps(cluster_dict), content_type='application/json')


@login_required
def stats(request):
    # get only enabled clusters
    clusters = Cluster.objects.filter(disabled=False)
    exclude_pks = []
    if (request.user.is_superuser or request.user.has_perm('ganeti.view_instances')):
        instances = cache.get('leninstances')
        if instances is None:
            p = Pool(20)
            instances = []

            def _get_instances(cluster):
                try:
                    instances.extend(cluster.get_user_instances(request.user))
                except (GanetiApiError, Exception):
                    exclude_pks.append(cluster.pk)
                finally:
                    close_connection()
            if not request.user.is_anonymous():
                p.map(_get_instances, clusters)
            instances = len(instances)
            cache.set('leninstances', instances, 90)
        users = cache.get('lenusers')
        if users is None:
            users = len(User.objects.all())
            cache.set('lenusers', users, 90)
        groups = cache.get('lengroups')
        if groups is None:
            groups = len(Group.objects.all())
            cache.set('lengroups', groups, 90)
        instance_apps = cache.get('leninstapps')
        if instance_apps is None:
            instance_apps = len(InstanceApplication.objects.all())
            cache.set('leninstapps', instance_apps, 90)
        orgs = cache.get('lenorgs')
        if orgs is None:
            orgs = len(Organization.objects.all())
            cache.set('lenorgs', orgs, 90)
        if exclude_pks:
            clusters = clusters.exclude(pk__in=exclude_pks)
        return render(
            request,
            'stats/statistics.html',
            {
                'clusters': clusters,
                'instances': instances,
                'users': users,
                'groups': groups,
                'instance_apps': instance_apps,
                'orgs': orgs
            }
        )
    else:
        return render(
            request,
            'stats/statistics.html',
            {'clusters': clusters}
        )
