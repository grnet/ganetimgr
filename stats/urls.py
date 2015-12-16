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
from stats import views

urlpatterns = patterns(
    '',
    url(r'^applications/?', views.stats_ajax_applications, name="stats_ajax_apps"),
    url(r'^instances/?', views.stats_ajax_instances, name="stats_ajax_instances"),
    url(r'^vms_cluster/(?P<cluster_slug>[^/]+)/?', views.stats_ajax_vms_per_cluster, name="stats_ajax_vms_pc"),
    url(r'^$', views.stats, name="stats"),
)
