from django.contrib import messages
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.core.exceptions import ObjectDoesNotExist

from ganetimgr.accounts.models import UserProfile

class UserMessageMiddleware(object):
    """
    Middleware to display various messages to the users.
    """

    def process_request(self, request):
        if not hasattr(request, "session"):
            return

        if request.user.is_authenticated():
            try:
                first_login = request.session["first_login"]
            except KeyError:
                try:
                    profile = request.user.get_profile()
                except ObjectDoesNotExist:
                    profile = UserProfile.objects.create(user=request.user)
                first_login = profile.first_login
                request.session["first_login"] = first_login

            if first_login:
                messages.add_message(request, messages.INFO,
                                     mark_safe(
                                     _("Welcome! Please take some time to"
                                       " update <a href=\"%s\">your profile</a>"
                                       " and upload your SSH keys.") %
                                       reverse("profile")))
                profile = request.user.get_profile()
                profile.first_login = False
                profile.save()
                request.session["first_login"] = False
