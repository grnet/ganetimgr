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

from cStringIO import StringIO

from django import forms
from django.contrib import messages
from django.core import urlresolvers
from django.utils.safestring import mark_safe
from django.core.mail import send_mail, mail_managers
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.template.loader import render_to_string, get_template
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.sites.models import Site
from django.core.cache import cache

from ganetimgr.apply.models import *
from ganetimgr.apply.forms import *
from ganetimgr.ganeti.models import Cluster, Network, InstanceAction
from ganetimgr.settings import SERVER_EMAIL, EMAIL_SUBJECT_PREFIX

from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from django.contrib.auth.decorators import user_passes_test


def any_permission_required(*args):
    def test_func(user):
        for perm in args:
            if user.has_perm(perm):
                return True
        return False
    return user_passes_test(test_func)

@login_required
def apply(request):
    user_groups = request.user.groups.all()
    user_networks = Network.objects.filter(groups__in=user_groups).distinct()

    if user_networks:
        InstanceApplicationForm.base_fields["network"] = \
            forms.ModelChoiceField(queryset=user_networks, required=False,
                                   label=ugettext_lazy("Network"),
                                   help_text=ugettext_lazy("Optionally, select"
                                    " a network to connect the virtual machine"
                                    " to if you have a special requirement"))
    else:
        try:
            del InstanceApplicationForm.base_fields["network"]
        except KeyError:
            pass

    if request.method == "GET":
        form = InstanceApplicationForm()
        return render_to_response('apply.html', {'form': form},
                                  context_instance=RequestContext(request))

    else:
        form = InstanceApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.applicant = request.user
            application.status = STATUS_PENDING
            net = request.POST.get('network','')
            if net:
                network = Network.objects.get(pk=net)
                application.instance_params = {"cluster":network.cluster.slug, "network":network.link, "mode":network.mode}
            application.save()
            fqdn = Site.objects.get_current().domain
            admin_url = "https://%s%s" % \
               (fqdn,
                urlresolvers.reverse("application-review",
                                     kwargs={"application_id": application.pk}))
            mail_body = render_to_string("apply_mail.txt",
                                         {"application": application,
                                          "user": request.user,
                                          "url": admin_url})
            mail_managers("New instance request by %s: %s" %
                         (request.user, application.hostname),
                         mail_body)
            messages.add_message(request, messages.INFO,
                                 _("Your request has been filed with id #%d and"
                                 " will be processed shortly.") %
                                 application.id)
            
            return HttpResponseRedirect(urlresolvers.reverse("user-instances"))
        else:
            return render_to_response('apply.html', {'form': form},
                                      context_instance=RequestContext(request))


@any_permission_required("apply.change_instanceapplication", "apply.view_applications")
def application_list(request):
    applications = InstanceApplication.objects.all()
    pending = applications.filter(status__in=PENDING_CODES)
    completed = applications.exclude(status__in=PENDING_CODES)

    return render_to_response("application_list.html",
                              {'applications': applications,
                               'pending': pending,
                               'completed': completed},
                              context_instance=RequestContext(request))


