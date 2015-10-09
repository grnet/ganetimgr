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

from django.conf import settings


def settings_vars(context):
    # return the value you want as a dictionary. you may add multiple
    # values in there. Also check if these values exist in settings.py

    return {
        'HELPDESK_INTEGRATION_JAVASCRIPT_URL': settings.HELPDESK_INTEGRATION_JAVASCRIPT_URL if hasattr(settings, 'HELPDESK_INTEGRATION_JAVASCRIPT_URL') else '',
        'HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS': settings.HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS if hasattr(settings, 'HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS') else '',
        'VERSION': settings.SW_VERSION if hasattr(settings, 'SW_VERSION') else '',
        'FEED_URL': settings.FEED_URL if hasattr(settings, 'FEED_URL') else '',
        'WEBSOCK_VNC_ENABLED': settings.WEBSOCK_VNC_ENABLED if hasattr(settings, 'WEBSOCK_VNC_ENABLED') else '',
        'BRANDING': settings.BRANDING if hasattr(settings, 'BRANDING') else '',
        'FLATPAGES': settings.FLATPAGES if hasattr(settings, 'FLATPAGES') else '',
        'COLLECTD_URL': settings.COLLECTD_URL if hasattr(settings, 'COLLECTD_URL') else ''
    }
