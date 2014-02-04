.. ganetimgr documentation master file, created by
   sphinx-quickstart on Thu Oct 31 10:48:21 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to ganetimgr's documentation!
=====================================


What is ganetimgr?
==================
ganetimgr is a web platform that eases the provisioning of virtual machines over miltiple ganeti clusters. In essence, ganetimgr aims to be the frontend of a VPS service. A simplified architecture of ganetimgr is depicted here::

	+------------------------+           +---------------+
	|                        |           |               |
	|                        |     +-----+ ganeti cluster|
	|         Django         |     |     |               |
	|                        |     |     +---------------+
	|                        |     |            ...
	+------------------------+     |            ...
	|     gevent watcher     |     |            ...
	|                        |     |     +---------------+
	+------------------------+     |     |               |
	|  Caching  |ganeti REST +-----+     + ganeti cluster|
	|           |API client  +-----------+               |
	+-----------+------------+           +---------------+

Compatibility
=============
ganetimgr has been tested with ganeti versions 2.4-2.9. Unless something really big has changed with the ganeti REST API client, ganetimgr should be able to interoperate with later versions.

Installation
============
For the time, installation requires the inclussion of GRNET's repository in your sources, but we are working hard to overcome such minor issues. You can go through the installation at the :doc:`Install ganetimgr <install>` section.

.. toctree::
   :maxdepth: 2

   install
   admin
