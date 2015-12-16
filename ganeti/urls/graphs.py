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
    url(r'^(?P<cluster_slug>[^/]+)/(?P<instance>[^/]+)/(?P<graph_type>[^/]+)(/(?P<start>[\\:\w\d\s\.+-]+),(?P<end>[\\:\w\d\s\.+-]+))?(/(?P<nic>eth\d+))?$', views.graph, name='graph'),
    url(r'^all/$', views.cluster_nodes_graphs, name="cluster-get-nodes-graphs"),
    url(r'^(?P<cluster_slug>[^/]+)/instances/$', views.cluster_nodes_graphs, name="cluster-get-nodes-graphs"),
)
