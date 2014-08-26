Ganeti Modifications
====================

For the time being, ganetimgr requires the use of some patched packages. We are working on merging those changes upstreas so that it works on tha vanilla software.
This software need to be install on the ganeti clusters.

Repository
----------

We provide Debian packages for all the different software listed here. To get them you need to use our public repository.

Add our repository to your sources.list::

  echo 'deb http://repo.noc.grnet.gr/ wheezy main backports' > /etc/apt/sources.list.d/grnet.list

Add our gpg key to apt's keyring::

    wget -O - http://repo.noc.grnet.gr/grnet.gpg.key| apt-key add -

And refresh the package list to discover the new packages::

   apt-get update


ganeti-instance-image
---------------------

This is a forked version of the [ganeti-instance-image](https://code.osuosl.org/projects/ganeti-image) OS provider writter by UOSL. 

    apt-get install ganeti-instance-image


It uses the Ganeti OS API v20 to specify runtime osparams so we can specify the instance os during instance creation. It also injects the ssh key of the user inside the insance.
The code from which the package is build can be found [here](https://github.com/grnet/ganeti-instance-image).
You can find a sample Debian Wheezy image [here](http://repo.noc.grnet.gr/debian-wheezy-x86_64.tgz)


Ganeti
------

You will need our ganeti package in order to use the boot from url feature of ganetimgr.


Java VNC applet
---------------
The package ``vncauthproxy`` is required to run on the host ganetimgr is running for the
Java VNC applet to work.

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

Make sure your setup fullfils all the required [firewall rules](https://code.osuosl.org/projects/ganeti-webmgr/wiki/VNC#Firewall-Rules)


Modern browsers block ws:// connections initiated from HTTPS websites, so if you want to open wss:// connections and encrypt your noVNC sessions you need to enable TLS noVNC.
You will also need signed a certificate for the 'example.domain.com' host and place it under twisted-vncauthproxy/keys directory. 
The paths are currently hardcoded so one needs to install these 2 files (keep the filenames)::

    twisted_vncauthproxy/keys/vncap.crt
    twisted_vncauthproxy/keys/vncap.key


IPv6 Warning
""""""""""""
Since twisted (at least until version 12) does not support IPv6, make sure the host running twisted-vncauthproxy
does not advertise any AAAA records, else your clients won't be able to connect.
