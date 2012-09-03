#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2012 Greek Research and Technology Network (GRNET S.A.)
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND ISC DISCLAIMS ALL WARRANTIES WITH REGARD
# TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL ISC BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
# OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF
# USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
# TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.

from django.contrib import messages
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.core.exceptions import ObjectDoesNotExist

from ganetimgr.accounts.models import UserProfile

class UserMessageMiddleware(object):
    """
    Middleware to display various messages to the users.
    """

    def process_request(self, request):
        if not hasattr(request, "session"):
            return

        if request.user.is_authenticated():
            try:
                first_login = request.session["first_login"]
            except KeyError:
                try:
                    profile = request.user.get_profile()
                except ObjectDoesNotExist:
                    profile = UserProfile.objects.create(user=request.user)
                first_login = profile.first_login
                request.session["first_login"] = first_login

            if first_login:
                messages.add_message(request, messages.INFO,
                                     mark_safe(
                                     _("Welcome! Please take some time to"
                                       " update <a href=\"%s\">your profile</a>"
                                       " and upload your SSH keys.") %
                                       reverse("profile")))
                profile = request.user.get_profile()
                profile.first_login = False
                profile.save()
                request.session["first_login"] = False
