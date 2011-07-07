from django.conf import settings
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from registration.models import RegistrationProfile
from registration.views import activate as registration_activate

def activate(request, activation_key):
    activation_key = activation_key.lower() # Normalize before trying anything with it.
    account = RegistrationProfile.objects.activate_user(activation_key)
    context = RequestContext(request)

    if account:
        # A user has been activated
        email = render_to_string("registration/activation_complete.txt",
                                 {"site": Site.objects.get_current(),
                                  "user": account})
        send_mail(_("%sUser account activated") % settings.EMAIL_SUBJECT_PREFIX,
                  email, settings.SERVER_EMAIL, [account.email])

    return render_to_response("registration/activate.html",
                              { 'account': account,
                                'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS },
                              context_instance=context)
