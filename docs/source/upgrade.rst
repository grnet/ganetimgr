=========
Upgrading
=========

This article describes the actions that are needed when upgrading from a previous version of ganetimgr.

Migrating to v.1.6
------------------

- Perform south migration:
    python manage.py migrate

- Collect static files:
    python manage.py collectstatic

- Update settings.py to settings.py.dist

Requirements
++++++++++++
ganetimgr v.1.6 comes with a requirements.txt file, which lists all requirements.
Make sure all of these requirements have been installed on your system.


Migrating to v.1.5.3
--------------------

- Perform south migration:
    python manage.py migrate

- Collect static files:
    python manage.py collectstatic

- Update settings.py to settings.py.dist. A new context processor is deployed
- Update urls.py to urls.py.dist. The graph url has been updated
- New dependencies: ``python-bs4``, ``python-requests`` and ``python-markdown``. All packaged in Debian.
- We recommend changing gunicorn logging to the system logging path (i.e. /var/log/) and not /tmp.
- Also create a logrotate script for the logfile.
- After upgrade is done make sure to restart the watcher process


======================================================================

Migrating to v.1.4.1
--------------------

Bugfix/Feature Enhancements release

settings.py:
- Copy the FLATPAGES dict from settings.py.dist to allow handling of flatpages

======================================================================

Migrating to v.1.4.0
--------------------

Debian wheezy/Django 1.4 compatibility

settings.py:
 - If migrating from a squeeze installation pay attention to
   Django 1.4 changes as depicted in settings.py file, especially the
   introduction of the staticfiles django app
 - Set BRANDING.FEED_URL to an RSS news feed if desired
 - Set BRANDING.ANALYTICS_FILE_PATH to point to an analytics script file if desired
 - Setup WebSockets VNCAuthProxy if desired
 - If WebSockets NoVNC is setup, set the WEBSOCK_VNC_ENABLED to True
   and the NOVNC_PROXY and NOVNC_USE_TLS to match your setup
 - Update the BRANDING dict to match your needs
 - Perform south migration

======================================================================

Migrating to v.1.3.0
--------------------

 - Set the WHITELIST_IP_MAX_SUBNET_V4/V6 to desired max
	whitelist IP subnets in settings.py
 - Perform south migration

======================================================================

Migrating to v.1.2.3
--------------------

- Make sure to include `HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS` in settings.py.

If you deploy Jira and want to set custom javascript parameters, set
```
HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS = { 'key' : 'value' # eg. 'customfield_23123': '1stline' }
```
In any other case set
```
HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS = False
```

======================================================================

Migrating to v1.2.2
--------------------

- Make sure to restart watcher.py

======================================================================

Migrating to >= v1.2
--------------------

- Make sure to:
    - Set the RAPI_TIMEOUT in settings.py (see .dist)
    - Set the NODATA_IMAGE path in settings.py.dist
    - Update urls.py to urls.py.dist
    - Copy templates/analytics.html.dist to templates/analytics.html.

=====================================================================

Migrating to v1.0:
--------------------

- install python-ipaddr lib
- update settings.py and urls.py with latest changes from dist files

Run::
    manage.py migrate

If your web server is nginx, consider placing:
```
proxy_set_header X-Forwarded-Host <hostname>;
```
in your nginx site location part and
```
USE_X_FORWARDED_HOST = True
```
in your settings.py.
The above ensures that i18n operates properly when switching between languages.
