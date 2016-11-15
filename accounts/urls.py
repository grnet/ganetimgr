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

from accounts.forms import PasswordResetFormPatched
from django.conf.urls import patterns, url, include
from django.contrib.auth import views as auth_views
from .views import CustomRegistrationView as RegistrationView


urlpatterns = patterns(
    '',
    url(
        r'^register/$',
        RegistrationView.as_view(),
        name='registration_register'
    ),
    url(
        r'^password/reset/$',
        auth_views.password_reset,
        {
            'password_reset_form':
            PasswordResetFormPatched,
        },
        name='password_reset'
    ),
    url(r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
	    auth_views.password_reset_confirm, name='password_reset_confirm'),
    url(r'^reset/done/$', auth_views.password_reset_complete, name='password_reset_complete'),
    url(
        r'^password_reset/done/$',
        auth_views.password_reset_done,
        name='password_reset_done'
    ),
    (r'^', include('registration.backends.admin_approval.urls')),
)
