ganetimgr installation
======================

.. toctree::
   :maxdepth: 2

.. note::
    This guide assumes a clean debian squeeze (old-stable) installation

Install packages
----------------

Update and install the required packages (you will be asked for a mysql username and password)::

    apt-get update
    apt-get upgrade
    apt-get install nginx mysql-server python-mysqldb python-django python-redis python-django-south python-django-registration python-django-extensions python-paramiko python-simplejson python-daemon python-setproctitle python-pycurl python-recaptcha python-ipaddr beanstalkd
    apt-get install redis-server

Add our repository::

    vim /etc/apt/sources.list.d/grnet.list

and add::

    deb http://repo.noc.grnet.gr/    squeeze main backports

add our gpg key::

    wget -O - http://repo.noc.grnet.gr/grnet.gpg.key|apt-key add -

and install packages::

    apt-get update
    apt-get install gunicorn=0.12.2-2
    apt-get install python-gevent=0.13.0-1

Database Setup
--------------
Login to the mysql interface::

    mysql -u <your username> -p

Create database and user::

    mysql> CREATE DATABASE ganetimgr;
    mysql> CREATE USER 'ganetimgr' IDENTIFIED BY '12345';
    mysql> GRANT ALL PRIVILEGES ON ganetimgr.* TO 'ganetimgr';
    mysql> flush privileges;

Excellent!

Platform Setup
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

    Change STATIC_URL to STATIC_URL = '/static'
    TEMPLATE_DIRS to TEMPLATE_DIRS = (
        '/srv/www/ganetimgr/templates',
    )
    CACHE_BACKEND to CACHE_BACKEND = "redis_cache.cache://127.0.0.1:6379/?timeout=1500"
    And finally:
    RECAPTCHA_PUBLIC_KEY = '<key>'
    RECAPTCHA_PRIVATE_KEY = '<key>'
    to match your own api key.

.. attention::
    When running the syncdb command that follows DO NOT create a superuser yet!

Run the following commands to create the database entries::

    ./manage.py syncdb
    ./manage.py migrate

and the superuser::

    ./manage.py createsuperuser

.. attention::
   If installing for the first time do not forget to copy templates/analytics.html.dist 
   to templates/analytics.html. Set your prefered (we suggest piwik) analytics inclussion 
   script in templates/analytics.html or leave the file empty if no analytics 
   is desired/available.

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
            'settings.py',
        ),
    }

Add to your nginx config::

      location /static {
                root   /srv/www/ganetimgr;
        }

        location /media {
                root  /usr/share/pyshared/django/contrib/admin;
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


And.... you are done!!!

If you visit your webserver's address you should see ganetimgr welcome page

Now it's time to through the :doc:`Admin guide <admin>` to setup your application.

Administration
==============

.. toctree::
   :maxdepth: 2

   admin
