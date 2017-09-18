# Django 1.8 (v2.0) Upgrade guide

This document describes the process required to upgrade GAENTIMGR to Django 1.8.

## Basic information

### Django versions & support

As of version '2.0', support for pre-1.8 Django versions will
be officially dropped, so it is best to upgrade as soon as possible to continue
receiving the newest features and bug fixes.

### Requirements & Package upgrades

The project's requirements have changed. We are always trying to follow the
Debian releases & official packages but it is not always possible, so some
packages need to be installed by `pip`.

This version has been developed and tested for Debian 8.0 (Jessie)



## Upgrade procedure

### Pre-upgrade steps

It is always a good idea to take a dump of your database during such operations
to ensure that no data is lost should anything go wrong. This would be the best
time to do so.

To succesfully upgrade to the new version you first need to make sure you have
applied the latest migrations before the upgrade. To do this:

    git pull origin master
    git checkout v1.7.0
    ./manage.py migrate

Then you are ready to upgrade to the latest version.

    git checkout master

### Installation of new packages

Now it is time to install the new packages.

We chose to use some package versions from the Backports repository.

If you don't have it enabled, you can do so by entering:
    
    echo "deb http://ftp.gr.debian.org/debian/     jessie-backports main contrib non-free" >> /etc/apt/sources.list.d/backports.list

We need Django, gunicorn and gevent from backports:
    
    apt-get install -t jessie-backports python-django gunicorn python-gevent

We prefer to target Django's LTS releases for the project, so we used Django
v1.8 from backports. Moreover, we found a bug with gevent on Jessie's python
base & another one with gevent, so we used the ones available from backports again

Further Info:
 - [ssl broken for python > 2.7.9](https://github.com/gevent/gevent/issues/477)
 - [gunicorn StopIteration](https://github.com/benoitc/gunicorn/issues/790)

We replaced `django-registration` with `django-registration-redux`.
There is no official Debian package for registration-redux, so for this package
you will need to use pip to install it.

We removed some libraries from the repository. You need to manually install
jsonfield and beanstalkc.

    apt-get install python-django-jsonfield python-beanstalkc
    
Django 1.7 introduced a build in migration mechanism, so we no longer use South.

    apt-get remove python-django-south


### Project upgrade

To upgrade:

    git checkout master
    git checkout v2.0

Then you need to make sure that your `settings.py` is up to date with whatever
has changed in `settings.py.dist`. 

Make sure you update the following on `settings.py`:

 - Remove south from `INSTALLED_APPS` from `settings.py`
 - Change `NODATA_IMAGE` to this:
    ```
    NODATA_IMAGE = 'static/ganetimgr/img/nodata.jpg'
    ```
  - Add these anywhere:
    ```
    TEST_RUNNER = 'django.test.runner.DiscoverRunner'
    SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'
    REGISTRATION_FORM = 'accounts.forms.RegistrationForm'
    ```
 - Remove `CACHE_BACKEND` and replace it with (change accordingly to your setup):
    ```
    CACHES = {
        'default': {
            'BACKEND': "redis_cache.cache.CacheClass",
            'LOCATION': "127.0.0.1:6379",
           'TIMEOUT': '1500',
    }
    ```
 - Ensure the `ADMINS` settings is populated with the mail of the user(s)
   you want to approve the newly registered accounts.
 
 - Ensure that `registration` is defined before `accounts` in `INSTALLED_APPS`


Then finally,

    ./manage.py migrate --fake-initial
    ./manage.py collectstatic --noinput
    ./manage.py compilemessages


If you are using Debian's gunicorn, you need to update the config in
`/etc/gunicorn.d/ganetimgr` (django mode no longer works with Jessie's gunicorn)
```
    CONFIG = {
            'mode': 'wsgi',
            'working_dir': '/srv/ganetimgr',
            'user': 'www-data',
            'group': 'www-data',
            'args': (
                    'ganetimgr.wsgi',
                    '--workers=2',
                    '--worker-class=gevent',
                    '--error-log=/var/log/gunicorn/ganetimgr.error.log',
                    '--timeout=60',
            ),
    }
```

Restart all related services

    service gunicorn restart
    service ganetimgr-watcher restart

and the upgrade is complete.


## Post upgrade configuration

The legacy vncauthproxy application will no work on Jessie systems.
We will deprecate and remove support for it in the next release.

Admin approval emails sent before the migration, will no longer work due to the
changed URL layout.

NOTE: The application used some custom permissions on `Instance`s. However,
since `Instance` does not inherit `django.db.models.Model` but is a pure
python object, Django > 1.7 will not detect the custom permissions defined
in the object's `Meta`. A fix has been introduced (using a `CustomPermission`
object), so that those permissions can be assigned again to users. However,
any permissions previously assigned will need to be reassigned. The affected
permissions are `ganeti.can_isolate`, `ganeti.can_lock`. Make sure you fix
this manually.
