# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROJECT_DIR = os.path.join(BASE_DIR, 'ganetimgr')


# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)


MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'middleware.ForceLogout.ForceLogoutMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    'middleware.UserMessages.UserMessageMiddleware',
    'corsheaders.middleware.CorsMiddleware',
)


STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

STATICFILES_DIRS = (
)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

ROOT_URLCONF = 'ganetimgr.urls'

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.flatpages',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.staticfiles',
    'django_markdown',
    'accounts',
    'registration',
    'ganeti',
    'apply',
    'notifications',
    'stats',
    'auditlog',
    'oauth2_provider',
    'corsheaders',
)


TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "context.pending_notifications.notify",
    "context.session_remaining.seconds",
    "context.global_vars.settings_vars",
    "django.core.context_processors.request",
    "django.contrib.messages.context_processors.messages"
)


SECRET_KEY = 'test'
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)


AUTH_PROFILE_MODULE = 'accounts.UserProfile'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',  # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'ganetimgr.db',                # Or path to database file if using sqlite3.
    }
}

RAPI_CONNECT_TIMEOUT = 8
RAPI_RESPONSE_TIMEOUT = 15
GANETI_TAG_PREFIX = 'TEST'

BRANDING = {
    "SERVICE_PROVIDED_BY": {
        "NAME": "EXAMPLE",
        "URL": "//example.dot.com",
        "SOCIAL_NETWORKS": [
            {
                "URL": "https://facebook.com/",
                "FONT_AWESOME_NAME": "fa-facebook",
                "FONT_COLOR": "#3b5998"
            },
            {
                "URL": "https://twitter.com/",
                "FONT_AWESOME_NAME": "fa-twitter",
                "FONT_COLOR": "#00acee"
            }
        ]
    },
    "LOGO": "/static/ganetimgr/img/logo.png",
    "FAVICON": "/static/ganetimgr/img/favicon.ico",
    "MOTTO": "virtual private servers",
    "FOOTER_ICONS_IFRAME": True,
    # show the administrative contact
    # option when creating a new vm
    "SHOW_ADMINISTRATIVE_FORM": True,
    "SHOW_ORGANIZATION_FORM": True,
}

IDLE_ACCOUNT_NOTIFICATION_DAYS = '180'
SITE_ID = 1
RECAPTCHA_PUBLIC_KEY = ''
RECAPTCHA_PRIVATE_KEY = ''
RECAPTCHA_USE_SSL = True
ACCOUNT_ACTIVATION_DAYS = 10
LOGIN_URL = '/user/login'
LOGIN_REDIRECT_URL = '/'
