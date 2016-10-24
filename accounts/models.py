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

import datetime

from apply.models import Organization

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.db import models
from django.db.models.signals import post_save

try:
    from django.utils.timezone import now as datetime_now
except ImportError:
    datetime_now = datetime.datetime.now


class UserProfile(models.Model):
    user = models.OneToOneField(User)
    first_login = models.BooleanField(default=True)
    force_logout_date = models.DateTimeField(null=True, blank=True)
    organization = models.ForeignKey(Organization, blank=True, null=True)
    telephone = models.CharField(max_length=13, blank=True, null=True)

    def force_logout(self):
        self.force_logout_date = datetime.datetime.now()
        self.save()

    def is_owner(self, instance):
        if self.user in instance.users:
            return True
        else:
            for group in self.user.groups.all():
                if group in instance.groups:
                    return True
        return False

    def __unicode__(self):
        return "%s profile" % self.user


# Signals
def create_user_profile(sender, instance, created, **kwargs):
    if created and not kwargs.get('raw', False):
        UserProfile.objects.create(user=instance)
post_save.connect(
    create_user_profile, sender=User, dispatch_uid='create_UserProfile')


def update_session_last_login(sender, user, request, **kwargs):
    if request:
        request.session['LAST_LOGIN_DATE'] = datetime.datetime.now()
user_logged_in.connect(update_session_last_login)
