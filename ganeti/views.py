#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
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

import urllib2
import re
import socket
from django import forms
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, render_to_response
from django.core.context_processors import request
from django.template.context import RequestContext
from django.template.loader import get_template
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.conf import settings
from ganetimgr.ganeti.models import *
from ganetimgr.ganeti.forms import *
from operator import itemgetter
from django.template.defaultfilters import filesizeformat

from gevent.pool import Pool
from gevent.timeout import Timeout

from util.ganeti_client import GanetiApiError
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext as _
from django.core.mail import send_mail, mail_managers

from time import sleep, mktime
import datetime

try:
    import json
except ImportError:
    import simplejson as json

from ganetimgr.settings import GANETI_TAG_PREFIX


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

@login_required
def user_info(request, type, usergroup):
     if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
         if type == 'user' :
             usergroup_info = User.objects.get(username=usergroup)
         if type == 'group' :
             usergroup_info = Group.objects.get(name=usergroup)
         return render_to_response('user_info.html', {'usergroup': usergroup_info, 'type': type}, context_instance=RequestContext(request))
     else:
        return HttpResponseRedirect(reverse('user-instances'))

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
            instance = cluster.get_instance_or_404(instance_name)
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


def user_index(request):
    if request.user.is_anonymous():
        return HttpResponseRedirect(reverse('login'))
    return render_to_response('user_instances_json.html',
                              context_instance=RequestContext(request))
@login_required
def user_index_json(request):
    if request.user.is_anonymous():
        action = {'error':_("Permissions' violation. This action has been logged and our admins will be notified about it")}
        return HttpResponse(json.dumps(action), mimetype='application/json')
    p = Pool(20)
    instances = []
    bad_clusters = []

    def _get_instances(cluster):
        t = Timeout(5)
        t.start()
        try:
            instances.extend(cluster.get_user_instances(request.user))
        except (GanetiApiError, Timeout):
            bad_clusters.append(cluster)
        finally:
            t.cancel()

    if not request.user.is_anonymous():
        p.imap(_get_instances, Cluster.objects.all())
        p.join()

    if bad_clusters:
        messages.add_message(request, messages.WARNING,
                             "Some instances may be missing because the"
                             " following clusters are unreachable: " +
                             ", ".join([c.description for c in bad_clusters]))
    jresp = {}
    cache_key = "user:%s:index:instances" %request.user.username
    res = cache.get(cache_key)
    instancedetails = []
    j = Pool(80)
    user = request.user
    def _get_instance_details(instance):
        t = Timeout(2)
        t.start()
        try:
            instancedetails.extend(generate_json(instance, user))
        except Exception as e:
            pass
        finally:
            t.cancel()
    
    if res is None:
        j.imap(_get_instance_details, instances)
        j.join()
        jresp['aaData'] = instancedetails
        cache.set(cache_key, jresp, 90)
        res = jresp

    return HttpResponse(json.dumps(res), mimetype='application/json')

