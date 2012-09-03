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

from django import forms
from django.conf import settings
from django.core.mail import mail_managers
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_unicode

from recaptcha.client import captcha
from registration.models import RegistrationProfile
from registration.forms import RegistrationForm as _RegistrationForm


# Add the new google service URLs, as the old ones to recaptcha.net are
# redirects and break HTTPs due to the certificate belonging to www.google.com
captcha.API_SSL_SERVER = "https://www.google.com/recaptcha/api"
captcha.API_SERVER = "http://www.google.com/recaptcha/api"

class ReCaptcha(forms.widgets.Widget):
    recaptcha_challenge_name = 'recaptcha_challenge_field'
    recaptcha_response_name = 'recaptcha_response_field'

    def render(self, name, value, attrs=None):
        return mark_safe(u'%s' % captcha.displayhtml(settings.RECAPTCHA_PUBLIC_KEY,
						     use_ssl=settings.RECAPTCHA_USE_SSL))

    def value_from_datadict(self, data, files, name):
        return [data.get(self.recaptcha_challenge_name, None),
            data.get(self.recaptcha_response_name, None)]


class ReCaptchaField(forms.CharField):
    default_error_messages = {
        'captcha_invalid': _(u'Invalid captcha')
    }

    def __init__(self, *args, **kwargs):
        self.widget = ReCaptcha
        self.required = True
        super(ReCaptchaField, self).__init__(*args, **kwargs)

    def clean(self, values):
        super(ReCaptchaField, self).clean(values[1])
        recaptcha_challenge_value = smart_unicode(values[0])
        recaptcha_response_value = smart_unicode(values[1])
        check_captcha = captcha.submit(recaptcha_challenge_value,
            recaptcha_response_value, settings.RECAPTCHA_PRIVATE_KEY, {})
        if not check_captcha.is_valid:
            raise forms.util.ValidationError(self.error_messages['captcha_invalid'])
        return values[0]


class RegistrationForm(_RegistrationForm):
    name = forms.CharField()
    surname = forms.CharField()
    recaptcha = ReCaptchaField(label=_("Verify"), required=False)

    def save(self, profile_callback=None):
        """
        Override registration.forms.RegistrationForm's save() method to save
        the user's full name as well.

        See the original method's documentation about profile_callback.
        """

        # Sadly, we can't call super().save(), since we want to keep the
        # application from sending an e-mail
        user = RegistrationProfile.objects.create_inactive_user(username=self.cleaned_data['username'],
                                                                password=self.cleaned_data['password1'],
                                                                email=self.cleaned_data['email'],
                                                                send_email=False,
                                                                profile_callback=profile_callback)
        user.first_name = self.cleaned_data["name"]
        user.last_name = self.cleaned_data["surname"]
        user.save()

        # This is partly the same as registration's original code, but we want
        # to send the notification to the managers instead.
        current_site = Site.objects.get_current()
        subject = render_to_string('registration/activation_email_subject.txt',
                                   { 'site': current_site })
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())

        registration_profile = RegistrationProfile.objects.get(user=user)
        message = render_to_string('registration/activation_email.txt',
                                   { 'activation_key': registration_profile.activation_key,
                                     'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
                                     'site': current_site,
                                     'user': user })

        mail_managers(subject, message)
        return user
