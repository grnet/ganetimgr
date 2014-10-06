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
from gevent.pool import Pool

from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse

from ganeti.models import Cluster
from util.client import GanetiApiError


def instance_owners(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        p = Pool(20)
        instancesall = []
        bad_clusters = []

        def _get_instances(cluster):
            try:
                instancesall.extend(cluster.get_user_instances(request.user))
            except (GanetiApiError, Exception):
                bad_clusters.append(cluster)
        if not request.user.is_anonymous():
            p.imap(_get_instances, Cluster.objects.all())
            p.join()
        instances = [i for i in instancesall if i.users]

        def cmp_users(x, y):
            return cmp(
                ",".join([u.username for u in x.users]),
                ",".join([u.username for u in y.users])
            )
        instances.sort(cmp=cmp_users)

        return render_to_response("instance_owners.html",
                                  {"instances": instances},
                                  context_instance=RequestContext(request))
    else:
        return HttpResponseRedirect(reverse('user-instances'))
