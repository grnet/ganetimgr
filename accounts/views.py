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

from registration.backends.admin_approval.views import RegistrationView
from apply.models import Organization
from accounts.models import UserProfile


class CustomRegistrationView(RegistrationView):

    def register(self, form):

        new_user = super(RegistrationView, self).register(form)

        telephone = form.cleaned_data['phone']
        organization = form.cleaned_data['organization']

        profile, created = UserProfile.objects.get_or_create(user=new_user)
        try:
            organization = Organization.objects.get(title=organization)
            profile.organization = organization
        except Organization.DoesNotExist:
            profile.organization = None

        profile.telephone = telephone
        profile.user = new_user
        profile.save()

        new_user.first_name = form.cleaned_data['name']
        new_user.last_name = form.cleaned_data['surname']
        new_user.save()

        return new_user
