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
import socket
import re
import urllib2

from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.utils.safestring import mark_safe
from django.conf import settings
from ganeti.models import Instance, Cluster
from ipaddr import IPNetwork

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


class InstanceConfigForm(forms.Form):
    nic_type = forms.ChoiceField(label=ugettext_lazy("Network adapter model"),
                                 choices=(('paravirtual', 'Paravirtualized'),
                                          ('rtl8139', 'Realtek 8139+'),
                                          ('e1000', 'Intel PRO/1000'),
                                          ('ne2k_pci', 'NE2000 PCI')))

    disk_type = forms.ChoiceField(label=ugettext_lazy("Hard disk type"),
                                  choices=(('paravirtual', 'Paravirtualized'),
                                           ('scsi', 'SCSI'),
                                           ('ide', 'IDE')))

    boot_order = forms.ChoiceField(label=ugettext_lazy("Boot device"),
                                   choices=(('disk', 'Hard disk'),
                                            ('cdrom', 'CDROM')))

    cdrom_type = forms.ChoiceField(label=ugettext_lazy("CD-ROM Drive"),
                                   choices=(('none', 'Disabled'),
                                            ('iso',
                                             'ISO Image over HTTP (see below)')),
                                   widget=forms.widgets.RadioSelect())

    cdrom_image_path = forms.CharField(required=False,
                                       label=ugettext_lazy("ISO Image URL (http)"))

    use_localtime = forms.BooleanField(
        label=ugettext_lazy(
            "Hardware clock uses local time"
            " instead of UTC"
        ),
        required=False
    )
    whitelist_ip = forms.CharField(
        required=False,
        label=ugettext_lazy("Allow From"),
        help_text="If isolated, allow access from v4/v6 address/network"
    )

    def clean_cdrom_image_path(self):
        data = self.cleaned_data['cdrom_image_path']
        if data:
            if not (data == 'none' or re.match(r'(https?|ftp)://', data)):
                raise forms.ValidationError(_('Only HTTP URLs are allowed'))

            elif data != 'none':
                # Check if the image is there
                oldtimeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(5)
                try:
                    urllib2.urlopen(data)
                    socket.setdefaulttimeout(oldtimeout)
                except ValueError:
                    socket.setdefaulttimeout(oldtimeout)
                    raise forms.ValidationError(
                        _('%(url)s is not a valid URL') % {'url': data}
                    )
                except:  # urllib2 HTTP errors
                    socket.setdefaulttimeout(oldtimeout)
                    raise forms.ValidationError(_('Invalid URL'))
        return data

    def clean_whitelist_ip(self):
        data = self.cleaned_data['whitelist_ip']
        if data:
            try:
                address = IPNetwork(data)
                if address.version == 4:
                    if address.prefixlen < settings.WHITELIST_IP_MAX_SUBNET_V4:
                        error = _(
                            "Currently no prefix lengths < %s are allowed"
                        ) % settings.WHITELIST_IP_MAX_SUBNET_V4
                        raise forms.ValidationError(error)
                if address.version == 6:
                    if address.prefixlen < settings.WHITELIST_IP_MAX_SUBNET_V6:
                        error = _(
                            "Currently no prefix lengths < %s are allowed"
                        ) % settings.WHITELIST_IP_MAX_SUBNET_V6
                        raise forms.ValidationError(error)
                if address.is_unspecified:
                    raise forms.ValidationError('Address is unspecified')
            except ValueError:
                raise forms.ValidationError(
                    _(
                        '%(address)s is not a valid address'
                    ) % {'address': data}
                )
            data = address.compressed
        return data
