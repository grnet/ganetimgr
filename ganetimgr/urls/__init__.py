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
from django.conf.urls.defaults import *
from ganeti.models import *
from django.conf import settings

from django.contrib import admin
from django_markdown import flatpages

# import urls
from accounts import urls as accounts
from ganeti.urls import graphs, instances, jobs, clusters
from stats import urls as stats_urls
from apply.urls import application, user
from ganeti.views import discovery

admin.autodiscover()
flatpages.register()

urlpatterns = patterns('',
    (r'^setlang/?$', 'django.views.i18n.set_language'),
    url(r'^$', 'ganeti.views.user_index', name="user-instances"),
    url(r'^news/?$', 'ganeti.views.news', name="news"),
    url(r'^notify/(?P<instance>[^/]+)?$', 'notifications.views.notify', name="notify"),
    url(r'^usergrps/?$', 'notifications.views.get_user_group_list', name="usergroups"),
    url(r'^lock/(?P<instance>[^/]+)?$', 'ganeti.views.lock', name="lock"),
    url(r'^isolate/(?P<instance>[^/]+)?$', 'ganeti.views.isolate', name="isolate"),
    url(r'^tags/(?P<instance>[^/]+)?$', 'ganeti.views.tagInstance', name="instance-tags"),
    url(r'^tagusergrps/?$', 'ganeti.views.get_user_groups', name="tagusergroups"),


    url(r'^clustersdetail/?$', 'ganeti.views.clusterdetails', name="clusterdetails"),
    url(r'^clustersdetail/json/?$', 'ganeti.views.clusterdetails_json', name="clusterdetails_json"),


    url(r'^instance/destreinst/(?P<application_hash>\w+)/(?P<action_id>\d+)/$', 'ganeti.views.reinstalldestreview', name='reinstall-destroy-review'),

    url(r'^nodegroup/fromnet/$', 'apply.views.get_nodegroups_fromnet', name='ng_from_net'),
    url(r'^nodegroups/cluster/$', 'apply.views.get_cluster_node_group_stack', name='cluster_ng_stack'),

    url(r'^history/$', 'auditlog.views.auditlog', name='auditlog'),
    url(r'^history_json/$', 'auditlog.views.auditlog_json', name='auditlog_json'),

    url(r'^clearcache/?$', 'ganeti.views.clear_cache', name="clearcache"),
    url(r'^operating_systems/$', discovery.get_operating_systems, name='operating_systems_json'),
    (r'^application/', include(application)),
    (r'^user/', include(user)),
    (r'^stats/', include(stats_urls)),
    (r'^jobs/', include(jobs)),
    (r'^cluster/', include(clusters)),
    (r'^instances/', include(instances)),
    (r'^accounts/', include(accounts)),
    (r'^graph/', include(graphs)),
    # get a list of the available operating systems
    url(r'^markdown/', include('django_markdown.urls')),
    (r'^admin/', include(admin.site.urls)),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^static/(?P<path>.*)', 'django.views.static.serve',\
            {'document_root':  settings.STATIC_URL}),
    )

