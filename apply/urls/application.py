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
from apply import views

urlpatterns = patterns(
    '',
    url(r'^apply/?$', views.apply, name="apply"),
    url(r'^list/?$', views.application_list, name="application-list"),
    # this url is accessible only if a superuser tries to create
    # an instance by himself
    url(r'^save/', views.review_application, name="application-save"),
    url(r'^(?P<application_id>\d+)/review/$', views.review_application, name="application-review"),
    url(r'^(?P<application_id>\d+)/(?P<cookie>\w+)/ssh_keys', views.instance_ssh_keys, name="instance-ssh-keys"),
)
