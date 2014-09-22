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

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from apply.models import InstanceApplication, STATUS_PENDING
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
            pend = InstanceApplication.objects.filter(status=STATUS_PENDING)
            res.update(pending_count=pend.count())
            cache.set('pendingapplications', res, 45)
        else:
            res = cres
    return res
