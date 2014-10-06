from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.http import HttpResponseForbidden
from django.template.context import RequestContext

from ganeti.models import Cluster


def check_instance_auth(view_fn):
    def check_auth(request, *args, **kwargs):
        try:
            cluster_slug = kwargs["cluster_slug"]
            instance_name = kwargs["instance"]
        except KeyError:
            cluster_slug = args[0]
            instance_name = args[1]

        cache_key = "cluster:%s:instance:%s:user:%s" % (
            cluster_slug,
            instance_name,
            request.user.username
        )
        res = cache.get(cache_key)
        if res is None:
            cluster = get_object_or_404(Cluster, slug=cluster_slug)
            instance = cluster.get_instance_or_404(instance_name)
            res = False

            if (
                request.user.is_superuser or
                request.user in instance.users or
                set.intersection(
                    set(request.user.groups.all()), set(instance.groups)
                )
            ):
                res = True

            cache.set(cache_key, res, 60)

        if not res:
            t = get_template("403.html")
            return HttpResponseForbidden(content=t.render(RequestContext(request)))
        else:
            return view_fn(request, *args, **kwargs)
    return check_auth
