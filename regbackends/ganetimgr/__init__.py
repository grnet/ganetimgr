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

from apply.models import Organization

from django.contrib.sites.models import RequestSite
from django.contrib.sites.models import Site
from registration import signals
from registration.backends.default import DefaultBackend


class GanetimgrBackend(DefaultBackend):

    def register(self, request, **kwargs):

        username = kwargs['username']
        email = kwargs['email']
        password = kwargs['password1']
        firstname = kwargs['name']
        lastname = kwargs['surname']
        organization = kwargs['organization']
        telephone = kwargs['phone']

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
        profile = new_user.userprofile
        try:
            organization = Organization.objects.get(title=organization)
        except Organization.DoesNotExist:
            pass
        else:
            profile.organization = organization
        profile.telephone = telephone
        profile.save()

        # Custom registration profile is being used to allow 2-step validation:
        # 1) user validates his email address
        # 2) admin activates user's account

        registration_profile = CustomRegistrationProfile.objects.get(
            user=new_user)

        registration_profile.send_validation_email(site)

        signals.user_registered.send(sender=self.__class__,
                                     user=new_user,
                                     request=request)
        return new_user
