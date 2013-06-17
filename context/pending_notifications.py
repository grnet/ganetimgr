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

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from ganetimgr.apply.models import InstanceApplication, STATUS_PENDING
from django.core.cache import cache

def notify(request):
    res = {}
    if (request.user and
        request.user.has_perm("apply.change_instanceapplication")):
        res.update(can_handle_applications=True)
        cres = cache.get('pendingapplications')
        if cres is None:
            pend = InstanceApplication.objects.filter(status=STATUS_PENDING)
            res.update(pending_count=pend.count())
            cache.set('pendingapplications', res, 45)
        else:
            res = cres
    return res
