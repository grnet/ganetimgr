from __future__ import unicode_literals
import datetime
import hashlib
import random
import re

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMultiAlternatives
from django.db import models, transaction
from django.template import RequestContext, TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now as datetime_now
from django.utils import six

from registration.users import UserModel, UserModelString
from registration import RegistrationProfile

SHA1_RE = re.compile('^[a-f0-9]{40}$')


class CustomRegistrationManager(models.Manager):
    def activate_user(self, activation_key, get_profile=False):
        if SHA1_RE.search(activation_key):
            try:
                profile = self.get(activation_key=activation_key)
            except self.model.DoesNotExist:
                # This is an actual activation failure as the activation
                # key does not exist. It is *not* the scenario where an
                # already activated User reuses an activation key.
                return False

            if profile.activated:
                # The User has already activated and is trying to activate
                # again. If the User is active, return the User. Else,
                # return False as the User has been deactivated by a site
                # administrator.
                if profile.user.is_active:
                    return profile.user
                else:
                    return False

            if not profile.activation_key_expired():
                user = profile.user
                # user.is_active = True
                profile.activated = True
                # if user is also admin_active, activate him
                if profile.admin_activated:
                    user.is_active = True

                with transaction.atomic():
                    user.save()
                    profile.save()

                if get_profile:
                    return profile
                else:
                    return user
        return False

    def admin_activate_user(self, activation_key, get_profile=False):
        if SHA1_RE.search(activation_key):
            try:
                profile = self.get(admin_activation_key=activation_key)
            except self.model.DoesNotExist:
                # This is an actual activation failure as the activation
                # key does not exist. It is *not* the scenario where an
                # already activated User reuses an activation key.
                return False

            if profile.admin_activated:
                # The User has already activated and is trying to activate
                # again. If the User is active, return the User. Else,
                # return False as the User has been deactivated by a site
                # administrator.
                if profile.user.is_active:
                    return profile.user
                else:
                    return False

            if not profile.admin_activation_key_expired():
                user = profile.user
                # user.is_active = True
                profile.admin_activated = True
                if profile.activated:
                    user.is_active = True

                with transaction.atomic():
                    user.save()
                    profile.save()

                if get_profile:
                    return profile
                else:
                    return user
        return False

    def create_inactive_user(self, site, new_user=None, send_email=True,
                             request=None, profile_info={}, **user_info):
        if new_user is None:
            password = user_info.pop('password')
            new_user = UserModel()(**user_info)
            new_user.set_password(password)
        new_user.is_active = False

        with transaction.atomic():
            new_user.save()
            registration_profile = self.create_profile(new_user, **profile_info)

        if send_email:
            registration_profile.send_activation_email(site, request)
            registration_profile.send_admin_activation_email(site, request)

        return new_user

    def create_profile(self, user, **profile_info):
        profile = self.model(user=user, **profile_info)

        if 'activation_key' not in profile_info:
            profile.create_new_activation_key(save=False)
            profile.create_new_admin_activation_key(save=False)

        profile.save()

        return profile

    def resend_activation_mail(self, email, site, request=None):
        try:
            profile = self.get(user__email=email)
        except ObjectDoesNotExist:
            return False

        if profile.activated or profile.activation_key_expired():
            return False

        profile.create_new_activation_key()
        profile.send_activation_email(site, request)

        return True

    def resend_admin_activation_mail(self, email, site, request=None):
        try:
            profile = self.get(user__email=email)
        except ObjectDoesNotExist:
            return False

        # should not be here probably, admin can activate him whenever...
        # (or not?)
        if profile.admin_activated or profile.admin_activation_key_expired():
            return False

        profile.create_new_admin_activation_key()
        profile.send_admin_activation_email(site, request)

        return True


@python_2_unicode_compatible
class CustomRegistrationProfile(RegistrationProfile):

    admin_activation_key = models.CharField(
        _('admin activation key'), max_length=40)

    admin_activated = models.BooleanField(default=False)

    both_actived = models.BooleanField(default=False)

    objects = CustomRegistrationManager()

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

    def admin_activation_key_expired(self):
        expiration_date = datetime.timedelta(
            days=settings.ACCOUNT_ACTIVATION_DAYS)
        return (self.admin_activated or
                (self.user.date_joined + expiration_date <= datetime_now()))
    admin_activation_key_expired.boolean = True

    def send_admin_activation_email(self, site, request=None):

        admin_activation_email_subject = getattr(
            settings,
            'ACTIVATION_EMAIL_SUBJECT',
            'registration/activation_email_subject.txt')
        admin_activation_email_body = getattr(
            settings,
            'ACTIVATION_EMAIL_BODY',
            'registration/activation_email.txt')
        admin_activation_email_html = getattr(
            settings, 'ACTIVATION_EMAIL_HTML',
            'registration/activation_email.html')

        ctx_dict = {}
        if request is not None:
            ctx_dict = RequestContext(request, ctx_dict)
        # update ctx_dict after RequestContext is created
        # because template context processors
        # can overwrite some of the values like user
        # if django.contrib.auth.context_processors.auth is used
        ctx_dict.update({
            'user': self.user,
            'activation_key': self.admin_activation_key,
            'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
            'site': site,
        })
        subject = (getattr(settings, 'REGISTRATION_EMAIL_SUBJECT_PREFIX', '') +
                   render_to_string(
                       admin_activation_email_subject, ctx_dict))
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        from_email = getattr(settings, 'REGISTRATION_DEFAULT_FROM_EMAIL',
                             settings.DEFAULT_FROM_EMAIL)
        message_txt = render_to_string(admin_activation_email_body,
                                       ctx_dict)

        email_message = EmailMultiAlternatives(subject, message_txt,
                                               from_email, ['sergiosaftsidis@gmail.com'])

        if getattr(settings, 'REGISTRATION_EMAIL_HTML', True):
            try:
                message_html = render_to_string(
                    admin_activation_email_html, ctx_dict)
            except TemplateDoesNotExist:
                pass
            else:
                email_message.attach_alternative(message_html, 'text/html')

        email_message.send()
