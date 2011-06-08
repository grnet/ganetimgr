import re
import base64
from paramiko import RSAKey, DSSKey, SSHException

from django import forms
from django.core import urlresolvers
from django.core.mail import mail_admins
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.template.loader import render_to_string, get_template
from django.template.defaultfilters import filesizeformat
from django.contrib.auth.decorators import login_required
from ganetimgr.apply.models import *


_VALID_NAME_RE = re.compile("^[a-z0-9._-]{1,255}$") # taken from ganeti

VALID_MEMORY_VALUES = ['512', '768', '1024', '1500', '2048', '3072', '4096']

MEMORY_CHOICES = [(m, filesizeformat(int(m) * 1024**2))
                  for m in VALID_MEMORY_VALUES]


class InstanceApplicationForm(forms.ModelForm):
    memory = forms.ChoiceField(choices=MEMORY_CHOICES)
    vcpus = forms.ChoiceField(choices=[(x, x) for x in range(1,5)],
                               label="Virtual CPUs")
    disk_size = forms.IntegerField(min_value=2, max_value=100,
                                   initial=5, label="Disk size (GB)")

    class Meta:
        model = InstanceApplication
        fields = ('hostname', 'memory', 'vcpus', 'disk_size',
                  'organization', 'hosts_mail_server',
                  'operating_system')

    def clean_hostname(self):
        hostname = self.cleaned_data["hostname"]

        # Check copied from ganeti's code
        if (not _VALID_NAME_RE.match(hostname) or
            # double-dots, meaning empty label
            ".." in hostname or
            # empty initial label
            hostname.startswith(".")):
            raise forms.ValidationError("Invalid hostname %s" % hostname)
        return hostname


class SshKeyForm(forms.Form):
    ssh_pubkey = forms.CharField(widget=forms.Textarea)

    def clean_ssh_pubkey(self):
        pubkey = self.cleaned_data["ssh_pubkey"].strip()
        if not pubkey:
            return pubkey

        fields = pubkey.split(None, 2)
        if len(fields) < 2:
            raise forms.ValidationError("Malformed SSH key, must be in"
                                        " OpenSSH format, RSA or DSA")

        key_type = fields[0].strip().lower()
        key = fields[1].strip()
        try:
            comment = fields[2].strip()
        except IndexError:
            comment = None

        try:
            data = base64.b64decode(key)
        except TypeError:
            raise forms.ValidationError("Malformed SSH key")

        if key_type == "ssh-rsa":
            try:
                pkey = RSAKey(data=data)
            except SSHException:
                raise forms.ValidationError("Invalid RSA SSH key")
        elif key_type == "ssh-dss":
            try:
                pkey = DSSKey(data=data)
            except SSHException:
                raise forms.ValidationError("Invalid DSS SSH key")
        else:
            raise forms.ValidationError("Unknown key type '%s'" % fields[0])

        return [key_type, key, comment]


@login_required
def apply(request):
    user_organizations = request.user.organization_set.all()
    InstanceApplicationForm.base_fields["organization"] = \
        forms.ModelChoiceField(queryset=user_organizations)

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
            admin_url = request.build_absolute_uri(
                urlresolvers.reverse("admin:apply_instanceapplication_changelist"))
            mail_body = render_to_string("apply_mail.txt",
                                         {"form": form,
                                          "user": request.user,
                                          "url": admin_url})
            mail_admins("New instance request by %s: %s" %
                        (request.user, application.hostname),
                        mail_body)
            return render_to_response('apply_success.html',
                                      context_instance=RequestContext(request))
        else:
            return render_to_response('apply.html', {'form': form},
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
                msg = "A key with the same fingerprint exists: %s" % fprint

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
