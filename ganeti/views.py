import urllib2
import os
import re
import socket
from models import *
from django import forms
from django.core.cache import cache
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, render_to_response
from ganetimgr.util.portforwarder import forward_port
from django.core.context_processors import request
from django.template.context import RequestContext
from django.template.loader import get_template

from gevent.pool import Pool
from gevent.timeout import Timeout

from django.utils import simplejson


def cluster_overview(request):
    clusters = Cluster.objects.all()
#    if request.is_mobile:
#        return render_to_response('m_index.html', {'object_list': clusters}, context_instance=RequestContext(request))
    return render_to_response('index.html', {'object_list': clusters}, context_instance=RequestContext(request))

def cluster_detail(request, slug):
    if slug:
        object = Cluster.objects.get(slug=slug)
    else:
        object = Cluster.objects.all()
#    if request.is_mobile:
#        return render_to_response('m_cluster.html', {'object': object}, context_instance=RequestContext(request))
    return render_to_response('cluster.html', {'object': object}, context_instance=RequestContext(request))

def render_login(request):
    return render_to_response('m_login.html', {'object': object}, context_instance=RequestContext(request))

def check_instance_auth(view_fn):
    def check_auth(request, *args, **kwargs):
        try:
            cluster_slug = kwargs["cluster_slug"]
            instance_name = kwargs["instance"]
        except KeyError:
            cluster_slug = args[0]
            instance_name = args[1]

        cache_key = "cluster:%s:instance:%s:user:%s" % (cluster_slug, instance_name,
                                                        request.user.username)
        res = cache.get(cache_key)
        if res is None:
            cluster = get_object_or_404(Cluster, slug=cluster_slug)
            instance = cluster.get_instance(instance_name)
            res = False

            if (request.user.is_superuser or
                request.user in instance.users or
                set.intersection(set(request.user.groups.all()), set(instance.groups))):
                res = True

            cache.set(cache_key, res, 60)

        if not res:
            t = get_template("403.html")
            return HttpResponseForbidden(content=t.render(RequestContext(request)))
        else:
            return view_fn(request, *args, **kwargs)
    return check_auth


class LoginForm(forms.Form):
    username = forms.CharField(max_length=255)
    password = forms.CharField(max_length=255,
                               widget=forms.widgets.PasswordInput)


def logout_view(request):
    logout(request)
    return HttpResponseRedirect('/')


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(username=form.cleaned_data['username'],
                                password=form.cleaned_data['password'])
            if user is not None:
                if user.is_active:
                    login(request, user)
                else:
                    return HttpResponseForbidden(content='Your account is disabled')
    return HttpResponseRedirect(request.META['HTTP_REFERER'])


def user_index(request):
    p = Pool(20)
    instances = []

    def _get_instances(cluster):
        instances.extend(cluster.get_user_instances(request.user))

    with Timeout(10, False):
        p.imap(_get_instances, Cluster.objects.all())
    p.join()

    return render_to_response('user_instances.html', {'instances': instances},
                              context_instance=RequestContext(request))

@check_instance_auth
def vnc(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    port, password = cluster.setup_vnc_forwarding(instance)

    return render_to_response("vnc.html",
                              {'cluster': cluster,
                               'instance': instance,
                               'host': request.META['HTTP_HOST'],
                               'port': port,
                               'password': password,
                               'user': request.user})


@check_instance_auth
def shutdown(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    cluster.shutdown_instance(instance)
    action = {'action': "Please wait... shutting-down"}
    return HttpResponse(simplejson.dumps(action))


@check_instance_auth
def startup(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    cluster.startup_instance(instance)
    action = {'action': "Please wait... starting-up"}
    return HttpResponse(simplejson.dumps(action))

@check_instance_auth
def reboot(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    cluster.reboot_instance(instance)
    action = {'action': "Please wait... rebooting"}
    return HttpResponse(simplejson.dumps(action))


class InstanceConfigForm(forms.Form):
    nic_type = forms.ChoiceField(label="Network adapter model",
                                 choices=(('paravirtual', 'Paravirtualized'),
                                          ('rtl8139', 'Realtek 8139+'),
                                          ('e1000', 'Intel PRO/1000'),
                                          ('ne2k_pci', 'NE2000 PCI')))

    disk_type = forms.ChoiceField(label="Hard disk type",
                                  choices=(('paravirtual', 'Paravirtualized'),
                                           ('scsi', 'SCSI'),
                                           ('ide', 'IDE')))

    boot_order = forms.ChoiceField(label="Boot device",
                                   choices=(('disk', 'Hard disk'),
                                            ('cdrom', 'CDROM')))

    cdrom_type = forms.ChoiceField(label="CD-ROM Drive",
                                   choices=(('none', 'Disabled'),
                                            ('iso',
                                             'ISO Image over HTTP (see below)')),
                                   widget=forms.widgets.RadioSelect())

    cdrom_image_path = forms.CharField(required=False,
                                       label="ISO Image URL (http)")

    use_localtime = forms.BooleanField(label="Hardware clock uses local time"
                                             " instead of UTC",
                                       required=False)

    def clean_cdrom_image_path(self):
        data = self.cleaned_data['cdrom_image_path']
        if data:
            if not (data == 'none' or re.match(r'(https?|ftp)://', data)):
                raise forms.ValidationError('Only HTTP URLs are allowed')

            elif data != 'none':
                # Check if the image is there
                oldtimeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(5)
                try:
                    response = urllib2.urlopen(data)
                    socket.setdefaulttimeout(oldtimeout)
                except ValueError:
                    socket.setdefaulttimeout(oldtimeout)
                    raise forms.ValidationError('%s is not a valid URL' % data)
                except: # urllib2 HTTP errors
                    socket.setdefaulttimeout(oldtimeout)
                    raise forms.ValidationError('Invalid URL')
        return data


@check_instance_auth
def instance(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    instance = cluster.get_instance(instance)
    if request.method == 'POST':
        configform = InstanceConfigForm(request.POST)
        if configform.is_valid():
            if configform.cleaned_data['cdrom_type'] == 'none':
                configform.cleaned_data['cdrom_image_path'] = ""
            elif (configform.cleaned_data['cdrom_image_path'] !=
                  instance.hvparams['cdrom_image_path']):
                # This should be an http URL
                if not (configform.cleaned_data['cdrom_image_path'].startswith('http://') or
                        configform.cleaned_data['cdrom_image_path'] == ""):
                    # Remove this, we don't want them to be able to read local files
                    del configform.cleaned_data['cdrom_image_path']
            data = {}
            for key, val in configform.cleaned_data.items():
                if key == "cdrom_type":
                    continue
                data[key] = val
            instance.set_params(hvparams=data)
            sleep(2)
            return HttpResponseRedirect(request.path)

    else:
        if instance.hvparams['cdrom_image_path']:
            instance.hvparams['cdrom_type'] = 'iso'
        else:
            instance.hvparams['cdrom_type'] = 'none'
        configform = InstanceConfigForm(instance.hvparams)
#    if request.is_mobile:
#        return render_to_response("m_instance.html",
#                              {'cluster': cluster,
#                               'instance': instance,
#                               'configform': configform,
#                               'user': request.user})
#    else:
    return render_to_response("instance.html",
                              {'cluster': cluster,
                               'instance': instance,
                               'configform': configform,
                               'user': request.user})

@check_instance_auth
def poll(request, cluster_slug, instance):
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        instance = cluster.get_instance(instance)
        return render_to_response("instance_actions.html",
                                  {'cluster':cluster,
                                   'instance': instance,
                                   })
