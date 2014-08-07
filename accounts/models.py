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


from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in

from datetime import datetime

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    first_login = models.BooleanField(default=True)
    force_logout_date = models.DateTimeField(null=True, blank=True)

    def force_logout(self):
        self.force_logout_date = datetime.now()
        self.save()
    
    def __unicode__(self):
        return "%s profile" %self.user

def create_user_profile(sender, instance, created, **kwargs):
    if created and not kwargs.get('raw', False):
        UserProfile.objects.create(user=instance)

post_save.connect(create_user_profile, sender=User, dispatch_uid='create_UserProfile')

def update_session_last_login(sender, user, request, **kwargs):
    if request:
        request.session['LAST_LOGIN_DATE'] = datetime.now()
user_logged_in.connect(update_session_last_login)