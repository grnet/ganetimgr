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

from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.utils.safestring import mark_safe
from ganeti.models import Instance, Cluster

import re

_VALID_NAME_RE = re.compile("^[a-z0-9.-]{1,255}$")


class tagsForm(forms.Form):
    tags = forms.CharField(required=False, help_text=ugettext_lazy(
        "Type a username or group name"
    ))


class lockForm(forms.Form):
    lock = forms.BooleanField(required=False)


class isolateForm(forms.Form):
    isolate = forms.BooleanField(required=False)


class InstanceRenameForm(forms.Form):
    hostname = forms.CharField(
        help_text=ugettext_lazy(
            "A fully qualified domain name, e.g. host.domain.com"
        ),
        label=ugettext_lazy("Hostname")
    )

    def clean_hostname(self):
        hostname = self.cleaned_data["hostname"].rstrip(".")

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


class GraphForm(forms.Form):
    cluster = forms.ModelChoiceField(
        queryset=Cluster.objects.filter(disabled=False),
        empty_label=None
    )
    nodes = forms.CharField(required=False, widget=forms.widgets.HiddenInput())

