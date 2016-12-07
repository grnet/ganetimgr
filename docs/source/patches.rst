====================
Ganeti Modifications
====================

For the time being, ganetimgr requires using some patched ganeti packages to enable all ganetimgr's features. We are working on merging those changes upstream so that it works on vanilla software.
The following software needs to be installed on the ganeti nodes/clusters.

.. note::
    All patches that enabled special ganetimgr's features have been merged upstream since Ganeti 2.12. If you're using Ganeti 2.12 or newer you
    don't need a patched ganeti any more.

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

This is a forked version of the [ganeti-instance-image](https://code.osuosl.org/projects/ganeti-image) OS provider written by UOSL::

    apt-get install ganeti-instance-image


It uses the Ganeti OS API v20 to specify runtime osparams so we can specify the instance os during instance creation. It also injects the ssh key of the user inside the instance.
The code from which the package is built can be found [here](https://github.com/grnet/ganeti-instance-image).
You can find a sample Debian 7 Wheezy image [here](http://repo.noc.grnet.gr/debian-wheezy-x86_64.tgz)


Ganeti
------
.. note::
    This feature has been merged upstream since Ganeti version 2.12.

If you want to use the ``boot from url`` feature of ganetimgr, you will need our ganeti package::

    apt-get install ganeti ganeti-htools

Our package version has *+grnet* appended to the version string.
