#

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from ganetimgr.apply.models import InstanceApplication, STATUS_PENDING

def notify(request):
    res = {}
    if (request.user and
        request.user.has_perm("apply.change_instance_application")):
        res.update(can_handle_applications=True)
        pend = InstanceApplication.objects.filter(status=STATUS_PENDING)
        res.update(pending_count=pend.count())
    return res
