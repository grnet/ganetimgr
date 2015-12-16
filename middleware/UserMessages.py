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

from django.contrib import messages
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.core.exceptions import ObjectDoesNotExist

from accounts.models import UserProfile


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
                    profile = request.user.userprofile
                except ObjectDoesNotExist:
                    profile = UserProfile.objects.create(user=request.user)
                first_login = profile.first_login
                request.session["first_login"] = first_login

            if first_login:
                messages.add_message(
                    request,
                    messages.INFO,
                    mark_safe(
                        _(
                            "Welcome! Please take some time to"
                            " update <a href=\"%s\">your profile</a>"
                            " and upload your SSH keys."
                        ) % reverse("profile")
                    )
                )
                profile = request.user.userprofile
                profile.first_login = False
                profile.save()
                request.session["first_login"] = False
