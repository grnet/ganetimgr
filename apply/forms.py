import re
import base64

from paramiko import RSAKey, DSSKey, SSHException

from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.template.defaultfilters import filesizeformat

from ganetimgr.apply.models import *


_VALID_NAME_RE = re.compile("^[a-z0-9._-]{1,255}$") # taken from ganeti

VALID_MEMORY_VALUES = ['512', '768', '1024', '1500', '2048', '3072', '4096']

MEMORY_CHOICES = [(m, filesizeformat(int(m) * 1024**2))
                  for m in VALID_MEMORY_VALUES]


class InstanceApplicationForm(forms.ModelForm):
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
                                                     " will be receiving"
                                                     " e-mail"), label=ugettext_lazy("Hosts mail server"))
    comments = forms.CharField(widget=forms.Textarea, required=False,
                               help_text=ugettext_lazy("Additional comments you would like"
                                         " the service administrators to see"), label=ugettext_lazy("Comments"))
    accept_tos = forms.BooleanField()
    organization = forms.ModelChoiceField(queryset=Organization.objects.all(), required=False,
                   label=ugettext_lazy("Organization"))

    class Meta:
        model = InstanceApplication
        fields = ('hostname', 'memory', 'vcpus', 'disk_size',
                  'organization', 'hosts_mail_server',
                  'operating_system', 'network',
                  'admin_contact_name', 'admin_contact_email',
                  'admin_contact_phone', 'comments')

    def clean_hostname(self):
        hostname = self.cleaned_data["hostname"]

        # Check copied from ganeti's code
        if (not _VALID_NAME_RE.match(hostname) or
            # double-dots, meaning empty label
            ".." in hostname or
            # empty initial label
            hostname.startswith(".")):
            raise forms.ValidationError(_("Invalid hostname %s") % hostname)
        return hostname

    def clean(self):
        super(InstanceApplicationForm, self).clean()

        organization = self.cleaned_data.get("organization", None)

        if not (organization or
                (self.cleaned_data["admin_contact_name"] and
                 self.cleaned_data["admin_contact_email"] and
                 self.cleaned_data["admin_contact_phone"] and
                 self.cleaned_data["comments"])):
            raise forms.ValidationError(_("Choose either an organization or"
                                          " fill in the contact information"))
        return self.cleaned_data


class InstanceApplicationReviewForm(InstanceApplicationForm):
    class Meta:
        model = InstanceApplication
        fields = InstanceApplicationForm.Meta.fields + ('admin_comments',)

    def clean_comments(self):
        return self.instance.comments

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
        pubkey = self.cleaned_data["ssh_pubkey"].strip()
        if not pubkey:
            return pubkey

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

        return [key_type, key, comment]


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
