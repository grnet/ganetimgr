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
#>from django.conf.urls import patterns, include, url
from django.conf.urls import include, url
from django.views.static import serve

from django.conf import settings

from django.contrib import admin

# import urls
from accounts import urls as accounts
from ganeti.urls import graphs, instances, jobs, clusters, nodegroup
from stats import urls as stats_urls
from apply.urls import application, user
from ganeti.views import get_user_groups, discovery, user_index, news
from ganeti.views import clear_cache, get_messages
from notifications import urls as notifications
from auditlog import urls as auditlog
from django.views.i18n import set_language
admin.autodiscover()

urlpatterns = [ 
    url(r'^setlang/?$', set_language, name='setlang'),
    url(r'^$', user_index, name="user-instances"),
    url(r'^news/?$', news, name="news"),

    # unique, helper urls
    url(r'^clearcache/?$', clear_cache, name="clearcache"),
    url(r'^get_messages/$', get_messages, name="get_messages"),
    url(r'^operating_systems/$', discovery.get_operating_systems, name='operating_systems_json'),
    url(r'^tagusergrps/?$', get_user_groups, name="tagusergroups"),

    # mount apps
    url(r'^application/', include(application)),
    url(r'^history/', include(auditlog)),
    url(r'^nodegroups/', include(nodegroup)),
    url(r'^notifications/', include(notifications)),
    url(r'^user/', include(user)),
    url(r'^stats/', include(stats_urls)),
    url(r'^jobs/', include(jobs)),
    url(r'^cluster/', include(clusters)),
    url(r'^instances/', include(instances)),
    url(r'^accounts/', include(accounts)),
    url(r'^graph/', include(graphs)),
    # get a list of the available operating systems
    url(r'^admin/', include(admin.site.urls)),
]

# oauth
if 'oauth2_provider' in settings.INSTALLED_APPS:
    urlpatterns += [
        url(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    ]

if settings.DEBUG:
    urlpatterns += [
        url(r'^static/(?P<path>.*)', serve,
            {'document_root':  settings.STATIC_URL}),
    ]