@permission_required("apply.change_instanceapplication")
def review_application(request, application_id):
    applications = InstanceApplication.objects.filter(status__in=PENDING_CODES)
    app = get_object_or_404(InstanceApplication, pk=application_id)
    fast_clusters = Cluster.objects.filter(fast_create=True).exclude(disable_instance_creation=True).order_by('description')

    if request.method == "GET":
        form = InstanceApplicationReviewForm(instance=app)
        if app.instance_params and 'cluster' in app.instance_params.keys():
            form = InstanceApplicationReviewForm(instance=app, initial={"cluster":Cluster.objects.get(slug=app.instance_params['cluster']).pk})
        return render_to_response('review.html',
                                  {'application': app,
                                   'applications': applications,
                                   'appform': form,
                                   'fast_clusters': fast_clusters},
                                  context_instance=RequestContext(request))

    else:
        nodegroup = request.POST.get('node_group', '')
        form_ngs = (('',''),)
        if nodegroup:
            form_ngs = ((nodegroup, nodegroup),)

        netw = request.POST.get('netw', '')
        form_netw = (('',''),)
        if netw:
            form_netw = ((netw, netw),)

        vgs = request.POST.get('vgs', '')
        form_vgs = (('',''),)
        if vgs:
            form_vgs = ((vgs, vgs),)

        dt = request.POST.get('disk_template', '')
        form_dt = (('',''),)
        if dt:
            form_dt = ((dt, dt),)
        form = InstanceApplicationReviewForm(request.POST, instance=app)
        form.fields['node_group'] = forms.ChoiceField(choices = form_ngs)
        form.fields['netw'] = forms.ChoiceField(choices = form_netw)
        form.fields['vgs'] = forms.ChoiceField(choices = form_vgs)
        form.fields['disk_template'] = forms.ChoiceField(choices = form_dt)
        if form.is_valid():
            application = form.save(commit=False)
            if "reject" in request.POST:
                application.status = STATUS_REFUSED
                application.save()
                mail_body = render_to_string("application_rejected_mail.txt",
                                             {"application": application})
                send_mail(EMAIL_SUBJECT_PREFIX + "Application for %s rejected" %
                          application.hostname,
                          mail_body, SERVER_EMAIL,
                          [application.applicant.email])
                messages.add_message(request, messages.INFO,
                                     "Application #%d rejected, user %s has"
                                     " been notified" % (app.pk, request.user))
            else:
                application.status = STATUS_APPROVED
                application.instance_params = {
                                               'cluster': Cluster.objects.get(pk=form.cleaned_data['cluster']).slug,
                                               'network': form.cleaned_data['netw'].split("::")[0],
                                               'mode': form.cleaned_data['netw'].split("::")[1],
                                               'node_group': form.cleaned_data['node_group'],
                                               'vgs': form.cleaned_data['vgs'],
                                               'disk_template': form.cleaned_data['disk_template'], 
                                               }
                application.save()
                application.submit()
                messages.add_message(request, messages.INFO,
                                     "Application #%d accepted and submitted"
                                     " to %s" % (app.pk, application.cluster))
            cache.delete('pendingapplications')
            return HttpResponseRedirect(urlresolvers.reverse("application-list"))
        else:
            return render_to_response('review.html',
                                      {'application': app,
                                       'applications': applications,
                                       'appform': form,
                                       'fast_clusters': fast_clusters},
                                      context_instance=RequestContext(request))

@permission_required("apply.change_instanceapplication")
def get_nodegroups_fromnet(request):
    network_id = request.GET.get('network_id', '')
    try:
        cluster = Network.objects.get(pk=network_id).cluster
    except Network.DoesNotExist:
        cluster = None
    if cluster:
        nodegroups = cluster.get_node_groups()
    nodegroups_list = []
    for g in nodegroups:
        nodeg_dict = {}
        nodeg_dict['name'] = g['name']
        nodegroups_list.append(nodeg_dict)
    return HttpResponse(json.dumps(nodegroups_list), mimetype='application/json')

@permission_required("apply.change_instanceapplication")
def get_groupnets_fromcluster(request):
    cluster_id = request.GET.get('cluster_id', '')
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
    except Cluster.DoesNotExist:
        return HttpResponse(json.dumps({'response':'Error. Cluster does not exist!'}), mimetype='application/json')
    if cluster:
        nodegroups = cluster.get_node_groups()
    nodegroups_list = []
    for g in nodegroups:
        nodeg_dict = {}
        nodeg_dict['name'] = g['name']
        nodegroups_list.append(nodeg_dict)
    return HttpResponse(json.dumps(nodegroups_list), mimetype='application/json')

@permission_required("apply.change_instanceapplication")
def get_cluster_node_group_stack(request):
    cluster_id = request.GET.get('cluster_id', '')
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
    except Cluster.DoesNotExist:
        return HttpResponse(json.dumps({'response':'Error. Cluster does not exist!'}), mimetype='application/json')
    cluster_info = cluster.get_cluster_info()
    res = {}
    res['slug'] = cluster.slug
    res['cluster_id'] = cluster.pk
    res['description'] = cluster.description
    res['disk_templates'] = cluster_info['enabled_disk_templates']
    res['node_groups'] = cluster.get_node_group_stack()
    return HttpResponse(json.dumps(res), mimetype='application/json')

