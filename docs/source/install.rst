ganetimgr installation
======================

.. toctree::
   :maxdepth: 2

.. note::
    This guide assumes a clean debian wheezy (stable) installation

Install packages
----------------

Update and install the required packages (you will be asked for a mysql username and password)::

    apt-get update
    apt-get upgrade
    apt-get install git nginx mysql-server python-mysqldb python-django python-redis python-django-south python-django-registration  python-paramiko python-simplejson python-daemon python-setproctitle python-pycurl python-recaptcha python-ipaddr beanstalkd
    apt-get install redis-server
    apt-get install gunicorn python-gevent

Database Setup
--------------
Login to the mysql interface::

    mysql -u <your username> -p

Create database and user::

    mysql> CREATE DATABASE ganetimgr;
    mysql> CREATE USER 'ganetimgr'@'localhost' IDENTIFIED BY '12345';
    mysql> GRANT ALL PRIVILEGES ON ganetimgr.* TO 'ganetimgr';
    mysql> flush privileges;

Excellent!

Pre-Setup
--------------
Get the source and checkout to latest stable::

    mkdir /srv/www/
    cd /srv/www/
    git clone https://code.grnet.gr/git/ganetimgr
    cd ganetimgr
    git checkout stable


Create a settings file for the django application::

    cp settings.py.dist settings.py
    cp urls.py.dist urls.py


Edit the settings.py file and change the django database config to match your setup. Pay attention to the following::

    Change STATIC_URL to the url serving your static files, eg. STATIC_URL = 'https://example.com/static' 
    and STATIC_ROOT to STATIC_ROOT = '/srv/www/ganetimgr/static/'
    TEMPLATE_DIRS to TEMPLATE_DIRS = (
        '/srv/www/ganetimgr/templates',
    )


Then set your cache backend::

    CACHE_BACKEND to CACHE_BACKEND = "redis_cache.cache://127.0.0.1:6379/?timeout=1500"


Set your supported operating systems via the corresponding OPERATING_SYSTEMS dict-of-dicts variable.

Set your re-CAPTCHA keys::

    RECAPTCHA_PUBLIC_KEY = '<key>'
    RECAPTCHA_PRIVATE_KEY = '<key>'

to match your API key.


If desired, enable LDAP authentication via the AUTH_LDAP_* variables.

If you deploy a servermon instance (https://github.com/servermon/servermon) that generates statistics for your cluster nodes instances, enter its url at::

	SERVER_MONITORING_URL

to link a node with its servermon page.


If you deploy a Jira installation then you can append a tab on the left of ganetimgr web interface via an issue
collection plugin that can be setup via::

	HELPDESK_INTEGRATION_JAVASCRIPT_URL
	HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS

If you want to embed collectd statistics in ganetimgr instance page fill the::

	COLLECTD_URL

You can limit the whitelisted subnets (in case of isolated instances) available via::

	WHITELIST_IP_MAX_SUBNET_V4
	WHITELIST_IP_MAX_SUBNET_V6

parameters


If you want to keep your users updated with the latest news around the service, fill in an RSS feed url at::

	FEED_URL


Eventually, you can change the logo, motto and some footer details via the::

	BRANDING

dictionary. You can create your own logo starting with the static/branding/logo.* files.


Software Setup
--------------

.. attention::
    When running the syncdb command that follows DO NOT create a superuser yet!

Run the following commands to create the database entries::

    python manage.py syncdb
    python manage.py migrate

and the superuser::

    python manage.py createsuperuser

.. attention::
   If installing for the first time and want to have analytics, alter the templates/analytics.html file.
   Set your prefered (we suggest piwik) analytics inclussion script or leave the file as is (commented) if no analytics 
   is desired/available.

To get the admin interface files, invoke collectstatic::

	python manage.py collectstatic


Run the watcher.py::

    mkdir /var/log/ganetimgr
    ./watcher.py

Edit /etc/gunicorn.d/ganetimgr::

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
                    '--debug',
            '--log-level=debug',
            '--log-file=/tmp/ganetimgr.log',
        ),
    }

Add to your nginx config::

   location /static {
          	root   /srv/www/ganetimgr;
   	}

   	location / {
          	proxy_pass http://127.0.0.1:8088;
   	}

   	location /admin {
          	proxy_pass http://127.0.0.1:8088;
   	}

Restart nginx and gunicorn::

    service nginx restart
    service gunicorn restart



WebSockets
==========

To enable WebSocket support you will need to install VNCAuthProxy following the guides of OSL:
https://code.osuosl.org/projects/twisted-vncauthproxy and https://code.osuosl.org/projects/ganeti-webmgr/wiki/VNC#VNC-AuthProxy

Start your twisted-vncauthproxy with::

	twistd --pidfile=/tmp/proxy.pid -n vncap -c tcp:8888:interface=0.0.0.0

Make sure your setup fullfils all the required firewall rules (https://code.osuosl.org/projects/ganeti-webmgr/wiki/VNC#Firewall-Rules)



Now what?
=========
You are done!!!

If you visit your webserver's address you should see ganetimgr welcome page

Now it's time to through the :doc:`Admin guide <admin>` to setup your application.

Administration
==============

.. toctree::
   :maxdepth: 2

   admin
