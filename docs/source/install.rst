*************************
Installation Instructions
*************************

We test (and use) ganetimgr on Debian 7 Wheezy. We also prefer using the Debian packages for Django and any python dependencies instead of using pip and virtualenv. That way we don't have to worry about any of the upstream projects breaking anything and we have quicker/easier security updates.

This guide documents how to install ganetimgr with the following software:

- Debian 7 Wheezy, the base OS
- gunicorn with gevent, it runs the Django project
- NGINX, the web server that serves the static content and proxies to gunicorn
- MySQL, the database backend
- Redis, as Django's caching backend. Stores session info and caches data
- Beanstalkd, used for asynchronous jobs (worker.py)

Any feedback on how to install under different circumstances is welcome.

Install packages
################

Update and install the required packages::

    apt-get install git nginx mysql-server gunicorn python-gevent redis-server beanstalkd
    apt-get install python-mysqldb python-django python-redis python-django-registration python-paramiko python-daemon python-setproctitle python-pycurl python-recaptcha python-ipaddr python-bs4 python-requests python-markdown


Fabric sript
^^^^^^^^^^^^
We have created a fabric sript in order to set up and deploy ganetimgr. It is included under "contrib/fabric/". One can use it by running::

    fab deploy:tag='v1.6' -H ganetimgr.example.com -u user

You will need to have fabric installed though.

This scrip will connect to the specified server and try to set up ganetimgr under "/srv/ganetimgr" which will be a symlink to the actual directory.

In general it performs the following steps:

 - stop redis, beanstalk, touch "/srv/maintenance.on"
 - git clone, git archive under "/tmp" and move to "/srv/ganetimgr<year><month><day><hour><minute>"
 - check if there is an old installation under /srv/ganetimgr and get all the dist files in order to compare them with the newer version
 - create a buckup of the database
 - If no differences have been found between the two versions of ganetimgr, the old configuration files (whatever has also a dist file) will be copied to the new installation.
 - "/srv/ganetimgr" will be point to the new installation
 - management commands (migrate, collectstatic) will be run
 - fabric will ask your permission to remove old installations
 - restart nginx, gunicorn, redis, beanstalk, rm "maintenance.on"
 - in case something goes wrong it will try to make a rollback
 - in case no older installations exist or the dist files, it will ask you to log in the server and edit the settings, while waiting for your input.


Beanstalkd
----------

Edit ``/etc/default/beanstalkd`` and uncomment the following line::

    START=yes


Setup Database (MySQL)
#######################

MySQL is used to store all necessary application data

Create a MySQL user for ganetimgr.

.. note::
    This is only defined on the project's settings.py so use a strong random password.

Login to the MySQL server::

    mysql -u root -p

Create database and user::

    mysql> CREATE DATABASE ganetimgr CHARACTER SET utf8;
    mysql> CREATE USER 'ganetimgr'@'localhost' IDENTIFIED BY <PASSWORD>;
    mysql> GRANT ALL PRIVILEGES ON ganetimgr.* TO 'ganetimgr'@'localhost';
    mysql> flush privileges;

Get the code
############

Get the source and checkout master branch::

    mkdir /srv/
    mkdir /var/log/ganetimgr
    cd /srv/
    git clone https://github.com/grnet/ganetimgr.git
    git checkout master
    cd ganetimgr

You can also checkout a tag if you prefer::
    git checkout tags/v1.6.0

Create the required ``settings.py`` files for the example files::

    cd ganetimgr
    cp settings.py.dist settings.py

Update settings.py
##################

There are a lot of parts of ganetimgr that are very customizable and most of the customization happens by modifying parts of the ``settings.py``
file.  You will find the most important settings to modify towards the end of the ``settings.py`` file.  Below are explanations for most of the
settings that need modification before using the software.

**Mandatory** settings to modify
********************************

- Fill the default ``DATABASES`` dictionary with the credentials and info about the database you created before.
- Set ``CACHES`` to the backend you want to use, take a look at: https://docs.djangoproject.com/en/1.4/topics/cache/

**Optional** settings to modify
*******************************

- Set ``STATIC_URL`` to the relative URL where Django expects the static resources (e.g. '/static/')
- The ``BRANDING`` dictionary allows you to customize stuff like logos and social profiles.
  You can create your own logo starting with the static/branding/logo.* files.
