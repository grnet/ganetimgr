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

from django.conf import settings
import datetime


def seconds(request):
    remaining = False
    if (
        request.user.is_authenticated() and
        request.user.userprofile.force_logout_date and
        (
            'LAST_LOGIN_DATE' not in request.session or
            request.session['LAST_LOGIN_DATE'] < request.user.userprofile.force_logout_date
        )
    ):
        remaining = 2
    if not request.user.is_anonymous():
        if 'LAST_LOGIN_DATE' in request.session:
            last_login = request.session['LAST_LOGIN_DATE']
            now = datetime.datetime.now()
            if now > last_login:
                elapsed = (now - last_login).seconds
                remaining = settings.SESSION_COOKIE_AGE - elapsed
                if remaining < 0:
                    remaining = 2
            else:
                remaining = 2
    return {"session_remaining": remaining}
