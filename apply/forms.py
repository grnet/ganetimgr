# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import re
import base64

from paramiko import RSAKey, DSSKey, SSHException

from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.template.defaultfilters import filesizeformat

from apply.models import *
from ganeti.models import Instance, Cluster
from django.forms.models import ModelChoiceIterator, ModelChoiceField
from itertools import groupby
from django.forms.widgets import Select
from django.utils.encoding import force_unicode
from django.utils.html import escape, conditional_escape
from accounts.models import UserProfile
from django.conf import settings

BRANDING = settings.BRANDING

# Taken from ganeti and patched to avoid non-bind9 friendly VM names
_VALID_NAME_RE = re.compile("^[a-z0-9.-]{1,255}$")

VALID_MEMORY_VALUES = [512, 768, 1024, 1500, 2048, 3072, 4096]

MEMORY_CHOICES = [
    (
        str(m),
        filesizeformat(m * 1024 ** 2)
    )
    for m in VALID_MEMORY_VALUES
]


class GroupedModelChoiceField(ModelChoiceField):
    def __init__(
        self,
        group_by_field,
        disabled_field=False,
        group_label=None,
        *args,
        **kwargs
    ):
        """
        group_by_field is the name of a field on the model
        group_label is a function to return a label for each choice group
        """
        super(GroupedModelChoiceField, self).__init__(*args, **kwargs)
        self.group_by_field = group_by_field
        self.disabled_field = disabled_field
        if group_label is None:
            self.group_label = lambda x: x
        else:
            self.group_label = group_label

    def _get_choices(self):
        """
        Exactly as per ModelChoiceField except returns new iterator class
        """
        if hasattr(self, '_choices'):
            return self._choices
        return GroupedModelChoiceIterator(self)
    choices = property(_get_choices, ModelChoiceField._set_choices)


class GroupedModelChoiceIterator(ModelChoiceIterator):
    def __iter__(self):
        if self.field.empty_label is not None:
            yield (u"", self.field.empty_label)
        if self.field.cache_choices:
            if self.field.choice_cache is None:
                self.field.choice_cache = [
                    (
                        self.field.group_label(group),
                        [self.choice(ch) for ch in choices]
                    )
                    for group, choices in groupby(
                        self.queryset.all(),
                        key=lambda row: getattr(row, self.field.group_by_field)
                    )
                ]
            for choice in self.field.choice_cache:
                yield choice
        else:
            for group, choices in groupby(
                self.queryset.all(),
                key=lambda row: getattr(row, self.field.group_by_field)
            ):
                yield (
                    self.field.group_label(group),
                    [
                        [
                            self.choice(ch)[0],
                            {
                                'label': self.choice(ch)[1],
                                'disabled': getattr(
                                    group,
                                    self.field.disabled_field
                                )
                            }
                        ] for ch in choices
                    ]
                )


class SelectWithDisabled(Select):
    """
    Subclass of Django's select widget that allows disabling options.
    To disable an option, pass a dict instead of a string for its label,
    of the form: {'label': 'option label', 'disabled': True}
    """
    def render_option(self, selected_choices, option_value, option_label):
        option_value = force_unicode(option_value)
        if (option_value in selected_choices):
            selected_html = u' selected="selected"'
        else:
            selected_html = ''
        disabled_html = ''
        if isinstance(option_label, dict):
            if dict.get(option_label, 'disabled'):
                disabled_html = u' disabled="disabled"'
            option_label = option_label['label']
        return u'<option value="%s"%s%s>%s</option>' % (
            escape(option_value), selected_html, disabled_html,
            conditional_escape(force_unicode(option_label)))