@login_required
def user_sum_stats(request):
    if request.user.is_anonymous():
        action = {'error':_("Permissions' violation. This action has been logged and our admins will be notified about it")}
        return HttpResponse(json.dumps(action), mimetype='application/json')
    p = Pool(20)
    instances = []
    bad_clusters = []

    def _get_instances(cluster):
        t = Timeout(5)
        t.start()
        try:
            instances.extend(cluster.get_user_instances(request.user))
        except (GanetiApiError, Timeout):
            bad_clusters.append(cluster)
        finally:
            t.cancel()

    if not request.user.is_anonymous():
        p.imap(_get_instances, Cluster.objects.all())
        p.join()

    if bad_clusters:
        messages.add_message(request, messages.WARNING,
                             "Some instances may be missing because the"
                             " following clusters are unreachable: " +
                             ", ".join([c.description for c in bad_clusters]))
    jresp = {}
    cache_key = "user:%s:index:instance:light" %request.user.username
    res = cache.get(cache_key)
    instancedetails = []
    j = Pool(80)
    user = request.user
    def _get_instance_details(instance):
        t = Timeout(5)
        t.start()
        try:
            instancedetails.extend(generate_json_light(instance, user))
        except Exception as e:
            pass
        finally:
            t.cancel()
    
    if res is None:
        j.imap(_get_instance_details, instances)
        j.join()
        jresp['aaData'] = instancedetails
        cache.set(cache_key, jresp, 125)
        res = jresp
    
    instances_stats = []
    user_dict = {}
    cache_key_stats = "user:%s:index:users:instance:stats" %request.user.username
    instances_stats = cache.get(cache_key_stats)
    if instances_stats is None:
        for i in res['aaData']:
            if not i.has_key('users'):
                i['users'] = [{'user':request.user.username}]
            for useritem in i['users']:
                if not user_dict.has_key(useritem['user']):
                    user_dict[useritem['user']] = {'instances':0, 'disk':0, 'cpu':0, 'memory':0}
                user_dict[useritem['user']]['instances'] = user_dict[useritem['user']]['instances'] + 1
                user_dict[useritem['user']]['disk'] = user_dict[useritem['user']]['disk'] + int(i['disk'])
                user_dict[useritem['user']]['cpu'] = user_dict[useritem['user']]['cpu'] + int(i['vcpus'])
                user_dict[useritem['user']]['memory'] = user_dict[useritem['user']]['memory'] + int(i['memory'])
        #TODO: Must implement that in a more efficient way
        instances_stats_list = []
        for u in user_dict.keys():
            user_stats_dict = {}
            user_stats_dict['user'] = u
            user_stats_dict['instances'] = user_dict[u]['instances']
            user_stats_dict['disk'] = user_dict[u]['disk']
            user_stats_dict['cpu'] = user_dict[u]['cpu']
            user_stats_dict['memory'] = user_dict[u]['memory']
            instances_stats_list.append(user_stats_dict)
        return_dict = {'aaData': instances_stats_list}
        cache.set(cache_key_stats, return_dict, 120)
        instances_stats = return_dict
    
    return HttpResponse(json.dumps(instances_stats), mimetype='application/json')    

def generate_json(instance, user):
    jresp_list = []
    i = instance
    inst_dict = {}
    if not i.admin_view_only:
        inst_dict['name_href'] = "%s"%(reverse("instance-detail",
                        kwargs={'cluster_slug': i.cluster.slug, 'instance':i.name}
                        ))

    inst_dict['name'] =  i.name
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['cluster'] = i.cluster.slug
    else:
        inst_dict['cluster'] = i.cluster.description
    inst_dict['memory'] = memsize(i.beparams['memory'])
    inst_dict['vcpus'] = i.beparams['vcpus']
    inst_dict['ipaddress'] = [ip for ip in i.nic_ips if ip]
    inst_dict['ipv6address'] = [ip for ip in i.ipv6s if ip]
    #inst_dict['status'] = i.nic_ips[0] if i.nic_ips[0] else "-"
    if i.admin_state == i.oper_state:
        if i.admin_state:
            inst_dict['status'] = "Running"
            inst_dict['status_style'] = "success"
        else:
            inst_dict['status'] = "Stopped"
            inst_dict['status_style'] = "important"
    else:
        if i.oper_state:
            inst_dict['status'] = "Running"
        else:
            inst_dict['status'] = "Stopped"
        if i.admin_state:
            inst_dict['status'] = "%s, should be running" %inst_dict['status']
        else:
            inst_dict['status'] = "%s, should be stopped" %inst_dict['status']
        inst_dict['status_style'] = "warning"
    
    if i.is_locked():
        inst_dict['locked'] = True
    if i.hvparams['cdrom_image_path'] and i.hvparams['boot_order'] == 'cdrom':
         inst_dict['cdrom'] = True
    inst_dict['nic_macs'] = ', '.join(i.nic_macs)
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['nic_links'] = ', '.join(i.nic_links)
        inst_dict['users'] = [{'user':user.username, 'email':user.email, 'user_href':"%s"%(reverse("user-info",
                            kwargs={'type': 'user', 'usergroup':user.username}
                            ))} for user in i.users]
        inst_dict['groups'] = [{'group':group.name, 'groupusers':["%s,%s"%(u.username, u.email) for u in group.userset], 'group_href':"%s"%(reverse("user-info",
                            kwargs={'type': 'group', 'usergroup':group.name}
                            ))} for group in i.groups]
    jresp_list.append(inst_dict)
    return jresp_list


