#

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from ganetimgr.apply.models import InstanceApplication, STATUS_PENDING

def notify(request):
    res = {}
    if (request.user and
        request.user.has_perm("apply.change_instance_application")):
        pend = InstanceApplication.objects.filter(status=STATUS_PENDING)
        if pend:
            count = pend.count()
            msg = "There are <a href=\"%s\">%d pending" \
                  " applications</a>." % (reverse("application-list"), count)
            messages.add_message(request, messages.INFO, mark_safe(msg))
            res.update(pending_count=count)
    return res
