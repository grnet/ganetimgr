#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2012 Greek Research and Technology Network (GRNET S.A.)
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

from django.conf import settings

def settings_vars(context):
    # return the value you want as a dictionnary. you may add multiple values in there.
    return {
            'HELPDESK_INTEGRATION_JAVASCRIPT_URL': settings.HELPDESK_INTEGRATION_JAVASCRIPT_URL,
            'HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS': settings.HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS,
            'VERSION': settings.SW_VERSION,
            'FEED_URL': settings.FEED_URL,
            'WEBSOCK_VNC_ENABLED': settings.WEBSOCK_VNC_ENABLED,
            'BRANDING': settings.BRANDING,
            'FLATPAGES':settings.FLATPAGES,
            }
