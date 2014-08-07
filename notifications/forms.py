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
from django.conf import settings
from django.core.mail import mail_managers
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy 
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_unicode

class MessageForm(forms.Form):
    subject = forms.CharField(max_length=100,label=ugettext_lazy("Subject"))
    message = forms.CharField(widget=forms.Textarea, label=ugettext_lazy("Body"))
    recipient_list = forms.CharField(label=ugettext_lazy("Recipients"))