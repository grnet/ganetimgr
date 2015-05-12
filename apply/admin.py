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
import functools

from django.contrib import admin

from apply.models import Organization, InstanceApplication

class InstanceApplicationAdmin(admin.ModelAdmin):
    list_display = ["hostname", "applicant", "organization", "cluster",
                    "status", "filed"]
    list_filter = ["status", "organization"]
    search_fields = [
        "hostname", "applicant", "organization", "cluster", "status", "filed"
    ]
    list_editable = ["organization"]
    readonly_fields = ["job_id", "backend_message", "reviewer"]
    ordering = ["-filed", "hostname"]
    fieldsets = [
        ('Instance Information', {'fields': ('hostname', 'memory', 'disk_size',
                                             'vcpus', 'operating_system',
                                             'hosts_mail_server')}),
        ('Placement', {'fields': ('instance_params',)}),
        ('Owner Information', {'fields': ('applicant', 'organization',
                                          'admin_contact_name',
                                          'admin_contact_phone',
                                          'admin_contact_email')}),
        ('Backend Information', {'fields': ('status', 'job_id',
                                            'backend_message', 'reviewer')})
    ]


admin.site.register(Organization)
admin.site.register(InstanceApplication, InstanceApplicationAdmin)
