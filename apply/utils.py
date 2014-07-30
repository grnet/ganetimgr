# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2014 Greek Research and Technology Network (GRNET S.A.)
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

import requests
from bs4 import BeautifulSoup
try:
    from ganetimgr.settings import OPERATING_SYSTEMS_URLS
except ImportError:
    OPERATING_SYSTEMS_URLS = False
try:
    from ganetimgr.settings import OPERATING_SYSTEMS
except ImportError:
    OPERATING_SYSTEMS = False

from ganetimgr.settings import OPERATING_SYSTEMS_PROVIDER, OPERATING_SYSTEMS_SSH_KEY_PARAM


def discover_available_operating_systems():
    if OPERATING_SYSTEMS_URLS:
        for url in OPERATING_SYSTEMS_URLS:
            raw_response = requests.get(url)
            if raw_response.ok:
                soup = BeautifulSoup(raw_response.text)
                operating_systems = {}
                extensions = {
                    '.tar.gz': 'tarball',
                    '.img': 'qemu',
                    '-root.dump': 'dump'
                }
                for link in soup.findAll('a'):
                    try:
                        extension = '.' + '.'.join(link.text.split('.')[-2:])
                    # in case of false link
                    except IndexError:
                        pass
                    else:
                        # if the file is tarball, qemu or dump then it is valid
                        if extension in extensions.keys() or '-root.dump' in link.text:
                            re = requests.get(url + link.text + '.dsc')
                            if re.ok:
                                name = re.text
                            else:
                                name = link.text
                            img_id = link.text.replace(extension, '').split('-x')[0]
                            description = name
                            img_format = extensions[extension]
                            operating_systems.update({
                                img_id: {
                                    'description': description,
                                    'provider': OPERATING_SYSTEMS_PROVIDER,
                                    'ssh_key_param': OPERATING_SYSTEMS_SSH_KEY_PARAM,
                                    'osparams': {
                                        'img_id': img_id,
                                        'img_format': img_format,
                                    }
                                }
                            })
            return operating_systems
        else:
            return {}


def get_operating_systems_dict():
    if OPERATING_SYSTEMS:
        return OPERATING_SYSTEMS
    else:
        return {}
