=========================
Installation Instructions
=========================

We test (and use) ganetimgr on the latest stable version of Debian. We also prefer using the Debian packages for Django and any python dependencies instead of using pip and virtualenv. That way we don't have to worry about any of the upstream projects breaking anything and we have quicker/easier security updates.

This guide documents how to install ganetimgr with the following software:

- Debian Stable, the base OS
- gunicorn with gevent, it runs the Django project
- Nginx, the web server that serves the static content and proxies to gunicorn
- Mysql, the database backend
- Redis, as Django's caching backend. Stores session info and caches data
- Beanstalkd, used by worker.py

Any feedback on how to install under different circumstances is welcome.

Install packages
----------------

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

and then start the daemon with::

    service beanstalkd start

Database Setup
--------------

Create a mysql user for ganetimgr.

.. note::
    This is only defined on the project's settings.py so use a strong random password.

Login to the mysql server::

    mysql -u root -p

Create database and user::

    mysql> CREATE DATABASE ganetimgr CHARACTER SET utf8;
    mysql> CREATE USER 'ganetimgr'@'localhost' IDENTIFIED BY <PASSWORD>;
    mysql> GRANT ALL PRIVILEGES ON ganetimgr.* TO 'ganetimgr';
    mysql> flush privileges;

Requirements.txt
----------------
A requirements.txt file is included in order to help you install the required python dependencies.
You can do that by running::

   pip install -r requirements.txt

Pre-Setup
---------

Get the source and checkout to latest stable::

    mkdir /srv/
    mkdir /var/log/ganetimgr
    cd /srv/
    git clone https://code.grnet.gr/git/ganetimgr
    cd ganetimgr
    git checkout stable

Create the required ``settings.py`` files for the example files::

    cd ganetimgr
    cp settings.py.dist settings.py

Settings.py
-----------

There are a lot of parts of ganetimgr that are customizable. Most of them are changed from the ``settings.py`` file.
Below are explanations for most of the settings:

- Fill the default ``DATABASES`` dictionary with the credentials and info about the database you created before.
- Set ``CACHES`` to the backend you want to use, take a look at: https://docs.djangoproject.com/en/1.4/topics/cache/
- Set ``STATIC_URL`` to the relative URL where Django expects the static resources (e.g. '/static/')
- The ``BRANDING`` dictionary allows you to customize stuff like logos and social profiles.
  You can create your own logo starting with the static/branding/logo.* files.
- ``FEED_URL`` is an RSS feed that is displayed in the user login page.
- ``SHOW_ADMINISTRATIVE_FORM`` toggles the admin info panel for the instance application form.
- ``SHOW_ORGANIZATION_FORM`` does the same for the Organization dropdown menu.
- You can use use an analytics service (Piwik, Google Analytics) by editing ``templates/analytics.html`` and adding the JS code that is generated for you by the service. This is souruced from all the project's pages.
- ``AUDIT_ENTRIES_LAST_X_DAYS`` (not required, default is None) determines if an audit entry will be shown depending on the date it was created. It's only applied for the admin and is used in order to prevent ganetimgr from beeing slow. '0' is forever.
- ``GANETI_TAG_PREFIX`` (Default is 'ganetimgr') sets the prefix ganetimgr will use in order to handle tags in instances. eg in order to define an owner it sets 'ganeti_tag_prefix:users:testuser' as a tag in an instance owned by `testuser`, assuming the GANETI_TAG_PREFIX is equal to 'ganeti_tag_prefix'.


External Services
^^^^^^^^^^^^^^^^^

You can use Google re-CAPTCHA during registration to avoid spam accounts. Generate a key pair from `here <http://www.google.com/recaptcha>`_ and fill these settings::

    RECAPTCHA_PUBLIC_KEY = '<key>'
    RECAPTCHA_PRIVATE_KEY = '<key>'

You can use LDAP as an authentication backend. The package ``python-ldap`` needs to be installed.
You need to uncomment the LDAPBackend entry in the ``AUTHENTICATION_BACKENDS`` and uncomment and edit accordingly the AUTH_LDAP_* variables. LDap authentication works simultaneously with normal account auth.

``SERVER_MONITORING_URL`` is used to link ganeti node information with ganetimgr. This URL with the hostname appended
is used to create a link for every node. We use `servermon <https://github.com/servermon/servermon>`_ for node information.

