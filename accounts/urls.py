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

from django.conf.urls.defaults import patterns, url, include
from django.contrib.auth import views as auth_v

from accounts import views
from accounts.forms import RegistrationForm, PasswordResetFormPatched


urlpatterns = patterns(
    '',
    url(r'^activate/(?P<activation_key>\w+)/$', views.activate, name='activate_account'),
    url(r'^register/$', 'registration.views.register', {'backend': 'regbackends.ganetimgr.GanetimgrBackend', 'form_class': RegistrationForm}, name='registration.views.register'),
    url(r'^password/reset/$', auth_v.password_reset, {'password_reset_form': PasswordResetFormPatched}, name='password_reset'),
    (r'^', include('registration.backends.default.urls')),
)
