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

from django.conf import settings
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.template.context import RequestContext
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from ganetimgr.notifications.forms import *
from ganetimgr.ganeti.models import *
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
import json


@csrf_exempt
@login_required
def notify(request):
    if request.user.is_superuser:
        if request.method == 'POST':
            koko = request.POST
            form = MessageForm(request.POST)
            if form.is_valid():
                rl = form.cleaned_data['recipient_list']
                rlist = rl.split(',')
                mail_list = get_mails(rlist)
                email = form.cleaned_data['message']
                if len(mail_list) > 0:
                    send_mail(_("%s%s") % (settings.EMAIL_SUBJECT_PREFIX, form.cleaned_data['subject']),
                              email, settings.SERVER_EMAIL, mail_list)
                return HttpResponseRedirect(reverse('user-instances'))
        else:
            form = MessageForm()
        return render_to_response('notifications/create.html', {
            'form': form,
        })
    else:
        return HttpResponseRedirect(reverse('user-instances'))


def get_mails(itemlist):
    mails = []
    for i in itemlist:
        #User
        if i.startswith('u'):
            mails.append(User.objects.get(pk=i.replace('u_','')).email)
        #Group
        if i.startswith('g'):
            group = Group.objects.get(pk=i.replace('g_',''))
            users = group.user_set.all()
            mails.extend([u.email for u in users])
        #Instance
        if i.startswith('i'):
            instance = Instance.objects.get(name=i.replace('i_',''))
            users = instance.users
            mails.extend([u.email for u in users])
        if i.startswith('c'):
            cluster = Cluster.objects.get(pk=i.replace('c_',''))
            instances = cluster.get_instances()
            for instance in instances:
                mails.extend([u.email for u in instance.users])
    return list(set(mails))
        

@login_required
def get_user_group_list(request):
    if request.user.is_superuser:
        q_params = None
        try:
            q_params = request.GET['q']
        except:
            pass
        users = User.objects.all()
        groups = Group.objects.all()
        instances = Instance.objects.all()
        clusters = Cluster.objects.all()
        if q_params:
            users = users.filter(username__icontains=q_params)
            groups = groups.filter(name__icontains=q_params)
            instances = Instance.objects.filter(name__icontains=q_params)
            clusters = clusters.filter(slug__icontains=q_params)
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
        for instance in instances:
            instd = {}
            instd['text']=instance.name
            instd['id']="i_%s"%instance.name
            instd['type']="vm"
            ret_list.append(instd)
        for cluster in clusters:
            cld = {}
            cld['text']=cluster.slug
            cld['id']="c_%s"%cluster.pk
            cld['type']="cluster"
            ret_list.append(cld)
        action = ret_list
        return HttpResponse(json.dumps(action), mimetype='application/json')
    else:
        action = {'error':_("Permissions' violation. This action has been logged and our admins will be notified about it")}
        return HttpResponse(json.dumps(action), mimetype='application/json')

    
