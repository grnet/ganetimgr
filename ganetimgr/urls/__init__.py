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

admin.autodiscover()
flatpages.register()

urlpatterns = patterns('',
    (r'^setlang/?$', 'django.views.i18n.set_language'),
    url(r'^$', 'ganeti.views.user_index', name="user-instances"),
    url(r'^apply/?$', 'apply.views.apply', name="apply"),

    url(r'^application/?$', 'apply.views.application_list', name="application-list"),
    url(r'^application/(?P<application_id>\d+)/review', 'apply.views.review_application', name="application-review"),
    url(r'^application/(?P<application_id>\d+)/(?P<cookie>\w+)/ssh_keys', 'apply.views.instance_ssh_keys', name="instance-ssh-keys"),

    url(r'^user/info/(?P<type>\w+)/(?P<usergroup>[\w\.\@-]+)/?$', 'ganeti.views.user_info', name="user-info"),
    url(r'^user/idle/?$', 'ganeti.views.idle_accounts', name="idle_accounts"),
    url(r'^user/profile/?$', 'apply.views.profile', name="profile"),
    url(r'^user/mail_change/?$', 'apply.views.mail_change', name="mail-change"),
    url(r'^user/name_change/?$', 'apply.views.name_change', name="name-change"),
    url(r'^user/keys/?$', 'apply.views.user_keys', name="user-keys"),
    url(r'^user/keys/delete/(?P<key_id>\d+)?$', 'apply.views.delete_key', name="delete-key"),
    url(r'^user/login/?', 'django.contrib.auth.views.login', {'template_name': 'login.html'}, name="login"),
    url(r'^user/logout/?', 'django.contrib.auth.views.logout', {'next_page': '/'}, name="logout"),
    url(r'^user/pass_change/$', 'django.contrib.auth.views.password_change', {'template_name':'pass_change.html', 'post_change_redirect':'done'}, name="pass_change"),
    url(r'^user/pass_change/done/$',  'django.contrib.auth.views.password_change_done', {'template_name':'pass_change_done.html'}, name="pass_change_done" ),
    url(r'^user/pass_change/notify/$', 'apply.views.pass_notify', name="pass_change_notify"),

    url(r'^news/?$', 'ganeti.views.news', name="news"),

    url(r'^clearcache/?$', 'ganeti.views.clear_cache', name="clearcache"),


    url(r'^notify/(?P<instance>[^/]+)?$', 'notifications.views.notify', name="notify"),
    url(r'^lock/(?P<instance>[^/]+)?$', 'ganeti.views.lock', name="lock"),
    url(r'^isolate/(?P<instance>[^/]+)?$', 'ganeti.views.isolate', name="isolate"),
    url(r'^usergrps/?$', 'notifications.views.get_user_group_list', name="usergroups"),

    url(r'^tags/(?P<instance>[^/]+)?$', 'ganeti.views.tagInstance', name="instance-tags"),
    url(r'^tagusergrps/?$', 'ganeti.views.get_user_groups', name="tagusergroups"),


    url(r'^stats_ajax/applications/?', 'ganeti.views.stats_ajax_applications', name="stats_ajax_apps"),
    url(r'^stats_ajax/instances/?', 'ganeti.views.stats_ajax_instances', name="stats_ajax_instances"),
    url(r'^stats_ajax/vms_cluster/(?P<cluster_slug>\w+)/?', 'ganeti.views.stats_ajax_vms_per_cluster', name="stats_ajax_vms_pc"),
    url(r'^clustersdetail/?$', 'ganeti.views.clusterdetails', name="clusterdetails"),
    url(r'^clustersdetail/json/?$', 'ganeti.views.clusterdetails_json', name="clusterdetails_json"),
    url(r'^stats/instance_owners/?$', 'stats.views.instance_owners', name="instance_owners"),
    url(r'^stats/?', 'ganeti.views.stats', name="stats"),

    url(r'^instance/destreinst/(?P<application_hash>\w+)/(?P<action_id>\d+)/$', 'ganeti.views.reinstalldestreview', name='reinstall-destroy-review'),

    url(r'^nodegroup/fromnet/$', 'apply.views.get_nodegroups_fromnet', name='ng_from_net'),
    url(r'^nodegroups/cluster/$', 'apply.views.get_cluster_node_group_stack', name='cluster_ng_stack'),

    url(r'^history/$', 'auditlog.views.auditlog', name='auditlog'),
    url(r'^history_json/$', 'auditlog.views.auditlog_json', name='auditlog_json'),

    # get a list of the available operating systems
    url(r'^operating_systems_json/$', 'apply.views.get_operating_systems', name='operating_systems_json'),
    url(r'^markdown/', include('django_markdown.urls')),

    (r'^jobs/', include(jobs)),
    (r'^cluster/', include(clusters)),
    (r'^instances/', include(instances)),
    (r'^accounts/', include(accounts)),
    (r'^graph/', include(graphs)),
    (r'^admin/', include(admin.site.urls)),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^static/(?P<path>.*)', 'django.views.static.serve',\
            {'document_root':  settings.STATIC_URL}),
    )