@login_required
def user_keys(request):
    msg = None
    if request.method == "GET":
        form = SshKeyForm()
    else:
        form = SshKeyForm(request.POST)
        if form.is_valid():
            dups = []
            for key_type, key, comment in form.cleaned_data["ssh_pubkey"]:
                ssh_key = SshPublicKey(key_type=key_type, key=key,
                                       comment=comment, owner=request.user)
                fprint = ssh_key.compute_fingerprint()
                other_keys = SshPublicKey.objects.filter(owner=request.user,
                                                         fingerprint=fprint)
                if not other_keys:
                    ssh_key.fingerprint = fprint
                    ssh_key.save()
                    form = SshKeyForm()
                else:
                    dups.append(fprint)
            if dups:
                msg = _("The following keys were skipped because"
                        " they already exist:<br />%s") % "<br />".join(dups)
                msg = mark_safe(msg)

    keys = SshPublicKey.objects.filter(owner=request.user)
    return render_to_response('user_keys.html',
                              {'form': form, 'keys': keys, 'msg': msg},
                              context_instance=RequestContext(request))


@login_required
def delete_key(request, key_id):
    key = get_object_or_404(SshPublicKey, pk=key_id)
    if key.owner != request.user:
        t = get_template("403.html")
        return HttpResponseForbidden(content=t.render(RequestContext(request)))
    key.delete()
    return HttpResponseRedirect(urlresolvers.reverse("user-keys"))


@login_required
def profile(request):
        return render_to_response("profile.html", context_instance=RequestContext(request))


@login_required
def mail_change(request):
    changed = False
    pending = False
    usermail = request.user.email
    if request.method == "GET":
        form = EmailChangeForm()
        pending = check_mail_change_pending(request.user)
    elif request.method == "POST":
        form = EmailChangeForm(request.POST)
        if form.is_valid():
            usermail = form.cleaned_data['email1']
            user = User.objects.get(username=request.user)
            if user.email:
                mailchangereq = InstanceAction.objects.create_action(request.user, '', None, 4, usermail)
                fqdn = Site.objects.get_current().domain
                url = "https://%s%s" % \
                    (fqdn,
                     reverse("reinstall-destroy-review",
                     kwargs={'application_hash': mailchangereq.activation_key, 'action_id':4}
                     )
                )
                email = render_to_string("reinstall_mail.txt",
                                         {"user": request.user,
                                          "action": mailchangereq.get_action_display(),
                                          "action_value": mailchangereq.action_value,
                                          "url": url})
                send_mail("%sUser email change requested" % (EMAIL_SUBJECT_PREFIX),
                  email, SERVER_EMAIL, [request.user.email])
                pending = True
            else:
                user.email = usermail
                user.save()
                changed = True
                form = EmailChangeForm()
    return render_to_response("mail_change.html", {'mail':usermail, 'form':form, 'changed':changed, 'pending': pending}, context_instance=RequestContext(request))

def check_mail_change_pending(user):
    actions = []
    pending_actions = InstanceAction.objects.filter(applicant=user, action=4)
    for pending in pending_actions:
        if pending.activation_key_expired():
            continue
        actions.append(pending)
    if len(actions) == 0:
        return False
    elif len(actions) == 1:
        return True
    else:
        return False

@login_required
def name_change(request):
    changed = False
    user_full_name = request.user.get_full_name()
    if request.method == "GET":
        form = NameChangeForm()
    elif request.method == "POST":
        form = NameChangeForm(request.POST)
        if form.is_valid():
            user_name = form.cleaned_data['name']
            user_surname = form.cleaned_data['surname']
            user = User.objects.get(username=request.user)
            user.first_name = user_name
            user.last_name = user_surname
            user.save()
            changed = True
            user_full_name = user.get_full_name()
            form = NameChangeForm()
    return render_to_response("name_change.html", {'name':user_full_name, 'form':form, 'changed':changed}, context_instance=RequestContext(request))

def instance_ssh_keys(request, application_id, cookie):
    app = get_object_or_404(InstanceApplication, pk=application_id)
    if cookie != app.cookie:
        t = get_template("403.html")
        return HttpResponseForbidden(content=t.render(RequestContext(request)))

    output = StringIO()
    output.writelines([k.key_line() for k in
                       app.applicant.sshpublickey_set.all()])
    return HttpResponse(output.getvalue(), mimetype="text/plain")

@login_required
def pass_notify(request):
    user = User.objects.get(username=request.user)
    up = user.get_profile().force_logout()
    if user.email:
        fqdn = Site.objects.get_current().domain
        email = render_to_string("pass_change_notify_mail.txt",
                                 {"user": request.user})
        send_mail("%sUser password change" % (EMAIL_SUBJECT_PREFIX),
          email, SERVER_EMAIL, [request.user.email])
        return HttpResponse("mail sent", mimetype="text/plain")
    else:
        return HttpResponse("mail not sent", mimetype="text/plain")


