import re
import base64

from paramiko import RSAKey, DSSKey, SSHException

from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.template.defaultfilters import filesizeformat

from ganetimgr.apply.models import *


_VALID_NAME_RE = re.compile("^[a-z0-9.-]{1,255}$") # taken from ganeti

VALID_MEMORY_VALUES = ['512', '768', '1024', '1500', '2048', '3072', '4096']

MEMORY_CHOICES = [(m, filesizeformat(int(m) * 1024**2))
                  for m in VALID_MEMORY_VALUES]


class InstanceForm(forms.ModelForm):
    hostname = forms.CharField(help_text=ugettext_lazy("A fully qualified domain name,"
                                         " e.g. host.domain.com"), label=ugettext_lazy("Hostname"))
    memory = forms.ChoiceField(choices=MEMORY_CHOICES, label=ugettext_lazy("Memory"))
    vcpus = forms.ChoiceField(choices=[(x, x) for x in range(1, 5)],
                               label="Virtual CPUs")
    disk_size = forms.IntegerField(min_value=2, max_value=100,
                                   initial=5, label=ugettext_lazy("Disk size (GB)"),
                                   help_text=ugettext_lazy("Specify a size from 2 to 100 GB"))
    hosts_mail_server = forms.BooleanField(required=False,
                                           help_text=ugettext_lazy("Check this option if"
                                                     " the virtual machine"
                                                     " will be sending"
                                                     " e-mail"), label=ugettext_lazy("Hosts mail server"))
    organization = forms.ModelChoiceField(queryset=Organization.objects.all(), required=False,
                   label=ugettext_lazy("Organization"))

    class Meta:
        model = InstanceApplication
        fields = ('hostname', 'memory', 'vcpus', 'disk_size',
                  'organization', 'hosts_mail_server',
                  'operating_system', 'network')

    def clean_hostname(self):
        hostname = self.cleaned_data["hostname"].rstrip(".")

        # Check copied from ganeti's code
        if (not _VALID_NAME_RE.match(hostname) or
            # double-dots, meaning empty label
            ".." in hostname or
            # empty initial label
            hostname.startswith(".")):
            raise forms.ValidationError(_("Invalid hostname %s") % hostname)

        if not hostname.count("."):
            # We require at least two DNS labels
            raise forms.ValidationError(mark_safe(_("Hostname should be fully"
                                                    " qualified, e.g. <em>host"
                                                    ".domain.com</em>, not"
                                                    " <em>host</em>")))
        return hostname


class InstanceApplicationForm(InstanceForm):
    comments = forms.CharField(widget=forms.Textarea, required=True,
                               help_text=ugettext_lazy("Additional comments you would like"
                                         " the service administrators to see"), label=ugettext_lazy("Comments"))
    accept_tos = forms.BooleanField()

    class Meta:
        model = InstanceApplication
        fields = InstanceForm.Meta.fields + ('admin_contact_name',
                                             'admin_contact_email',
                                             'admin_contact_phone',
                                             'comments')

    def clean(self):
        super(InstanceApplicationForm, self).clean()

        organization = self.cleaned_data.get("organization", None)

        if not (organization or
                (self.cleaned_data.get("admin_contact_name", None) and
                 self.cleaned_data.get("admin_contact_email", None) and
                 self.cleaned_data.get("admin_contact_phone", None))):
            raise forms.ValidationError(_("Choose either an organization or"
                                          " fill in the contact information"))
        return self.cleaned_data


class InstanceApplicationReviewForm(InstanceForm):
    memory = forms.IntegerField(min_value=512, initial=1024)
    vcpus = forms.IntegerField(min_value=1, initial=1, label="Virtual CPUs")
    disk_size = forms.IntegerField(min_value=2, initial=5,
                                   label=ugettext_lazy("Disk size (GB)"))
    class Meta:
        model = InstanceApplication
        fields = InstanceForm.Meta.fields + ('admin_comments',)

    def clean_network(self):
        if self.cleaned_data["network"] is None:
            if self.data and "reject" not in self.data:
                raise forms.ValidationError(_("Please specify a network"))
        return self.cleaned_data["network"]

    def clean_admin_comments(self):
        if self.data and "reject" in self.data and not \
            self.cleaned_data["admin_comments"]:
            raise forms.ValidationError(_("Please specify a reason for"
                                        " rejection"))
        return self.cleaned_data["admin_comments"]

    def clean(self):
        if not self.instance.is_pending:
            raise forms.ValidationError(_("Application already handled"))
        return self.cleaned_data


class SshKeyForm(forms.Form):
    ssh_pubkey = forms.CharField(widget=forms.Textarea)

    def clean_ssh_pubkey(self):
        keydata = self.cleaned_data["ssh_pubkey"].strip()
        keys = keydata.splitlines()
        if not keys:
            return keys

        pubkeys = []
        for pubkey in keys:
            if not pubkey:
                continue

            fields = pubkey.split(None, 2)
            if len(fields) < 2:
                raise forms.ValidationError(_("Malformed SSH key, must be in"
                                            " OpenSSH format, RSA or DSA"))

            key_type = fields[0].strip().lower()
            key = fields[1].strip()
            try:
                comment = fields[2].strip()
            except IndexError:
                comment = None

            try:
                data = base64.b64decode(key)
            except TypeError:
                raise forms.ValidationError(_("Malformed SSH key"))

            if key_type == "ssh-rsa":
                try:
                    pkey = RSAKey(data=data)
                except SSHException:
                    raise forms.ValidationError(_("Invalid RSA SSH key"))
            elif key_type == "ssh-dss":
                try:
                    pkey = DSSKey(data=data)
                except SSHException:
                    raise forms.ValidationError(_("Invalid DSS SSH key"))
            else:
                raise forms.ValidationError(_("Unknown key type '%s'") % fields[0])

            pubkeys.append((key_type, key, comment))

        return pubkeys


class EmailChangeForm(forms.Form):
    email1 = forms.EmailField(label=ugettext_lazy("Email"), required=True)
    email2 = forms.EmailField(label=ugettext_lazy("Email (verify)"), required=True)

    def clean(self):
        cleaned_data = self.cleaned_data
        email1 = cleaned_data.get("email1")
        email2 = cleaned_data.get("email2")
        if email1 and email2:
            if email1 != email2:
                raise forms.ValidationError(_("Mail fields do not match."))
        return cleaned_data

class NameChangeForm(forms.Form):
    name = forms.CharField(label=ugettext_lazy("Name"), max_length=50, min_length = 2,required=True)
    surname = forms.CharField(label=ugettext_lazy("Surname"), max_length=50, min_length = 2, required=True)
