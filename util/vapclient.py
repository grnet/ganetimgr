#!/usr/bin/env python
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
#

# Copyright (c) 2014 GRNET SA
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

import sys
import socket

try:
    import simplejson as json
except ImportError:
    import json

CTRL_SOCKET = "/var/run/vncauthproxy/vncproxy.sock"

def request_forwarding(sport, daddr, dport, password):
    assert(len(password) > 0)
    req = {
        "source_port": int(sport),
        "destination_address": daddr,
        "destination_port": int(dport),
        "password": password
    }

    ctrl = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    ctrl.connect(CTRL_SOCKET)
    ctrl.send(json.dumps(req))

    response = ctrl.recv(1024)
    res = json.loads(response)
    return res

if __name__ == '__main__':
    res = request_forwarding(*sys.argv[1:])
    if res['status'] == "OK":
        sys.exit(0)
    else:
        sys.exit(1)


def request_novnc_forwarding(server, daddr, dport, password, sport=None, tls=False):
    """
    Ask TVAP/VNCAP for a forwarding port.

    The control socket on TVAP wants a JSON dictionary containing at least the
    destination port and address, and VNC password. It optionally can accept a
    requested source port, whether WebSockets should be used, and whether TLS
    (SSL/WSS) should be used.
    """

    try:
        host, port = server
        port = int(port)
        dport = int(dport)
        if not password:
            return False

        request = {
            "daddr": daddr,
            "dport": dport,
            "password": password,
            "ws": True,
            "tls": tls,
        }

        if sport:
            request["sport"] = sport

        request = json.dumps(request)

        ctrl = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ctrl.connect((host, port))
        ctrl.send("%s\r\n" % request)
        response = ctrl.recv(1024).strip()
        ctrl.close()

        if response.startswith("FAIL"):
            return False
        else:
            return response

    # XXX bare except
    except:
        return False

