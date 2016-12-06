VNC console
===========

For the time being, ganetimgr requires using some patched ganeti packages to enable all the features. We are working on merging those changes upstream so that it works on tha vanilla software.
The following software needs to be installed on the ganeti nodes/clusters.

Repository
----------

We provide Debian packages for all the different software listed here. To get them you need to use our public repository.

Add our repository to your sources.list::

    echo 'deb http://repo.noc.grnet.gr/ wheezy main backports' > /etc/apt/sources.list.d/grnet.list

Add our gpg key to apt's keyring::

    wget -O - http://repo.noc.grnet.gr/grnet.gpg.key| apt-key add -

And refresh the package list to discover the new packages::

    apt-get update

Java VNC applet
---------------
.. warning::
    This method has been deprecated in favor of the WebSocketsVNC version

The package ``vncauthproxy`` is required to run on the host ganetimgr is
running for the Java VNC applet to work.

You can install it with::

   apt-get install vncauthproxy

An example config that needs to be placed on ``/etc/default/vncauthproxy`` ::

    DAEMON_OPTS="-p11000 -P15000 -s /var/run/vncauthproxy/vncproxy.sock"
    CHUID="nobody:www-data"

11000-15000 is the (hardcoded, it seems) port range that ganeti uses for vnc binding, so you will need to open
your firewall on the nodes for these ports.


WebSocketsVNC
-------------

To enable WebSocket support you will need to install [VNCAuthProxy](https://github.com/osuosl/twisted_vncauthproxy) following this [guide](https://code.osuosl.org/projects/ganeti-webmgr/wiki/VNC#VNC-AuthProxy) from OSL

You will also need at least the following packages: python-twisted, python-openssl

Start your twisted-vncauthproxy with::

    twistd --pidfile=/tmp/proxy.pid -n vncap -c tcp:8888:interface=0.0.0.0

Make sure your setup fulfills all the required [firewall rules](https://code.osuosl.org/projects/ganeti-webmgr/wiki/VNC#Firewall-Rules)

Modern browsers block ws:// connections initiated from HTTPS websites, so if you want to open wss:// connections and encrypt your noVNC sessions you need to enable TLS noVNC.
You will also need signed a certificate for the 'example.domain.com' host and place it under twisted-vncauthproxy/keys directory.
The paths are currently *hardcoded* so one needs to install these 2 files (keep the filenames)::

    twisted_vncauthproxy/keys/vncap.crt
    twisted_vncauthproxy/keys/vncap.key


IPv6 Warning
""""""""""""
Since twisted (at least until version 12) does not support IPv6, make sure the host running twisted-vncauthproxy
does not advertise any AAAA records, else your clients won't be able to connect.
