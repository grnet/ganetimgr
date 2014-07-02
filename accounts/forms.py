#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2012 Greek Research and Technology Network (GRNET S.A.)
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD
# TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
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
from registration.forms import RegistrationFormUniqueEmail as _RegistrationForm
from django.contrib.auth.forms import PasswordResetForm 

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

class PasswordResetFormPatched(PasswordResetForm):
    error_messages = {
        'unknown': _("That e-mail address doesn't have an associated "
                     "user account or the account has not been activated yet. Are you sure you've registered?"),
        'unusable': _("The user account associated with this e-mail "
                      "address cannot reset the password."),
    }
