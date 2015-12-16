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

from django.conf.urls import patterns, url

from ganeti import views

urlpatterns = patterns(
    '',
    url(r'^list/$', views.list_user_instances, name='instances-list'),
    url(r'^tags/(?P<instance>[^/]+)?$', views.tagInstance, name="instance-tags"),
    url(r'^json/$', views.user_index_json, name="user-instances-json"),
    url(r'^stats/json/$', views.user_sum_stats, name="user-stats-json"),
    url(r'^lock/(?P<instance>[^/]+)?$', views.lock, name="lock"),
    url(r'^isolate/(?P<instance>[^/]+)?$', views.isolate, name="isolate"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/poll/?$', views.poll, name="instance-poll"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/vnc/?$', views.vnc, name="instance-vnc"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/novnc/?$', views.novnc, name="instance-novnc"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/novnc-proxy/?$', views.novnc_proxy, name="instance-novnc-proxy"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/shutdown/?$', views.shutdown, name="instance-shutdown"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/startup/?$', views.startup, name="instance-startup"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/reboot/?$', views.reboot, name="instance-reboot"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/reinstalldestroy/(?P<action_id>\d+)/(?P<action_value>[^/]+)?$', views.reinstalldestroy, name="instance-reinstall-destroy"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/rename/(?P<action_id>\d+)(/(?P<action_value>[^/]+))?$', views.rename_instance, name="instance-rename"),
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/?', views.instance, name="instance-detail"),
)