- ``BRANDING.FEED_URL`` is an RSS feed that is displayed in the user login page.
- ``BRANDING.ALNALYTICS_FILE_PATH`` is a file included in every page for analytics.
- ``SHOW_ADMINISTRATIVE_FORM`` toggles the admin info panel for the instance application form.
- ``SHOW_ORGANIZATION_FORM`` does the same for the Organization dropdown menu.
- You can use use an analytics service (Piwik, Google Analytics) by editing ``templates/analytics.html`` and adding the JS code that is generated for you by the service. This is souruced from all the project's pages.
- ``AUDIT_ENTRIES_LAST_X_DAYS`` (not required, default is None) determines if an audit entry will be shown depending on the date it was created. It's only applied for the admin and is used in order to prevent ganetimgr from beeing slow. '0' is forever.
- ``GANETI_TAG_PREFIX`` (Default is 'ganetimgr') sets the prefix ganetimgr will use in order to handle tags in instances. eg in order to define an owner it sets 'ganeti_tag_prefix:users:testuser' as a tag in an instance owned by `testuser`, assuming the GANETI_TAG_PREFIX is equal to 'ganeti_tag_prefix'.

Image Handling
**************

There are two ways to define available images:

Manual image definition
=======================

From the OPERATING_SYSTEMS dictionary (e.g. for a Debian Wheezy image)::

    OPERATING_SYSTEMS = {
    "debian-wheezy": {
        "description": "Debian Wheezy 64 bit",
        "provider": "image+default",
        "osparams": {
            "img_id": "debian-wheezy",
            "img_format": "tarball",
        },
        "ssh_key_param": "img_ssh_key_url",
        },
    }

Automatic image discovery
=========================

As of v.1.5.0 there is an auto-discovery mechanism for the images. You just have to insert the following settings variable::

    OPERATING_SYSTEMS_URLS = ['http://repo.noc.grnet.gr/images/', 'http://example.com/images/']

All the given HTTP URLs from OPERATING_SYSTEMS_URLS will be searched for images. This discovers all images found on these URLs and makes them
available for usage.

The description of the images can be automatically fetched from the contents of a .dsc file with the same name as the image. For example, if an
image named debian-wheezy-x86_64.tar.gz, ganetimgr will look for a debian-wheezy-x86_64.tar.gz.dsc file in the same directory and read it's
contents (e.g. Debian Wheezy) and display it accordingly.

You also need to set OPERATING_SYSTEMS_PROVIDER and OPERATING_SYSTEMS_SSH_KEY_PARAM::

    OPERATING_SYSTEMS_PROVIDER = 'image+default'
    OPERATING_SYSTEMS_SSH_KEY_PARAM = 'img_ssh_key_url'

ganetimgr will look for available images from both sources. None of the above settings is mandatory.

snf-image integration
=======================

There is also an auto-discovery mechanism for images to be used by snf-image, just set the following::

    SNF_OPERATING_SYSTEMS_URLS = ['http://repo.noc.grnet.gr/images/snf-image/']

The process is identical with the one above.


Flat pages
**********

ganetimgr provides 3 flatpages - Service Info, Terms of Service and FAQ. Flatpages can be enabled or disabled via the dictionary::

    FLATPAGES

We provide 6 flatpages placeholders (3 flatpages x 2 languages - English and Greek) for the flatpages mentioned. By invoking the command::

    python manage.py loaddata flatpages.json

the flatpages placeholders are inserted in the database and become available for editing via the admin interface (Flat Pages).

VNC console
***********

We provide 2 VNC console options, a Java based one and a Websockets based. More information about how to setup each option can be found in the VNC documentation :doc:`here </vnc>`.

There are three relevant VNC options for settings.py::

    WEBSOCK_VNC_ENABLED - enables/disabled the options for the noVNC console.
    NOVNC_PROXY  - defines the host vncauthproxy is running (default is 'localhost:8888').
    NOVNC_USE_TLS  - specifies whether to use TLS or not in the websockets connection.

For more information TLS/keys look at the :doc:`VNC documentation </vnc>`.


Whitelisting subnet length
**************************

