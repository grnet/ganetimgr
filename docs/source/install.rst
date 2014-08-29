=========================
Installation Instructions
=========================

We test (and use) ganetimgr on Debian Stable. This guides documents how to install it on Debian Stable with Nginx, gunicorn and Mysql.
Any feedback on how to install under different circumstances is welcome.

Install packages
----------------

Update and install the required packages::

    apt-get install git nginx mysql-server gunicorn python-gevent redis-server beanstalkd
    apt-get install python-mysqldb python-django python-redis python-django-south python-django-registration python-paramiko python-simplejson python-daemon python-setproctitle python-pycurl python-recaptcha python-ipaddr python-bs4 python-requests python-markdown


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

Pre-Setup
---------

Get the source and checkout to latest stable::

    mkdir /srv/www/
    mkdir /var/log/ganetimgr
    cd /srv/www/
    git clone https://code.grnet.gr/git/ganetimgr
    cd ganetimgr
    git checkout stable

Create the required ``settings.py`` and ``urls.py`` files for the example files::

    cd ganetimgr
    cp settings.py.dist settings.py
    cp urls.py.dist urls.py

Settings.py
-----------

There are a lot of parts of ganetimgr that are customizable. Most of them are changed from the ``settings.py`` file.
Below are explanations for most of the settings:

- Fill the default ``DATABASES`` dictionary with the credentials and info about the database you created before.
- Set ``CACHE_BACKEND`` to "redis_cache.cache://127.0.0.1:6379/?timeout=1500".
- Set ``STATIC_URL`` to the relative URL where Django expects the static resources (e.g. '/static/')
- Set ``STATIC_ROOT`` to the file path of the collected static resources (e.g. '/srv/www/ganetimgr/static/')
- ``TEMPLATE_DIRS`` should contain the project's template folder (e.g. '/srv/www/ganetimgr/static/' )
- The ``BRANDING`` dictionary allows you to customize the logo, moto and footer.
  You can create your own logo starting with the static/branding/logo.* files.
- ``FEED_URL`` is an RSS feed that is displayed in the user login page.
- ``SHOW_ADMINISTRATIVE_FORM`` toggles the admin info panel for the instance application form.
- ``SHOW_ORGANIZATION_FORM`` does the same for the Organization dropdown menu.
- You can use use an analytics service (Piwik, Google Analytics) by editing ``templates/analytics.html`` and adding the JS code that is generated for you by the service. This is souruced from all the project's pages.

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

As of v.1.5.0 there is an autodiscovery mechanism for the images.

    OPERATING_SYSTEMS_URLS = ['http://repo.noc.grnet.gr/images/', 'http://example.com/images/']

All the given HTTP URLs from OPERATING_SYSTEMS_URLS will be searched for images. This discovers all images found on these URLS and makes them available for usage.

The desciption of the images can be automatically fetched from
the contents of a .dsc file with the same name as the image. For example, if an image named debian-wheezy-x86_64.tar.gz, ganetimgr will look for a debian-wheezy-x86_64.tar.gz.dsc file in the same directory
and read it's contents (e.g. Debian Wheezy) and display it accordingly.

You also need to set OPERATING_SYSTEMS_PROVIDER and OPERATING_SYSTEMS_SSH_KEY_PARAM::

    OPERATING_SYSTEMS_PROVIDER = 'image+default'
    OPERATING_SYSTEMS_SSH_KEY_PARAM = 'img_ssh_key_url'

GannetiMgr will look for available images both from both sources. None of the above settings is required.

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
        'working_dir': '/srv/www/ganetimgr',
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
