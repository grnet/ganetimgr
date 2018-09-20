from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.template.context import RequestContext
from functools import partial

from ganeti.models import Cluster, Instance


def ajax_required(f):
    """
    AJAX request required decorator
    use it in your views:

    @ajax_required
    def my_view(request):
        ....

    """
    def wrap(request, *args, **kwargs):
            if not request.is_ajax():
                return HttpResponseBadRequest()
            return f(request, *args, **kwargs)
    wrap.__doc__ = f.__doc__
    wrap.__name__ = f.__name__
    return wrap

def check_auth(view_fn, custom_perm, request, *args, **kwargs):

    cluster_slug = kwargs.get("cluster_slug") or args[0]
    instance_name = kwargs.get("instance") or args[1]

    cache_key = "cluster:%s:instance:%s:user:%s" % (
        cluster_slug,
        instance_name,
        request.user.username
    )
    user_permitted = cache.get(cache_key)
    if user_permitted is None:
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        instance = cluster.get_instance_or_404(instance_name)
        user_permitted = False

        if (
            request.user.is_superuser or
            request.user in instance.users or
            (custom_perm and request.user.has_perm(custom_perm)) or
            (set(request.user.groups.all()) & set(instance.groups))
        ):
            user_permitted = True

        cache.set(cache_key, user_permitted, 180)
    if not user_permitted:
        template = get_template("403.html")
        return HttpResponseForbidden(content=template.render(request=request))
    else:
        return view_fn(request, *args, **kwargs)


def check_graph_auth(view_fn):
    return partial(check_auth, view_fn, 'ganeti.view_all_graphs')


def check_instance_auth(view_fn):
    return partial(check_auth, view_fn, None)


def check_admin_lock(view_fn):
    def check_lock(request, *args, **kwargs):
        try:
            instance_name = kwargs["instance"]
        except KeyError:
            instance_name = args[0]
        if request.user.is_superuser:
            res = False
        else:
            if cache.get('instances:%s' % (instance_name)):
                res = cache.get('instances:%s' % (instance_name))
            else:
                instance = Instance.objects.get(name=instance_name)
                res = instance.adminlock
                cache.set('instances:%s' % (instance_name), res, 60 * 60)
        if not res:
            return view_fn(request, *args, **kwargs)
        else:
            t = get_template("403.html")
            return HttpResponseForbidden(content=t.render(request=request))
    return check_lock


def check_instance_readonly(view_fn):
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
                request.user.has_perm('ganeti.view_instances') or
                set.intersection(
                    set(request.user.groups.all()), set(instance.groups)
                )
            ):
                res = True

            cache.set(cache_key, res, 60)

        if not res:
            t = get_template("403.html")
            return HttpResponseForbidden(
                content=t.render(request=request)
            )
        else:
            return view_fn(request, *args, **kwargs)
    return check_auth