There is a instance isolation feature for instances that are misbehaving. The administrator can add a special tag to the instance and ganeti can
then apply a policy to drop all traffic towards/from that instance. The admin or the user though can define a subnet from which the instance will
remain accessible for further investigation. This is also added as an instance tag to the VM. The next settings limit the subnet width (v4 and v6
accordingly) that is allowed to be used as a whitelist.::

    WHITELIST_IP_MAX_SUBNET_V4
    WHITELIST_IP_MAX_SUBNET_V6

Interaction with external services
**********************************

re-Captcha
===========

You can use Google re-CAPTCHA during registration to avoid spam accounts. Generate a key pair from `here <http://www.google.com/recaptcha>`_ and
fill these settings::

    RECAPTCHA_PUBLIC_KEY = '<key>'
    RECAPTCHA_PRIVATE_KEY = '<key>'


LDAP authentication
===================
You can use LDAP as an authentication backend. The package ``python-ldap`` needs to be installed.  You need to uncomment the LDAPBackend entry in
the ``AUTHENTICATION_BACKENDS`` and uncomment and edit accordingly the AUTH_LDAP_* variables. LDAP authentication works simultaneously with normal
account auth.

Jira integration
================

If you deploy a Jira installation then you can append a tab on the left of ganetimgr web interface via an issue
collection plugin that can be setup via::

    HELPDESK_INTEGRATION_JAVASCRIPT_URL
    HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS

VM performance graphs
=====================

If you want to embed instance performance graphs in ganetimgr instance view fill the::

    COLLECTD_URL

If COLLECTD_URL is not null, then the graphs section can be used in order to show graphs for each instance. One can define a NODATA_IMAGE if the
default is not good enough. We use the `vima-grapher <https://github.com/grnet/vima-grapher>`_ to collect performance metrics for the instances and generate graphs.

Ganeti node information
=======================

``SERVER_MONITORING_URL`` is used to link ganeti node information with ganetimgr. This URL with the hostname appended to it is used to create a link for every node. We use `servermon <https://github.com/servermon/servermon>`_ for node information.


Initialize Django
#################

.. warning::
    When running the syncdb command that follows DO NOT create a superuser yet!

Run the following commands to create the database entries::

    cd /srv/ganetimgr
    python manage.py syncdb --noinput
    python manage.py migrate

and then create the superuser manually::

    python manage.py createsuperuser

To get the admin interface files, invoke collectstatic::

    python manage.py collectstatic

Setup asynchronous jobs (Beanstalk)
###################################

Beanstalk is used for asynchronous jobs

Edit ``/etc/default/beanstalkd`` and uncomment the following line::

    START=yes

and then start the daemon with::

    service beanstalkd start

To enable processing of asynchronous jobs you need to run the watcher.py as a service. There is an init script for that provided in the contrib/init.d directory and a default file in the contrib/default. You can test that everything is OK before running the service issuing a::

    cp contrib/default/ganetimgr-watcher /etc/default
    cp contrib/init.d/ganetimgr-watcher /etc/init.d
    service ganetimgr-watcher start

Setup gunicorn
##############

Create a gunicorn configuration file (/etc/gunicorn.d/ganetimgr)::

    CONFIG = {
        'mode': 'django',
        'working_dir': '/srv/ganetimgr',
        'user': 'www-data',
        'group': 'www-data',
        'args': (
            '--bind=127.0.0.1:8088',
            '--workers=2',
            '--worker-class=egg:gunicorn#gevent',
            '--timeout=30',
            '--log-file=/var/log/ganetimgr/ganetimgr.log',
        ),
    }

You can find an example in the contrib/gunicorn directory::

    cp contrib/gunicorn/ganetimgr /etc/gunicorn.d

.. note::
    A logrotate script is recommended to keep the logfile from getting too big.

Restart the service::

    service gunicorn restart

Setup Web Server
################

Create (or edit) an nginx vhost with at least the following::

   location /static {
          root   /srv/ganetimgr;
   }

   location / {
          proxy_pass http://127.0.0.1:8088;
   }

You can find an example config in the contrib/nginx directory.

Restart nginx::

    service nginx restart

The End (is the beginning)
#############################
The installation is finished. If you visit your webserver's address you should see the ganetimgr welcome page.

Now it's time to go through the :doc:`Admin guide <admin>` to setup your clusters.
