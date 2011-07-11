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

from ganetimgr.apply.models import *
from ganetimgr.apply.forms import *
from ganetimgr.ganeti.models import Cluster, Network
from ganetimgr.settings import SERVER_EMAIL, EMAIL_SUBJECT_PREFIX

from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy


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
                send_mail(EMAIL_SUBJECT_PREFIX + "Application for %s rejected" %
                          application.hostname,
                          mail_body, SERVER_EMAIL,
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
