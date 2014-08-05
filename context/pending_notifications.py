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

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from apply.models import InstanceApplication, PENDING_CODES
from django.core.cache import cache

def notify(request):
    res = {}
    if request.user:
        if request.user.has_perm("apply.change_instanceapplication"):
            res.update(can_handle_applications=True)
        elif request.user.has_perm("apply.view_applications"):
            res.update(can_view_applications=True)
        else:
            return res
        cres = cache.get('pendingapplications')
        if cres is None:
            pend = InstanceApplication.objects.filter(status__in=PENDING_CODES)
            res.update(pending_count=pend.count())
            cache.set('pendingapplications', res, 45)
        else:
            res = cres
    return res