class InstanceForm(forms.ModelForm):
    hostname = forms.CharField(help_text=ugettext_lazy(
        "A fully qualified domain name,"
        " e.g. host.domain.com"
    ), label=ugettext_lazy("Hostname"))
    memory = forms.ChoiceField(
        choices=MEMORY_CHOICES,
        label=ugettext_lazy("Memory")
    )
    vcpus = forms.ChoiceField(
        choices=[
            (x, x) for x in range(1, 5)
        ],
        label="Virtual CPUs"
    )
    disk_size = forms.IntegerField(
        min_value=2,
        max_value=50,
        initial=5,
        label=ugettext_lazy("Disk size (GB)"),
        help_text=ugettext_lazy("Specify a size from 2 to 50 GB")
    )
    hosts_mail_server = forms.BooleanField(
        required=False,
        help_text=ugettext_lazy(
            "Check this option if  the virtual machine will be sending e-mail"
        ),
        label=ugettext_lazy("Hosts mail server")
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        label=ugettext_lazy("Organization")
    )
    operating_system = forms.CharField(
        label=ugettext_lazy("Operating System"),
        widget=forms.Select
    )

    class Meta:
        model = InstanceApplication
        fields = ('hostname', 'memory', 'vcpus', 'disk_size',
                  'organization', 'hosts_mail_server',)

    def clean_hostname(self):
        hostname = self.cleaned_data["hostname"].rstrip(".").lower()

        # Check copied from ganeti's code
        if (
            not _VALID_NAME_RE.match(hostname) or
            # double-dots, meaning empty label
            ".." in hostname or
            # empty initial label
            hostname.startswith(".")
        ):
            raise forms.ValidationError(_("Invalid hostname %s") % hostname)

        if not hostname.count("."):
            # We require at least two DNS labels
            raise forms.ValidationError(mark_safe(_("Hostname should be fully"
                                                    " qualified, e.g. <em>host"
                                                    ".domain.com</em>, not"
                                                    " <em>host</em>")))
        existing_instances = Instance.objects.all()
        pending_instances = InstanceApplication.objects.all()
        names_pending = [j.hostname for j in pending_instances if j.is_pending()]
        names = [i.name for i in existing_instances]
        reserved_names = names + names_pending
        if hostname in reserved_names:
            raise forms.ValidationError(_("Hostname already exists."))
        return hostname


class InstanceApplicationForm(InstanceForm):
    comments = forms.CharField(
        widget=forms.Textarea,
        required=True,
        help_text=ugettext_lazy(
            "Additional comments you would like"
            " the service administrators to see"
        ),
        label=ugettext_lazy("Comments")
    )
    accept_tos = forms.BooleanField()

    class Meta:
        model = InstanceApplication
        fields = InstanceForm.Meta.fields + ('admin_contact_name',
                                             'admin_contact_email',
                                             'admin_contact_phone',
                                             'comments')

    def clean(self):
        super(InstanceApplicationForm, self).clean()

        if (
            BRANDING.get('SHOW_ORGANIZATION_FORM', False) and
            BRANDING.get('SHOW_ADMINISTRATIVE_FORM', False)
        ):
            # if both forms are shown
            organization = self.cleaned_data.get('organization', False)
            if not (
                organization or
                self.cleaned_data.get("admin_contact_name", None) and
                self.cleaned_data.get("admin_contact_email", None) and
                self.cleaned_data.get("admin_contact_phone", None)
            ):
                raise forms.ValidationError(
                    _(
                        "Choose either an organization or"
                        " fill in the contact information"
                    )
                )
        elif (
            BRANDING.get('SHOW_ORGANIZATION_FORM', False) and not
            BRANDING.get('SHOW_ADMINISTRATIVE_FORM', False)
        ):
            # raise exception if there is no organization
            # and the administrative form is not shown
            organization = self.cleaned_data.get('organization', False)
            if not organization:
                raise forms.ValidationError(_("Choose an organization"))
        elif (
            BRANDING.get('SHOW_ADMINISTRATIVE_FORM', False) and not
            BRANDING.get('SHOW_ORGANIZATION_FORM', False)
        ):
            # if only administrative form is displayed
            if not (self.cleaned_data.get("admin_contact_name", None) and
                    self.cleaned_data.get("admin_contact_email", None) and
                    self.cleaned_data.get("admin_contact_phone", None)
                    ):
                raise forms.ValidationError(
                    _("Please fill in the contact information")
                )
        return self.cleaned_data


