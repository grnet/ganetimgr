from cStringIO import StringIO

from django import forms
from django.contrib import messages
from django.core import urlresolvers
from django.core.mail import send_mail, mail_managers
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.template.loader import render_to_string, get_template
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.sites.models import Site

from ganetimgr.apply.models import *
from ganetimgr.apply.forms import *
from ganetimgr.ganeti.models import Cluster, Network
from ganetimgr.settings import SERVICE_MAIL

from django.utils.translation import ugettext as _


@login_required
def apply(request):
    user_organizations = request.user.organization_set.all()
    user_networks = Network.objects.filter(groups__in=request.user.groups.all())
    InstanceApplicationForm.base_fields["organization"] = \
        forms.ModelChoiceField(queryset=user_organizations)

    if user_networks:
        InstanceApplicationForm.base_fields["network"] = \
            forms.ModelChoiceField(queryset=user_networks, required=False)
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
            application.save()
            fqdn = Site.objects.get_current().domain
            admin_url = "https://%s%s" % \
               (fqdn,
                urlresolvers.reverse("application-review",
                                     kwargs={"application_id": application.pk}))
            mail_body = render_to_string("apply_mail.txt",
                                         {"form": form,
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


@permission_required("apply.change_instanceapplication")
def application_list(request):
    applications = InstanceApplication.objects.all()
    pending = applications.filter(status=STATUS_PENDING)
    completed = applications.exclude(status=STATUS_PENDING)

    return render_to_response("application_list.html",
                              {'applications': applications,
                               'pending': pending,
                               'completed': completed},
                              context_instance=RequestContext(request))


@permission_required("apply.change_instanceapplication")
def review_application(request, application_id):
    app = get_object_or_404(InstanceApplication, pk=application_id)
    fast_clusters = Cluster.objects.filter(fast_create=True)

    if request.method == "GET":
        form = InstanceApplicationReviewForm(instance=app)
        return render_to_response('review.html',
                                  {'application': app,
                                   'appform': form,
                                   'fast_clusters': fast_clusters},
                                  context_instance=RequestContext(request))

    else:
        form = InstanceApplicationReviewForm(request.POST, instance=app)
        if form.is_valid():
            application = form.save(commit=False)
            if "reject" in request.POST:
                application.status = STATUS_REFUSED
                application.save()
                mail_body = render_to_string("application_rejected_mail.txt",
                                             {"application": application})
                send_mail("Application for %s rejected" % application.hostname,
                          mail_body, SERVICE_MAIL,
                          [application.applicant.email])
                messages.add_message(request, messages.INFO,
                                     "Application #%d rejected, user %s has"
                                     " been notified" % (app.pk, request.user))
            else:
                application.status = STATUS_APPROVED
                application.save()
                application.submit()
                messages.add_message(request, messages.INFO,
                                     "Application #%d accepted and submitted"
                                     " to %s" % (app.pk, application.cluster))
            return HttpResponseRedirect(urlresolvers.reverse("application-list"))
        else:
            return render_to_response('review.html',
                                      {'application': app,
                                       'appform': form,
                                       'fast_clusters': fast_clusters},
                                      context_instance=RequestContext(request))


@login_required
def user_keys(request):
    msg = None
    if request.method == "GET":
        form = SshKeyForm()
    else:
        form = SshKeyForm(request.POST)
        if form.is_valid():
            key_type, key, comment = form.cleaned_data["ssh_pubkey"]
            ssh_key = SshPublicKey(key_type=key_type, key=key, comment=comment,
                                   owner=request.user)
            fprint = ssh_key.compute_fingerprint()
            other_keys = SshPublicKey.objects.filter(fingerprint=fprint)
            if not other_keys:
                ssh_key.fingerprint = fprint
                ssh_key.save()
                form = SshKeyForm()
            else:
                msg = _("A key with the same fingerprint exists: %s") % fprint

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
    usermail = request.user.email
    if request.method == "GET":
        form = EmailChangeForm()
    elif request.method == "POST":
        form = EmailChangeForm(request.POST)
        if form.is_valid():
            usermail = form.cleaned_data['email1']
            user = User.objects.get(username=request.user)
            user.email = usermail
            user.save()
            changed = True
            form = EmailChangeForm()
    return render_to_response("mail_change.html", {'mail':usermail, 'form':form, 'changed':changed}, context_instance=RequestContext(request))


def instance_ssh_keys(request, application_id, cookie):
    app = get_object_or_404(InstanceApplication, pk=application_id)
    if cookie != app.cookie:
        t = get_template("403.html")
        return HttpResponseForbidden(content=t.render(RequestContext(request)))

    output = StringIO()
    output.writelines([k.key_line() for k in
                       app.applicant.sshpublickey_set.all()])
    return HttpResponse(output.getvalue(), mimetype="text/plain")
