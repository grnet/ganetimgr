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