class InstanceApplicationReviewForm(InstanceForm):
    memory = forms.IntegerField(min_value=min(VALID_MEMORY_VALUES), initial=1024)
    vcpus = forms.IntegerField(min_value=1, initial=1, label="Virtual CPUs")
    disk_size = forms.IntegerField(min_value=2, initial=5,
                                   label=ugettext_lazy("Disk size (GB)"))
    cluster = forms.ChoiceField(
        choices=[('', 'Select')] + [
            (
                c.pk,
                "%s (%s)" % (c.description or c.hostname, c.slug)
            ) for c in Cluster.objects.exclude(
                disabled=True
            ).exclude(disable_instance_creation=True).order_by('description')
        ],
        label="Cluster",
        required=False
    )
    node_group = forms.ChoiceField(
        label="Node Group",
        required=False
    )
    netw = forms.ChoiceField(
        label="Network",
        required=False
    )
    vgs = forms.ChoiceField(
        label="Volume Groups",
        required=False
    )
    disk_template = forms.ChoiceField(
        label="Disk Template",
        required=False
    )

    class Meta:
        model = InstanceApplication
        fields = InstanceForm.Meta.fields + ('admin_comments',)

    def __init__(self, *args, **kwargs):
        super(InstanceApplicationReviewForm, self).__init__(*args, **kwargs)
        self.fields['cluster'].choices = self.get_clusters()

    def get_clusters(self):
        return [('', 'Select')] + [
            (
                c.pk,
                "%s (%s)" % (c.description or c.hostname, c.slug)
            ) for c in Cluster.objects.exclude(
                disabled=True
            ).exclude(disable_instance_creation=True).order_by('description')
        ]

    def clean_admin_comments(self):
        if (
            self.data and
            "reject" in self.data and not
            self.cleaned_data["admin_comments"]
        ):
            raise forms.ValidationError(
                _("Please specify a reason for rejection")
            )
        return self.cleaned_data["admin_comments"]

    def clean_cluster(self):
        if self.data and "reject" in self.data:
            return ''
        else:
            cluster = self.cleaned_data['cluster']
            if not cluster:
                raise forms.ValidationError(_("This field is required"))
            else:
                return cluster

    def clean_netw(self):
        if self.data and "reject" in self.data:
            return ''
        else:
            netw = self.cleaned_data['netw']
            if not netw:
                raise forms.ValidationError(_("This field is required"))
            else:
                return netw

    def clean_node_group(self):
        if self.data and "reject" in self.data:
            return ''
        else:
            node_group = self.cleaned_data['node_group']
            if not node_group:
                raise forms.ValidationError(_("This field is required"))
            else:
                return node_group

    def clean_disk_template(self):
        if self.data and "reject" in self.data:
            return ''
        else:
            disk_template = self.cleaned_data.get('disk_template')
            if not disk_template:
                raise forms.ValidationError(_("This field is required"))
            else:
                return disk_template

    def clean_hostname(self):
        hostname = self.cleaned_data["hostname"].rstrip(".").lower()
        if self.data and "reject" in self.data:
            return hostname
        # Check copied from ganeti's code
        if (
            not _VALID_NAME_RE.match(hostname) or
            # double-dots, meaning empty label
            ".." in hostname or
            # empty initial label
            hostname.startswith(".")
        ):
            raise forms.ValidationError(_("Invalid hostname %s") % hostname)

        if not hostname.count("."):
            # We require at least two DNS labels
            raise forms.ValidationError(mark_safe(_("Hostname should be fully"
                                                    " qualified, e.g. <em>host"
                                                    ".domain.com</em>, not"
                                                    " <em>host</em>")))
        existing_instances = Instance.objects.all()
        names = [i.name for i in existing_instances]
        if hostname in names:
            raise forms.ValidationError(_("Hostname already exists."))
        return hostname

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
    name = forms.CharField(
        label=ugettext_lazy("Name"),
        max_length=50,
        min_length=2,
        required=True
    )
    surname = forms.CharField(
        label=ugettext_lazy("Surname"),
        max_length=50,
        min_length=2,
        required=True
    )


class OrganizationPhoneChangeForm(forms.ModelForm):

    class Meta:
        model = UserProfile
        fields = ['organization', 'telephone']
