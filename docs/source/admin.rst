Administrator guide
===================

Cluster Setup
-------------

Ganetimgr needs a set of RAPI credentials to communicate with a cluster. These need to be created manually.
The next steps need to be repeated for every cluster you wish to administrer with ganetimgr.

Create (or edit if it already exists) the ``/var/lib/ganeti/rapi/users`` file on every node at the cluster like this::

	<user> <pass> write

You can replace ``write`` with ``read`` so that ganetimgr can only view the cluster resources, but most of the ganetimgr functionality will be disabled.

=====================================================================

Login to the ganetimgr platform and go to the admin interface. You can do so from the sidebar:

.. image:: _static/images/image00.png

Select the ``cluster`` option from the Ganeti section.

.. image:: _static/images/image01.png
	:scale: 50 %

From here you can manage the you cluster pool. Normally this list is empty now. Select the “Add” cluster option:

.. image:: _static/images/image03.png
	:scale: 50 %

An explanation about some of the settings:

- ``Hostname`` is the fully qualified domain name of the cluster
- ``Slug`` is a friendly name for the cluster
- ``Port`` is the port the RAPI daemon listens to on the master node. Unless you manually changed it this should be 5080
- ``Username/Password`` are the credentials created earlier for the cluster
- ``Fast instance creation`` is an option to submit instance creation requests through the admin insterface instead of going through the normal application procedure.
- ``Default disk template`` is the disk template used by default for the specific cluster
- ``Cluster uses gnt-network`` is a soon to be deprecated option about network options for new instances. If you use routed networks (though gnt-network) this should be on.

Network Setup
-------------

Ganetimgr autodiscovers any network available through gnt-network on the cluster during the instance creation. You can also hardcode any other networks (e.g. bridged vlans) from the admin interface

.. image:: _static/images/image04.png
	:scale: 50 %

- Link is the name of the network device found on the cluster.
- Mode is the network mode for the interface can be routed or bridged.
- Groups ties the network to a specific user group. When a user from that group submits an application this network is autoselected.