If you deploy a Jira installation then you can append a tab on the left of ganetimgr web interface via an issue
collection plugin that can be setup via::

    HELPDESK_INTEGRATION_JAVASCRIPT_URL
    HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS

If you want to embed collectd statistics in ganetimgr instance view fill the::

    COLLECTD_URL

If COLLECTD_URL is not null, then the graphs section can be used in order to show graphs for each instance. One can define
a NODATA_IMAGE if the default is not good enough.

There is a vm isolation feature for vms that are suspect of having been compromised. The admin or the user can
define a subnet from which the vm will remain accessible for further investigation. The next settings limit the
subnet width (v4 and v6 accordingly) that is allowed to be used.::

    WHITELIST_IP_MAX_SUBNET_V4
    WHITELIST_IP_MAX_SUBNET_V6

Instance Images
^^^^^^^^^^^^^^^

There are two ways to define available images:

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

As of v.1.5.0 there is an autodiscovery mechanism for the images. You just have to insert the following settings variable::

    OPERATING_SYSTEMS_URLS = ['http://repo.noc.grnet.gr/images/', 'http://example.com/images/']

All the given HTTP URLs from OPERATING_SYSTEMS_URLS will be searched for images. This discovers all images found on these URLS and makes them available for usage.

The desciption of the images can be automatically fetched from
the contents of a .dsc file with the same name as the image. For example, if an image named debian-wheezy-x86_64.tar.gz, ganetimgr will look for a debian-wheezy-x86_64.tar.gz.dsc file in the same directory
and read it's contents (e.g. Debian Wheezy) and display it accordingly.

You also need to set OPERATING_SYSTEMS_PROVIDER and OPERATING_SYSTEMS_SSH_KEY_PARAM::

    OPERATING_SYSTEMS_PROVIDER = 'image+default'
    OPERATING_SYSTEMS_SSH_KEY_PARAM = 'img_ssh_key_url'

GannetiMgr will look for available images both from both sources. None of the above settings is required.

There is also an autodiscovery mechanism for snf images, by setting snf-image url in settings.py as such::

    SNF_OPERATING_SYSTEMS_URLS = ['http://repo.noc.grnet.gr/images/snf-image/']

The process is identical with that above.


FLATPAGES
^^^^^^^^^

Ganetimgr provides 3 flatpages - Service Info, Terms of Service and FAQ. Flatpages can be enabled or disabled via the::

    FLATPAGES

dictionary.

We provide 6 flatpages placeholders (3 flatpages x 2 languages - English and Greek) for the flatpages mentioned. By invoking the command::

    python manage.py loaddata flatpages.json

the flatpages placeholders are inserted in the database and become available for editing via the admin interface (Flat Pages).

VNC
^^^
We provide 2 VNC options for the users.

- For the Java VNC applet to work, ``vncauthproxy`` must be running on the server. Setup instructions can be found :doc:`here </ganeti>`.
- For setup instructions for the Websocker VNC applet, check :doc:`here </ganeti>`.

There are three relevant options here:

- ``WEBSOCK_VNC_ENABLED`` enables/disabled the options for the noVNC console.
- ``NOVNC_PROXY`` defines the host vncauthproxy is running (default is 'localhost:8888').
- ``NOVNC_USE_TLS`` specifies the use or not of TLS in the connection. For cert info look at :doc:`here </ganeti>`.


Install
-------

.. attention::
    When running the syncdb command that follows DO NOT create a superuser yet!

Run the following commands to create the database entries::

    python manage.py syncdb --noinput
    python manage.py migrate

and create the superuser manually::

    python manage.py createsuperuser


To get the admin interface files, invoke collectstatic::

    python manage.py collectstatic


Run the watcher.py::

    ./watcher.py


Gunicorn Setup
--------------

Create the gunicorn configuration file (/etc/gunicorn.d/ganetimgr)::

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

.. attention::
    A logrotate script is recommended from keeping the logfile from getting too big.

Restart the service::

    service gunicorn restart


Web Server Setup
----------------

Create (or edit) an nginx vhost with the following::

   location /static {
          root   /srv/www/ganetimgr;
   }

   location / {
          proxy_pass http://127.0.0.1:8088;
   }

Restart nginx::

    service nginx restart

End
---

Ths installation is finished. If you visit your webserver's address you should see the ganetimgr welcome page.

Now it's time to go through the :doc:`Admin guide <admin>` to setup your clusters.

