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

from django.conf.urls.defaults import patterns, url
from ganeti import views

urlpatterns = patterns(
    '',
    # this view lives in jobs.py
    url(r'^jobdetails/?$', views.job_details, name="jobdets-popup"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/poll/?$', views.poll, name="instance-poll"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/vnc/?$', views.vnc, name="instance-vnc"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/novnc/?$', views.novnc, name="instance-novnc"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/novnc-proxy/?$', views.novnc_proxy, name="instance-novnc-proxy"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/shutdown/?$', views.shutdown, name="instance-shutdown"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/startup/?$', views.startup, name="instance-startup"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/reboot/?$', views.reboot, name="instance-reboot"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/reinstalldestroy/(?P<action_id>\d+)/(?P<action_value>[^/]+)?$', views.reinstalldestroy, name="instance-reinstall-destroy"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/rename/(?P<action_id>\d+)(/(?P<action_value>[^/]+))?$', views.rename_instance, name="instance-rename"),
    url(r'^(?P<cluster_slug>\w+)/(?P<instance>[^/]+)/?', views.instance, name="instance-detail"),
    url(r'^popup/?', views.instance_popup, name="instance-popup"),
    url(r'^nodes/?', views.get_clusternodes, name="cluster-nodes"),
    url(r'^jnodes/(?P<cluster>[^/]+)/$', views.clusternodes_json, name="cluster-nodes-json"),
    url(r'^jnodes/$', views.clusternodes_json, name="cluster-nodes-json"),
)
