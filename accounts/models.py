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
import hashlib
import random
import re

from apply.models import Organization

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.db import transaction
from django.db.models.signals import post_save
from django.template import RequestContext, TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils import six

from django.utils.translation import ugettext_lazy as _

try:
    from django.utils.timezone import now as datetime_now
except ImportError:
    datetime_now = datetime.datetime.now

from registration.models import RegistrationProfile

if Site._meta.installed:
    site = Site.objects.get_current()
else:
    site = ''


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
post_save.connect(create_user_profile, sender=User, dispatch_uid='create_UserProfile')


def update_session_last_login(sender, user, request, **kwargs):
    if request:
        request.session['LAST_LOGIN_DATE'] = datetime.datetime.now()
user_logged_in.connect(update_session_last_login)


SHA1_RE = re.compile('^[a-f0-9]{40}$')


class CustomRegistrationManager(models.Manager):

    def activate_user(self, activation_key):
        # Make sure the key we're trying conforms to the pattern of a
        # SHA1 hash; if it doesn't, no point trying to look it up in
        # the database.
        if SHA1_RE.search(activation_key):
            try:
                profile = self.get(activation_key=activation_key)
            except self.model.DoesNotExist:
                return False
            if not profile.activation_key_expired():
                user = profile.user
                profile.activated = True
                user.save()
                profile.save()

                # an e-mail is sent to the site managers to activate the
                # user's account
                profile.send_admin_activation_email(site)

                return user
        return False

    def admin_activate_user(self, activation_key, get_profile=False):
        if SHA1_RE.search(activation_key):
            try:
                profile = self.get(admin_activation_key=activation_key)
            except self.model.DoesNotExist:
                return False
            # do not check for expired admin keys, admin can activate the
            # account whenever
            user = profile.user
            profile.admin_activated = True
            if profile.activated:
                user.is_active = True
            user.save()
            profile.save()
            return user
        return False

    def create_inactive_user(self, username, email, password,
                             site, send_email=True):
        new_user = User.objects.create_user(username, email, password)
        new_user.is_active = False
        new_user.save()

        registration_profile = self.create_profile(new_user)

        if send_email:
            registration_profile.send_activation_email(site)

        return new_user
    create_inactive_user = transaction.commit_on_success(create_inactive_user)

    def create_profile(self, user, **profile_info):
        profile = self.model(user=user, **profile_info)

        if 'activation_key' not in profile_info:
            profile.create_new_activation_key(save=False)
            profile.create_new_admin_activation_key(save=False)

        profile.save()

        return profile

    def delete_expired_users(self):
        for profile in self.all():
            try:
                if profile.activation_key_expired():
                    user = profile.user
                    if not user.is_active:
                        user.delete()
                        profile.delete()
            except User.DoesNotExist:
                profile.delete()


class CustomRegistrationProfile(RegistrationProfile):

    admin_activation_key = models.CharField(
        _('admin activation key'), max_length=40)
    admin_activated = models.BooleanField(default=False)
    activated = models.BooleanField(default=False)

    objects = CustomRegistrationManager()

    class Meta:
        verbose_name = _('registration profile')
        verbose_name_plural = _('registration profiles')

    def __unicode__(self):
        return u"Registration information for %s" % self.user

    def create_new_admin_activation_key(self, save=True):
        salt = hashlib.sha1(six.text_type(random.random())
                            .encode('ascii')).hexdigest()[:5]
        salt = salt.encode('ascii')
        user_pk = str(self.user.pk)
        if isinstance(user_pk, six.text_type):
            user_pk = user_pk.encode('utf-8')
        self.admin_activation_key = hashlib.sha1(salt + user_pk).hexdigest()
        if save:
            self.save()
        return self.admin_activation_key

    def create_new_activation_key(self, save=True):
        salt = hashlib.sha1(six.text_type(random.random())
                            .encode('ascii')).hexdigest()[:5]
        salt = salt.encode('ascii')
        user_pk = str(self.user.pk)
        if isinstance(user_pk, six.text_type):
            user_pk = user_pk.encode('utf-8')
        self.activation_key = hashlib.sha1(salt + user_pk).hexdigest()
        if save:
            self.save()
        return self.activation_key

    # Probably useless, if seen again delete it

    # def admin_activation_key_expired(self):
    #     expiration_date = datetime.timedelta(
    #         days=settings.ACCOUNT_ACTIVATION_DAYS)
    #     return (self.admin_activated or
    #             (self.user.date_joined + expiration_date <= datetime_now()))
    # admin_activation_key_expired.boolean = True

    def send_activation_email(self, site):
        subject = render_to_string(
            'registration/activation_email_subject.txt',
            {'site': site}
        )
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())

        message = render_to_string(
            'registration/validation_email.txt',
            {
                'validation_key': self.activation_key,
                'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
                'site': site,
                'user': self.user
            }
        )

        email_message = EmailMultiAlternatives(
            subject, message,
            settings.DEFAULT_FROM_EMAIL, [self.user.email])

        email_message.send()

    def send_admin_activation_email(self, site):

        subject = render_to_string(
            'registration/activation_email_subject.txt',
            {'site': site}
        )
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())

        message = render_to_string(
            'registration/activation_email.txt',
            {
                'activation_key': self.admin_activation_key,
                'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
                'site': site,
                'user': self.user
            }
        )

        # test multiple managers
        email_message = EmailMultiAlternatives(
            subject, message,
            settings.DEFAULT_FROM_EMAIL,
            [addr[1] for addr in settings.MANAGERS])

        email_message.send()
