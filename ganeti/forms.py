#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2013 Greek Research and Technology Network (GRNET S.A.)
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

from django import forms
from django.conf import settings
from django.core.mail import mail_managers
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_unicode
from ganeti.models import Instance

import re

_VALID_NAME_RE = re.compile("^[a-z0-9.-]{1,255}$")

class tagsForm(forms.Form):
    tags = forms.CharField(required=False, help_text=ugettext_lazy("Type a username or group name"))

class lockForm(forms.Form):
    lock = forms.BooleanField(required=False)

class isolateForm(forms.Form):
    isolate = forms.BooleanField(required=False)

class InstanceRenameForm(forms.Form):
    hostname = forms.CharField(help_text=ugettext_lazy("A fully qualified domain name,"
                                         " e.g. host.domain.com"), label=ugettext_lazy("Hostname"))
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
        existing_instances = Instance.objects.all()
        names = [i.name for i in existing_instances]
        if hostname in names:
            raise forms.ValidationError(_("Hostname already exists."))
        return hostname

