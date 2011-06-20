from django import forms
from recap import field as recap_field
from registration.forms import RegistrationForm
from django.utils.translation import ugettext_lazy as _

class RecaptchaRegistrationForm(RegistrationForm):
    recaptcha = recap_field.ReCaptchaField(label=_("Verify"))
