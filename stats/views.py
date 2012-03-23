#
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

from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.contrib.auth.decorators import user_passes_test

from ganetimgr.ganeti.models import Cluster


@user_passes_test(lambda u: u.is_staff)
def instance_owners(request):
    instances = [i for i in Cluster.get_all_instances() if i.users]
    def cmp_users(x, y):
        return cmp(",".join([ u.username for u in x.users]),
                   ",".join([ u.username for u in y.users]))
    instances.sort(cmp=cmp_users)

    return render_to_response("instance_owners.html",
                              {"instances": instances},
                              context_instance=RequestContext(request))