def generate_json_light(instance, user):
    
    jresp_list = []
    i = instance
    inst_dict = {}
    if not i.admin_view_only:
        inst_dict['name_href'] = "%s"%(reverse("instance-detail",
                        kwargs={'cluster_slug': i.cluster.slug, 'instance':i.name}
                        ))

    inst_dict['name'] =  i.name
    inst_dict['clusterslug'] = i.cluster.slug
    inst_dict['memory'] = i.beparams['memory']
    inst_dict['vcpus'] = i.beparams['vcpus']
    inst_dict['disk'] = sum(i.disk_sizes)
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['users'] = [{'user':user.username} for user in i.users]
    jresp_list.append(inst_dict)
    return jresp_list

@login_required
@check_instance_auth
def vnc(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    port, password = cluster.setup_vnc_forwarding(instance)

    return render_to_response("vnc.html",
                              {'cluster': cluster,
                               'instance': instance,
                               'host': request.META['HTTP_HOST'],
                               'port': port,
                               'password': password},
                               context_instance=RequestContext(request))


@login_required
@csrf_exempt
@check_instance_auth
def shutdown(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    cluster.shutdown_instance(instance)
    action = {'action': _("Please wait... shutting-down")}
    clear_cluster_user_cache(request.user.username, cluster_slug)
    return HttpResponse(json.dumps(action))

@login_required
@csrf_exempt
@check_instance_auth
def rename_instance(request, cluster_slug, instance, action_id, action_value=None):
    if request.method == 'POST':
        form = InstanceRenameForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            action_value = data['hostname']
            return HttpResponseRedirect(reverse('instance-reinstall-destroy',
                                                kwargs={'cluster_slug': cluster_slug, 
                                                        'instance':instance,
                                                        'action_id': int(action_id),
                                                        'action_value': action_value}))
        else:
            return render_to_response('rename_instance.html',
                {
                    'form': form, 'instance': instance, 'cluster_slug': cluster_slug
                }, 
                context_instance=RequestContext(request)
                )
    elif request.method == 'GET':
        form = InstanceRenameForm()
        return render_to_response('rename_instance.html', {
                'form': form, 'instance': instance, 'cluster_slug': cluster_slug}, 
                context_instance=RequestContext(request)
            )


@login_required
@csrf_exempt
@check_instance_auth
def reinstalldestroy(request, cluster_slug, instance, action_id, action_value=None):
    action_id = int(action_id)
    if action_id not in [1,2,3]:
        action = {'action':_("Not allowed action")}
        return HttpResponse(json.dumps(action))
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    instance = cluster.get_instance_or_404(instance)
    reinstalldestroy_req = InstanceAction.objects.create_action(request.user, instance, cluster, action_id, action_value)
    fqdn = Site.objects.get_current().domain
    url = "https://%s%s" % \
               (
                fqdn,
                reverse("reinstall-destroy-review",
                        kwargs={'application_hash': reinstalldestroy_req.activation_key, 'action_id':action_id}
                        )
                )
    email = render_to_string("reinstall_mail.txt",
                                         {"instance": instance,
                                          "user": request.user,
                                          "action": reinstalldestroy_req.get_action_display(),
                                          "action_value": reinstalldestroy_req.action_value,
                                          "url": url})
    if action_id == 1:
        action_mail_text = "re-installation"
    if action_id == 2:
        action_mail_text = "destruction"
    if action_id == 3:
        action_mail_text = "rename"
    send_mail(_("%sInstance %s requested: %s") % (settings.EMAIL_SUBJECT_PREFIX, action_mail_text, instance),
                  email, settings.SERVER_EMAIL, [request.user.email])
    action = {'action':_("Mail sent")}
    return HttpResponse(json.dumps(action))

@login_required
@csrf_exempt
def reinstalldestreview(request, application_hash, action_id):
    action_id = int(action_id)
    if action_id not in [1,2,3,4]:
        return HttpResponseRedirect(reverse('user-instances'))
    activation_key = application_hash.lower() # Normalize before trying anything with it.
    try:
        action = InstanceAction.objects.get(activation_key=activation_key, action=action_id)
    except InstanceAction.DoesNotExist:
        activated = True
        return render_to_response('verify_action.html', {
                                                         'action': action_id,
                                                         'activated': activated,
                                                         'hash': application_hash},
                                  context_instance=RequestContext(request))
    instance = action.instance
    cluster = action.cluster
    action_value = action.action_value
    activated = False
    if action.activation_key_expired():
            activated = True
    if request.method == 'POST':
        if not activated:
            instance_action = InstanceAction.objects.activate_request(application_hash)
            if not instance_action:
                 return render_to_response('verify_action.html', {
                                                             'action': action_id, 
                                                             'activated': activated, 
                                                             'hash': application_hash},
                              context_instance=RequestContext(request))
            if action_id == 1:
                cluster.reinstall_instance(instance)
            if action_id == 2:
                cluster.destroy_instance(instance)
            if action_id == 3:
                cluster.rename_instance(instance, action_value)
            if action_id == 4:
                user = User.objects.get(username=request.user)
                user.email = action_value
                user.save()
                return HttpResponseRedirect(reverse('profile'))
            activated = True
            return HttpResponseRedirect(reverse('instance-detail', kwargs={
                                                    'instance': instance, 
                                                    'cluster_slug':cluster.slug 
                                                     }))
        else:
            return render_to_response('verify_action.html', {
                                                             'action': action_id, 
                                                             'activated': activated, 
                                                             'hash': application_hash},
                              context_instance=RequestContext(request))
        
    elif request.method == 'GET':
        return render_to_response('verify_action.html', {'instance': instance,
                                                         'action': action_id,
                                                         'action_value': action_value,  
                                                         'cluster':cluster, 
                                                         'activated': activated, 
                                                         'hash': application_hash},
                                  context_instance=RequestContext(request))
    else:
        return HttpResponseRedirect(reverse('user-instances'))




@login_required
@csrf_exempt
@check_instance_auth
def startup(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    cluster.startup_instance(instance)
    action = {'action': _("Please wait... starting-up")}
    clear_cluster_user_cache(request.user.username, cluster_slug)
    return HttpResponse(json.dumps(action))

@login_required
@csrf_exempt
@check_instance_auth
def reboot(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    cluster.reboot_instance(instance)
    action = {'action': _("Please wait... rebooting")}
    clear_cluster_user_cache(request.user.username, cluster_slug)
    return HttpResponse(json.dumps(action))


class InstanceConfigForm(forms.Form):
    nic_type = forms.ChoiceField(label=ugettext_lazy("Network adapter model"),
                                 choices=(('paravirtual', 'Paravirtualized'),
                                          ('rtl8139', 'Realtek 8139+'),
                                          ('e1000', 'Intel PRO/1000'),
                                          ('ne2k_pci', 'NE2000 PCI')))

    disk_type = forms.ChoiceField(label=ugettext_lazy("Hard disk type"),
                                  choices=(('paravirtual', 'Paravirtualized'),
                                           ('scsi', 'SCSI'),
                                           ('ide', 'IDE')))

    boot_order = forms.ChoiceField(label=ugettext_lazy("Boot device"),
                                   choices=(('disk', 'Hard disk'),
                                            ('cdrom', 'CDROM')))

    cdrom_type = forms.ChoiceField(label=ugettext_lazy("CD-ROM Drive"),
                                   choices=(('none', 'Disabled'),
                                            ('iso',
                                             'ISO Image over HTTP (see below)')),
                                   widget=forms.widgets.RadioSelect())

    cdrom_image_path = forms.CharField(required=False,
                                       label=ugettext_lazy("ISO Image URL (http)"))

    use_localtime = forms.BooleanField(label=ugettext_lazy("Hardware clock uses local time"
                                             " instead of UTC"),
                                       required=False)

    def clean_cdrom_image_path(self):
        data = self.cleaned_data['cdrom_image_path']
        if data:
            if not (data == 'none' or re.match(r'(https?|ftp)://', data)):
                raise forms.ValidationError(_('Only HTTP URLs are allowed'))

            elif data != 'none':
                # Check if the image is there
                oldtimeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(5)
                try:
                    response = urllib2.urlopen(data)
                    socket.setdefaulttimeout(oldtimeout)
                except ValueError:
                    socket.setdefaulttimeout(oldtimeout)
                    raise forms.ValidationError(_('%(url)s is not a valid URL') % { 'url': data})
                except: # urllib2 HTTP errors
                    socket.setdefaulttimeout(oldtimeout)
                    raise forms.ValidationError(_('Invalid URL'))
        return data

    
@login_required
@check_instance_auth
def instance(request, cluster_slug, instance):
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    instance = cluster.get_instance_or_404(instance)
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
    instance.cpu_url = reverse(graph, args=(cluster.slug, instance.name,'cpu-ts'))
    instance.net_url = reverse(graph, args=(cluster.slug, instance.name,'net-ts'))

    return render_to_response("instance.html",
                              {'cluster': cluster,
                               'instance': instance,
                               'configform': configform},
                              context_instance=RequestContext(request))

@login_required
def instance_popup(request):
    if (request.user.is_superuser or request.user.has_perm('ganeti.view_instances')):
        if request.method == 'GET':
            if 'cluster' in request.GET:
                cluster_slug = request.GET.get('cluster')
            if 'instance' in request.GET:
                instance = request.GET.get('instance')
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        instance = cluster.get_instance_or_404(instance)

        return render_to_response("instance_popup.html",
                                  {'cluster': cluster,
                                   'instance': instance},
                                  context_instance=RequestContext(request))
    else:
        return HttpResponseRedirect(reverse('user-instances'))

@login_required
@check_instance_auth
def poll(request, cluster_slug, instance):
        cluster = get_object_or_404(Cluster, slug=cluster_slug)
        instance = cluster.get_instance_or_404(instance)
        return render_to_response("instance_actions.html",
                                  {'cluster':cluster,
                                   'instance': instance,
                                   },
                                  context_instance=RequestContext(request))

@csrf_exempt
@login_required     
def tagInstance(request, instance):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        instance = Instance.objects.get(name=instance)
        if request.method == 'POST':
            users = []
            for user in instance.users:
                users.append("u_%s"%user.pk)
            groups = []
            for group in instance.groups:
                groups.append("g_%s"%group.pk)
            existingugtags = users+groups
            form = tagsForm(request.POST)
            if form.is_valid():
                newtags = form.cleaned_data['tags']
                newtags = newtags.split(',')
                common = list(set(existingugtags).intersection(set(newtags)))
                deltags = list(set(existingugtags)-set(common))
                if len(deltags)>0:
                    #we have tags to delete
                    oldtodelete = prepare_tags(deltags)
                    instance.cluster._client.DeleteInstanceTags(instance.name, oldtodelete)
                newtagstoapply = prepare_tags(newtags)
                instance.cluster._client.AddInstanceTags(instance.name, newtagstoapply)
                cache_key = instance.cluster._instance_cache_key(instance)
                cache.delete(cache_key)
                cache.delete("cluster:%s:instances" % instance.cluster.slug)
                res = {'result':'success'}
                return HttpResponse(json.dumps(res), mimetype='application/json')
            else:
                return render_to_response('tagging/itags.html',
                    {
                        'form': form, 'users': users, 'instance': instance
                    }, 
                    context_instance=RequestContext(request)
                    )
        elif request.method == 'GET':
            form = tagsForm()
            users = []
            for user in instance.users:
                userd = {}
                userd['text']=user.username
                userd['id']="u_%s"%user.pk
                userd['type']="user"
                users.append(userd)
            for group in instance.groups:
                groupd = {}
                groupd['text']=group.name
                groupd['id']="u_%s"%group.pk
                groupd['type']="group"
                users.append(groupd)
            return render_to_response('tagging/itags.html', {
                    'form': form, 'users': users, 'instance': instance}, 
                    context_instance=RequestContext(request)
                )
    else:
        return HttpResponseRedirect(reverse('user-instances'))

@login_required
def get_clusternodes(request):
    if (request.user.is_superuser or request.user.has_perm('ganeti.view_instances')):
        nodes = cache.get('allclusternodes')
        if nodes is None:
            clusters = Cluster.objects.all()
            p = Pool(20)
            nodes = []
            bad_clusters = []
            bad_nodes = []
            servermon_url = None
            def _get_nodes(cluster):
                t = Timeout(5)
                t.start()
                try:
                    nodes.extend(cluster.get_node_info(node) for node in cluster.get_cluster_nodes())
                    bad_nodes.extend(cluster.get_node_info(node)['name'] for node in cluster.get_cluster_nodes() if cluster.get_node_info(node)['offline'] == True)
                except (GanetiApiError, Timeout):
                    bad_clusters.append(cluster)
                finally:
                    t.cancel()
        
            if not request.user.is_anonymous():
                p.imap(_get_nodes, clusters)
                p.join()
                
            if bad_clusters:
                messages.add_message(request, messages.WARNING,
                                     "Some nodes may be missing because the" +
                                     " following clusters are unreachable: " +
                                     ", ".join([c.description for c in bad_clusters]))
            if bad_nodes:
                messages.add_message(request, messages.ERROR,
                                     "Some nodes appear to be offline: "+
                                     ", ".join(bad_nodes))
            cache.set('allclusternodes', nodes, 90)
        if settings.SERVER_MONITORING_URL:
            servermon_url = settings.SERVER_MONITORING_URL 
        return render_to_response('cluster_nodes.html', {'nodes': nodes, 'servermon':servermon_url},
                                  context_instance=RequestContext(request))
    else:
        return HttpResponseRedirect(reverse('user-instances'))

def prepare_tags(taglist):
    tags = []
    for i in taglist:
        #User
        if i.startswith('u'):
            tags.append("%s:user:%s" %(GANETI_TAG_PREFIX, User.objects.get(pk=i.replace('u_','')).username))
        #Group
        if i.startswith('g'):
            tags.append("%s:group:%s" %(GANETI_TAG_PREFIX, Group.objects.get(pk=i.replace('g_','')).name))
    return list(set(tags))

@login_required
def stats(request):
    clusters = Cluster.objects.all()
    if (request.user.is_superuser or request.user.has_perm('ganeti.view_instances')):
        instances = cache.get('leninstances')
        if instances is None:
            instances = len(Instance.objects.all())
            cache.set('leninstances', instances, 90)
        users = cache.get('lenusers')
        if users is None:
            users = len(User.objects.all())
            cache.set('lenusers', users, 90)
        groups = cache.get('lengroups')
        if groups is None:
            groups = len(Group.objects.all())
            cache.set('lengroups', groups, 90)
        instance_apps = cache.get('leninstapps')
        if instance_apps is None:
            instance_apps = len(InstanceApplication.objects.all())
            cache.set('leninstapps', instance_apps, 90)
        orgs = cache.get('lenorgs')
        if orgs is None:
            orgs = len(Organization.objects.all())
            cache.set('lenorgs', orgs, 90)
        return render_to_response('statistics.html', {
                                                      'clusters':clusters, 
                                                      'instances':instances,
                                                      'users':users,
                                                      'groups': groups,
                                                      'instance_apps': instance_apps,
                                                      'orgs': orgs},
                                  context_instance=RequestContext(request))
    else:
        return render_to_response('statistics.html',
                                  {'clusters':clusters},  
                                  context_instance=RequestContext(request))

@login_required
def stats_ajax_instances(request):
    username = request.user.username
    cluster_list = cache.get('%s:ajaxinstances' %username)
    if cluster_list is None:
        clusters = Cluster.objects.all()
        inst_dates = []
        ret = []
        i = 0
        cluster_list = []
        for cluster in clusters:
            i = 0
            cluster_dict = {}
            if (request.user.is_superuser or request.user.has_perm('ganeti.view_instances')):
                cluster_dict['name'] = cluster.slug
            else:
                cluster_dict['name'] = cluster.description
            cluster_dict['instances'] = []
            for instance in cluster.get_user_instances(request.user):
                inst_dict = {}
                inst_dict['time'] = (1000*mktime(instance.ctime.timetuple()))
                inst_dict['name'] = instance.name
                cluster_dict['instances'].append(inst_dict)
            cluster_dict['instances'] = sorted(cluster_dict['instances'], key=itemgetter('time'))
            for item in cluster_dict['instances']:
                i = i + 1
                item['count'] = i
            cluster_list.append(cluster_dict)
        cache.set('%s:ajaxinstances' %username, cluster_list, 90)
    return HttpResponse(json.dumps(cluster_list), mimetype='application/json')

@login_required
def stats_ajax_vms_per_cluster(request, cluster_slug):
    cluster_dict = cache.get('%s:ajaxvmscluster:%s'%(request.user.username, cluster_slug))
    if cluster_dict is None:
        cluster = Cluster.objects.get(slug=cluster_slug)
        inst_dates = []
        ret = []
        i = 0
        cluster_dict = {}
        cluster_dict['name'] = cluster.slug
        cluster_dict['instances'] = {'up':0,'down':0}
        for instance in cluster.get_user_instances(request.user):
            if instance.admin_state:
                cluster_dict['instances']['up'] = cluster_dict['instances']['up'] + 1
            else:
                cluster_dict['instances']['down'] = cluster_dict['instances']['down'] + 1
        cache.set('%s:ajaxvmscluster:%s'%(request.user.username, cluster_slug), cluster_dict, 90)
    return HttpResponse(json.dumps(cluster_dict), mimetype='application/json')


@login_required
def stats_ajax_applications(request):
    username = request.user.username
    app_list = cache.get('%s:ajaxapplist' %username)
    if app_list is None:
        applications = InstanceApplication.objects.all().order_by('filed')
        if not (request.user.is_superuser or request.user.has_perm('ganeti.view_instances')):
            applications = applications.filter(applicant = request.user)
        app_list = []
        i = 0
        for app in applications:
           appd = {}
           appd['instance'] = app.hostname
           i = i + 1
           appd['count'] = i
           appd['user'] = app.applicant.username
           appd['time'] = (1000*mktime(app.filed.timetuple()))
           app_list.append(appd)
        cache.set('%s:ajaxapplist' %username,app_list, 90)
    return HttpResponse(json.dumps(app_list), mimetype='application/json')


@login_required
def get_user_groups(request):
    if request.user.is_superuser or request.user.has_perm('ganeti.view_instances'):
        q_params = None
        try:
            q_params = request.GET['q']
        except:
            pass
        users = User.objects.all()
        groups = Group.objects.all()
        if q_params:
            users = users.filter(username__icontains=q_params)
            groups = groups.filter(name__icontains=q_params)
        ret_list = []
        for user in users:
            userd = {}
            userd['text']=user.username
            userd['email']=user.email
            userd['id']="u_%s"%user.pk
            userd['type']="user"
            ret_list.append(userd)
        for group in groups:
            groupd = {}
            groupd['text']=group.name
            groupd['id']="g_%s"%group.pk
            groupd['type']="group"
            ret_list.append(groupd)
        action = ret_list
        return HttpResponse(json.dumps(action), mimetype='application/json')
    else:
        action = {'error':_("Permissions' violation. This action has been logged and our admins will be notified about it")}
        return HttpResponse(json.dumps(action), mimetype='application/json')

def disksizes(value):
    return [filesizeformat(v * 1024**2) for v in value]

def memsize(value):
    return filesizeformat(value * 1024**2)

@login_required
@check_instance_auth
def graph(request, cluster_slug, instance, graph_type, start=None, end=None):
    if not start:
        start = "-1d"
    start = str(start)
    if not end:
        end = "-20s"
    end = str(end)
    try:
        url = "%s/%s/%s.png/%s,%s" %(settings.COLLECTD_URL, instance, graph_type, start, end)
        req = urllib2.Request(url)
        response = urllib2.urlopen(req)
    except urllib2.HTTPError:
        pass
    return HttpResponse(response.read(), mimetype="image/png")

@login_required
def idle_accounts(request):
    if (request.user.is_superuser or request.user.has_perm('ganeti.view_instances')):
        idle_users = []
        idle_users.extend([u for u in User.objects.filter(is_active=True, last_login__lte=datetime.datetime.now()-datetime.timedelta(days=int(settings.IDLE_ACCOUNT_NOTIFICATION_DAYS))) if u.email])
        idle_users = list(set(idle_users))
        return render_to_response('idle_accounts.html', {'users': idle_users},
                                  context_instance=RequestContext(request))


def clear_cluster_user_cache(username, cluster_slug):
    cache.delete("user:%s:index:instances" %username)
    cache.delete("cluster:%s:instances" % cluster_slug)

