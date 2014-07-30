======================
ganetimgr installation
======================

.. toctree::
   :maxdepth: 2

.. note::
    This guide assumes a clean debian wheezy (stable) installation

.. attention::
    If updating from a squeeze installation, pay attention to changes in setting.py

Install packages
----------------

Update and install the required packages (you will be asked for a mysql username and password)::

    apt-get update
    apt-get upgrade
    apt-get install git nginx mysql-server python-mysqldb python-django python-redis python-django-south python-django-registration  python-paramiko python-simplejson python-daemon python-setproctitle python-pycurl python-recaptcha python-ipaddr beanstalkd
    apt-get install redis-server
    apt-get install gunicorn python-gevent
    apt-get install python-bs4

Ganeti-instance-image on your clusters (optional)
-------------------------------------------------

If you want to use all the features of ganetimgr you will need to install our packages of ganeti-instance-image and ganeti *on your clusters* (not on ganetimgr).

Add our repository::

    vim /etc/apt/sources.list.d/grnet.list

and add::

    deb http://repo.noc.grnet.gr/    wheezy main backports

add our gpg key::

    wget -O - http://repo.noc.grnet.gr/grnet.gpg.key|apt-key add -

and install packages::

    apt-get install ganeti-instance-image
    apt-get install ganeti-os-noop
    apt-get install ganeti=2.9.3-1~bpo70+grnet

And finally create an operating system image for ganeti-instance-image. You can download an image of debian wheezy from us::

    wget http://repo.noc.grnet.gr/debian-wheezy-x86_64.tgz -P /srv/ganeti-instance-image/

Repeat those steps for each node.

Our ganeti-instance-image injects ssh keys into an instance.
You will need our ganeti package in order to use the boot from url feature of ganetimgr.

Beanstalkd
----------

Edit ``/etc/default/beanstalkd`` and uncomment the following line::
    
    START=yes

and then start the daemon with::

    service beanstalkd start

Database Setup
--------------
Login to the mysql interface::

    mysql -u <your username> -p

Create database and user::

    mysql> CREATE DATABASE ganetimgr CHARACTER SET utf8;
    mysql> CREATE USER 'ganetimgr'@'localhost' IDENTIFIED BY '12345';
    mysql> GRANT ALL PRIVILEGES ON ganetimgr.* TO 'ganetimgr';
    mysql> flush privileges;

Excellent!

Pre-Setup
---------
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

Set your re-CAPTCHA keys. Generate a key pair here: http://www.google.com/recaptcha ::

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

You can change the logo, motto and some footer details via the::

    BRANDING

dictionary. You can create your own logo starting with the static/branding/logo.* files.


Software Setup
--------------

If you are gonna use our ganeti-instance-image and the debian wheezy image we provide you will need to define it into the settings.py::

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

Ganetimgr provides 3 flatpages - Service Info, Terms of Service and FAQ. Flatpages can be enabled or disabled via the::

    FLATPAGES

dictionary. 

We provide 6 flatpages placeholders (3 flatpages x 2 languages - English and Greek) for the flatpages mentioned. By invoking the command::

    python manage.py loaddata flatpages.json

the flatpages placeholders are inserted in the database and become available for editing via the admin interface (Flat Pages).

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
            '--log-file=/var/log/ganetimgr.log',
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


Analytics Setup
***************

If installing for the first time do not forget to alter `templates/analytics.html` to suit your needs.

If you do not wish to use analytics, leave this file intact (it is commented with Django template comments).

Set your preferred (we use piwik) analytics inclusion script in templates/analytics.html.
Eg::
    <!-- Piwik -->
    <script type="text/javascript">
      var _paq = _paq || [];
      _paq.push(['trackPageView']);
      _paq.push(['enableLinkTracking']);
      (function() {
        var u=(("https:" == document.location.protocol) ? "https" : "http") + "://piwik.example.com//";
        _paq.push(['setTrackerUrl', u+'piwik.php']);
        _paq.push(['setSiteId', 1]);
        var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0]; g.type='text/javascript';
        g.defer=true; g.async=true; g.src=u+'piwik.js'; s.parentNode.insertBefore(g,s);
      })();
    </script>
    <noscript><p><img src="http://piwik.example.com/piwik.php?idsite=1" style="border:0" alt="" /></p></noscript>
    <!-- End Piwik Code -->


Java VNC Setup
**************

The package ``vncauthproxy`` (available from our repo) is required to run on the host ganetimgr is running for the
Java VNC applet to work.

An example config that needs to be placed on ``/etc/default/vncauthproxy`` ::

    DAEMON_OPTS="-p11000 -P15000 -s /var/run/vncauthproxy/vncproxy.sock"
    CHUID="nobody:www-data"

11000-15000 is the (hardcoded, it seems) port range that ganeti uses for vnc binding, so you will need to open 
your firewall on the nodes for these ports.

WebSockets
**********

To enable WebSocket support you will need to install VNCAuthProxy following the guides of OSL:
https://github.com/osuosl/twisted_vncauthproxy and https://code.osuosl.org/projects/ganeti-webmgr/wiki/VNC#VNC-AuthProxy

You will also need at least the following packages: python-twisted, python-openssl

Start your twisted-vncauthproxy with::

    twistd --pidfile=/tmp/proxy.pid -n vncap -c tcp:8888:interface=0.0.0.0

Make sure your setup fullfils all the required firewall rules (https://code.osuosl.org/projects/ganeti-webmgr/wiki/VNC#Firewall-Rules)

The relevant options in settings.py are::

    WEBSOCK_VNC_ENABLED = True
    NOVNC_PROXY = "example.domain.com:8888"

Modern browsers block ws:// connections initiated from HTTPS websites, so if you want to open wss:// connections and encrypt your noVNC sessions you need to edit settings.py and set::

    NOVNC_USE_TLS = True

Then you will also need signed a certificate for the 'example.domain.com' host and place it under twisted-vncauthproxy/keys directory. The paths are currently hardcoded so one needs to install these 2 files (keep the filenames)::

    twisted_vncauthproxy/keys/vncap.crt
    twisted_vncauthproxy/keys/vncap.key


IPv6 Warning
""""""""""""
Since twisted (at least until version 12) does not support IPv6, make sure the host running twisted-vncauthproxy
does not advertise any AAAA records, else your clients won't be able to connect.

Now what?
---------
You are done!!!

If you visit your webserver's address you should see ganetimgr welcome page

Now it's time to through the :doc:`Admin guide <admin>` to setup your application.

Administration
--------------

.. toctree::
   :maxdepth: 2

   admin
