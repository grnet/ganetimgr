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

import requests
from bs4 import BeautifulSoup
import json
from django.core.cache import cache
from requests.exceptions import ConnectionError

try:
    from ganetimgr.settings import OPERATING_SYSTEMS_URLS
except ImportError:
    OPERATING_SYSTEMS_URLS = False
else:
    from ganetimgr.settings import OPERATING_SYSTEMS_PROVIDER, OPERATING_SYSTEMS_SSH_KEY_PARAM

try:
    from ganetimgr.settings import OPERATING_SYSTEMS
except ImportError:
    OPERATING_SYSTEMS = False


def discover_available_operating_systems():
    operating_systems = {}
    if OPERATING_SYSTEMS_URLS:
        for url in OPERATING_SYSTEMS_URLS:
            try:
                raw_response = requests.get(url)
            except ConnectionError:
                # fail silently if url is unreachable
                break
            else:
                if raw_response.ok:
                    soup = BeautifulSoup(raw_response.text)
                    extensions = {
                        '.tar.gz': 'tarball',
                        '.img': 'qemu',
                        '-root.dump': 'dump'
                    }
                    architectures = ['-x86_', '-amd' '-i386']
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
                                for arch in architectures:
                                    if arch in link.text:
                                        img_id = link.text.replace(extension, '').split(arch)[0]
                                        architecture = arch
                                        break
                                description = name
                                img_format = extensions[extension]
                                operating_systems.update({
                                    img_id: {
                                        'description': description,
                                        'provider': OPERATING_SYSTEMS_PROVIDER,
                                        'ssh_key_param': OPERATING_SYSTEMS_SSH_KEY_PARAM,
                                        'arch': architecture,
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


def operating_systems():
    # check if results exist in cache
    response = cache.get('operating_systems')
    # if no items in cache
    if not response:
        discovery = discover_available_operating_systems()
        dictionary = get_operating_systems_dict()
        operating_systems = sorted(dict(discovery.items() + dictionary.items()).items())
        # move 'none' on the top of the list for ui purposes.
        for os in operating_systems:
            if os[0] == 'none':
                operating_systems.remove(os)
                operating_systems.insert(0, os)
        if discovery:
            status = 'success'
        else:
            status = 'success'
        response = json.dumps({'status': status, 'operating_systems': operating_systems})
        # add results to cache for one day
        cache.set('operating_systems', response, timeout=86400)
    return response


# find os info given its img_id
def get_os_details(img_id):
    oss = json.loads(operating_systems()).get('operating_systems')
    for os in oss:
        if os[0] == img_id:
            return os[1]
    return False
