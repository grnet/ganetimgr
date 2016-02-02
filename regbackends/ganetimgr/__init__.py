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
from django.contrib.sites.models import RequestSite
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.core.mail import mail_managers

from registration import signals
from accounts.models import CustomRegistrationProfile
from registration.backends.default import DefaultBackend
from apply.models import Organization


class GanetimgrBackend(DefaultBackend):

    def register(self, request, **kwargs):
        username, email, password, firstname, lastname, organization, telephone = kwargs['username'], kwargs['email'], kwargs['password1'], kwargs['name'], kwargs['surname'], kwargs['organization'], kwargs['phone']
        if Site._meta.installed:
            site = Site.objects.get_current()
        else:
            site = RequestSite(request)
        new_user = CustomRegistrationProfile.objects.create_inactive_user(
            username, email,
            password, site, send_email=False)
        new_user.first_name = firstname
        new_user.last_name = lastname
        new_user.save()
        profile = new_user.get_profile()
        try:
            organization = Organization.objects.get(title=organization)
        except Organization.DoesNotExist:
            pass
        else:
            profile.organization = organization
        profile.telephone = telephone
        profile.save()
        subject = render_to_string(
            'registration/activation_email_subject.txt',
            {'site': site}
        )
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        registration_profile = CustomRegistrationProfile.objects.get(user=new_user)
        registration_profile.send_activation_email('test')
        registration_profile.send_admin_activation_email('test')
        # message = render_to_string('registration/activation_email.txt',
        #                            { 'activation_key': registration_profile.activation_key,
        #                              'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
        #                              'site': site,
        #                              'user': new_user })
        # mail_managers(subject, message)
        signals.user_registered.send(sender=self.__class__,
                                     user=new_user,
                                     request=request)
        return new_user
