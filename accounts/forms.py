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
from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_unicode

from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordResetForm
from recaptcha.client import captcha
from registration.forms import RegistrationFormUniqueEmail as _RegistrationForm
from apply.models import Organization

# Add the new google service URLs, as the old ones to recaptcha.net are
# redirects and break HTTPs due to the certificate belonging to www.google.com
captcha.API_SSL_SERVER = "https://www.google.com/recaptcha/api"
captcha.API_SERVER = "http://www.google.com/recaptcha/api"


class ReCaptcha(forms.widgets.Widget):
    recaptcha_challenge_name = 'recaptcha_challenge_field'
    recaptcha_response_name = 'recaptcha_response_field'

    def render(self, name, value, attrs=None):
        return mark_safe(
            u'%s' % captcha.displayhtml(
                settings.RECAPTCHA_PUBLIC_KEY,
                use_ssl=settings.RECAPTCHA_USE_SSL
            )
        )

    def value_from_datadict(self, data, files, name):
        return [
            data.get(self.recaptcha_challenge_name, None),
            data.get(self.recaptcha_response_name, None)
        ]


class ReCaptchaField(forms.CharField):
    default_error_messages = {
        'captcha_invalid': _(u'Invalid captcha')
    }

    def __init__(self, *args, **kwargs):
        self.widget = ReCaptcha
        self.required = True
        super(ReCaptchaField, self).__init__(*args, **kwargs)

    def clean(self, values):
        # ignore captcha validation for unit tests
        import sys
        if 'test' in sys.argv:
            return True
        super(ReCaptchaField, self).clean(values[1])
        recaptcha_challenge_value = smart_unicode(values[0])
        recaptcha_response_value = smart_unicode(values[1])
        check_captcha = captcha.submit(
            recaptcha_challenge_value,
            recaptcha_response_value,
            settings.RECAPTCHA_PRIVATE_KEY,
            {}
        )
        if not check_captcha.is_valid:
            raise ValidationError(self.error_messages['captcha_invalid'])
        return values[0]


class RegistrationForm(_RegistrationForm):
    name = forms.CharField()
    surname = forms.CharField()
    phone = forms.CharField(required=False)
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        label=_("Organization")
    )
    recaptcha = ReCaptchaField(label=_("Verify"), required=False)


class PasswordResetFormPatched(PasswordResetForm):
    error_messages = {
        'unknown': _("That e-mail address doesn't have an associated "
                     "user account or the account has not been activated yet. Are you sure you've registered?"),
        'unusable': _("The user account associated with this e-mail "
                      "address cannot reset the password."),
    }
