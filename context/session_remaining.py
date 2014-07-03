#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2012 Greek Research and Technology Network (GRNET S.A.)
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD
# TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
# OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF
# USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
# TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.

from django.core.cache import cache
from django.conf import settings 
import datetime


def seconds(request):
    remaining = False
    if request.user.is_authenticated() and request.user.get_profile().force_logout_date and \
           ( 'LAST_LOGIN_DATE' not in request.session or \
             request.session['LAST_LOGIN_DATE'] < request.user.get_profile().force_logout_date ):
        remaining = 2
    if not request.user.is_anonymous():
        if 'LAST_LOGIN_DATE' in request.session:
            last_login = request.session['LAST_LOGIN_DATE']
            now = datetime.datetime.now()
            if now > last_login:
                elapsed = (now-last_login).seconds
                remaining = settings.SESSION_COOKIE_AGE - elapsed
                if remaining < 0:
                    remaining = 2
            else:
                remaining = 2
    return {"session_remaining": remaining}
