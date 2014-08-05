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

from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseRedirect

from ganeti.models import Cluster
from gevent.pool import Pool
from gevent.timeout import Timeout
from django.conf import settings
from util.ganeti_client import GanetiApiError

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
            return cmp(",".join([ u.username for u in x.users]),
                       ",".join([ u.username for u in y.users]))
        instances.sort(cmp=cmp_users)
    
        return render_to_response("instance_owners.html",
                                  {"instances": instances},
                                  context_instance=RequestContext(request))
    else:
        return HttpResponseRedirect(reverse('user-instances'))
