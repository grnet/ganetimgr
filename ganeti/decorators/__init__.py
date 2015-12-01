from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.template.context import RequestContext

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

            cache.set(cache_key, res, 180)
        if not res:
            t = get_template("403.html")
            return HttpResponseForbidden(content=t.render(RequestContext(request)))
        else:
            return view_fn(request, *args, **kwargs)
    return check_auth


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
            return HttpResponseForbidden(content=t.render(RequestContext(request)))
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
                content=t.render(RequestContext(request))
            )
        else:
            return view_fn(request, *args, **kwargs)
    return check_auth
