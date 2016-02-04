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

from accounts.models import CustomRegistrationProfile

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _


def validate_email(request, validation_key):
    # Normalize before trying anything with it.
    validation_key = validation_key.lower()
    account = CustomRegistrationProfile.objects.activate_user(validation_key)
    context = RequestContext(request)

    if account:
        email = render_to_string(
            "registration/validation_complete.txt",
            {
                "site": Site.objects.get_current(),
                "user": account
            }
        )
        send_mail(
            _("%s account email validated") % settings.EMAIL_SUBJECT_PREFIX,
            email,
            settings.SERVER_EMAIL,
            [account.email]
        )
    else:
        # Probably validation key has expired, delete user's account and
        # force him to register again
        pass

    return render_to_response(
        "registration/validation_complete.html",
        {
            'account': account,
            'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS
        },
        context_instance=context
    )


# TODO: should only be accessible from admins
def activate_account(request, activation_key):
    # Normalize before trying anything with it.
    activation_key = activation_key.lower()
    account = CustomRegistrationProfile.objects.admin_activate_user(activation_key)
    context = RequestContext(request)

    if account:
        # the user must be emailed, not the admin
        email = render_to_string(
            "registration/activation_complete.txt",
            {
                "site": Site.objects.get_current(),
                "user": account
            }
        )
        send_mail(
            _("%sUser account activated") % settings.EMAIL_SUBJECT_PREFIX,
            email,
            settings.SERVER_EMAIL,
            [account.email]
        )
    else:
        # Probably admin was lazy, account was deleted before he got to
        # activating it
        pass

    return render_to_response(
        "registration/activate.html",
        {
            'account': account,
            'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS
        },
        context_instance=context
    )
