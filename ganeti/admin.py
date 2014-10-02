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

from django.contrib import admin
from models import Cluster, Network, InstanceAction


class ClusterAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'description')
    prepopulated_fields = {'slug': ('hostname',)}
    exclude = ('fast_create', 'use_gnt_network')


class NetworkAdmin(admin.ModelAdmin):
    list_display = (
        'description',
        'cluster',
        'cluster_default',
        'mode',
        'link'
    )
    list_filter = ('cluster',)


class InstanceActionAdmin(admin.ModelAdmin):
    list_display = (
        'instance',
        'cluster',
        'action',
        'action_value',
        'activation_key'
    )
    list_filter = ('instance',)

admin.site.register(Cluster, ClusterAdmin)
admin.site.register(Network, NetworkAdmin)
admin.site.register(InstanceAction, InstanceActionAdmin)

