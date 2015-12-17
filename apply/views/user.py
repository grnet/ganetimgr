import datetime
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib.sites.models import Site
from django.contrib import messages
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.http import (
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponse,
    HttpResponseBadRequest
)
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string, get_template
from django.template.context import RequestContext
from django.utils.safestring import mark_safe

from django.utils.translation import ugettext_lazy as _

from ganeti.models import InstanceAction

from apply.forms import (
    EmailChangeForm,
    NameChangeForm,
    SshKeyForm,
    OrganizationPhoneChangeForm
)
from apply.utils import check_mail_change_pending
from apply.models import SshPublicKey


if 'oauth2_provider' in settings.INSTALLED_APPS:
    from oauth2_provider.decorators import protected_resource

    @protected_resource()
    def detail_api(request):
        '''
        This view a username and a password and
        returns the user's instances,
        if the credentials are valid.
        '''
        from oauth2_provider.models import AccessToken
        token = get_object_or_404(AccessToken, token=request.GET.get('access_token'))
        user = token.user
        return HttpResponse(
            json.dumps(
                {
                    'username': user.username,
                    'email': user.email,
                    'id': user.pk,
                }
            ),
            content_type='application/json'
        )
else:
    def detail_api(request):
        raise NotImplementedError(
            'Please install oauth2_toolkit.'
            'For more details take a look at admin section of the docs.'
        )


@login_required
def user_info(request, type, usergroup):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        usergroup_info = None
        if type == 'user':
            usergroup_info = get_object_or_404(User, username=usergroup)
        elif type == 'group':
            usergroup_info = get_object_or_404(Group, name=usergroup)
        if usergroup_info:
            return render(
                request,
                'users/user_info.html',
                {'usergroup': usergroup_info, 'type': type}
            )
        else:
            return HttpResponseBadRequest('Bad request')
    else:
        return HttpResponseRedirect(reverse('user-instances'))


@login_required
def idle_accounts(request):
    if (
        request.user.is_superuser or
        request.user.has_perm('ganeti.view_instances')
    ):
        idle_users = []
        idle_users.extend([
            u for u in User.objects.filter(
                is_active=True,
                last_login__lte=datetime.datetime.now() - datetime.timedelta(
                    days=int(settings.IDLE_ACCOUNT_NOTIFICATION_DAYS)
                )
            ) if u.email
        ])
        idle_users = list(set(idle_users))
        return render(
            request,
            'users/idle_accounts.html',
            {'users': idle_users},
        )
    else:
        t = get_template("403.html")
        return HttpResponseForbidden(content=t.render(RequestContext(request)))


@login_required
def profile(request):
    return render(
        request,
        'users/profile.html',
        {}
    )


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
                mailchangereq = InstanceAction.objects.create_action(
                    request.user,
                    '',
                    None,
                    4,
                    usermail
                )
                fqdn = Site.objects.get_current().domain
                url = "https://%s%s" % (
                    fqdn,
                    reverse(
                        "reinstall-destroy-review",
                        kwargs={
                            'application_hash': mailchangereq.activation_key,
                            'action_id': 4
                        }
                    )
                )
                email = render_to_string(
                    "instances/emails/reinstall_mail.txt",
                    {
                        "user": request.user,
                        "action": mailchangereq.get_action_display(),
                        "action_value": mailchangereq.action_value,
                        "url": url
                    }
                )
                send_mail(
                    "%sUser email change requested" % (
                        settings.EMAIL_SUBJECT_PREFIX
                    ),
                    email,
                    settings.SERVER_EMAIL,
                    [request.user.email]
                )
                pending = True
            else:
                user.email = usermail
                user.save()
                changed = True
                form = EmailChangeForm()
    return render(
        request,
        "users/mail_change.html",
        {
            'mail': usermail,
            'form': form,
            'changed': changed,
            'pending': pending
        }
    )


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
    return render(
        request,
        'users/name_change.html',
        {
            'name': user_full_name,
            'form': form,
            'changed': changed
        }
    )


@login_required
def other_change(request):
    changed = False
    if request.method == "GET":
        form = OrganizationPhoneChangeForm(instance=request.user.userprofile)
    elif request.method == "POST":
        form = OrganizationPhoneChangeForm(request.POST, instance=request.user.userprofile)
        if form.is_valid():
            form.save()
            changed = True
    return render(
        request,
        'users/other_change.html',
        {
            'form': form,
            'changed': changed
        }
    )


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
    return render(
        request,
        'users/user_keys.html',
        {
            'form': form,
            'keys': keys,
            'msg': msg
        }
    )


@login_required
def delete_key(request, key_id):
    key = get_object_or_404(SshPublicKey, pk=key_id)
    if key.owner != request.user:
        t = get_template("403.html")
        return HttpResponseForbidden(content=t.render(RequestContext(request)))
    key.delete()
    return HttpResponseRedirect(reverse("user-keys"))


@login_required
def pass_notify(request):
    user = User.objects.get(username=request.user)
    messages.add_message(request, messages.INFO, _('Password changed!'))
    user.userprofile.force_logout()
    if user.email:
        email = render_to_string(
            "users/emails/pass_change_notify_mail.txt",
            {
                "user": request.user,
                "service_title": settings.BRANDING.get('TITLE'),
                "provider": settings.BRANDING.get('SERVICE_PROVIDED_BY').get('NAME'),
            }
        )
        send_mail(
            "%sUser password change" % (settings.EMAIL_SUBJECT_PREFIX),
            email,
            settings.SERVER_EMAIL,
            [request.user.email]
        )
        return HttpResponse("mail sent", content_type="text/plain")
    else:
        return HttpResponse("mail not sent", content_type="text/plain")
