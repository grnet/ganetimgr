from django.contrib import admin
from ganetimgr.apply.models import *
from ganetimgr.ganeti.models import Cluster

def make_fast_create_actions():
    actions = []
    for cluster in Cluster.objects.filter(fast_create=True):
        def _submit_applications(modeladmin, request, queryset):
            for app in queryset:
                if app.status == STATUS_PENDING:
                    app.approve()

                if app.status == STATUS_APPROVED:
                    app.cluster = cluster
                    app.save()
                    app.submit()

        _submit_applications.short_description = "Approve and submit to %s" % \
            cluster.description
        # Change the function name, because the admin interface relies on it
        _submit_applications.func_name = "submit_applications_%s" % \
            str(cluster.slug)
        actions.append(_submit_applications)
    return actions


class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["hostname", "applicant", "organization", "cluster",
                    "network", "status", "filed"]
    list_filter = ["status", "network", "organization"]
    list_editable = ["organization", "network"]
    readonly_fields = ["job_id", "backend_message"]
    ordering = ["-filed", "hostname"]
    actions = make_fast_create_actions()
    fieldsets = [
        ('Instance Information', {'fields': ('hostname', 'memory', 'disk_size',
                                             'vcpus', 'operating_system',
                                             'hosts_mail_server') }),
        ('Placement', {'fields': ('network',)}),
        ('Owner Information', {'fields': ('applicant', 'organization',
                                          'admin_contact_name',
                                          'admin_contact_phone',
                                          'admin_contact_email')}),
        ('Backend Information', {'fields': ('status', 'job_id',
                                            'backend_message')})
    ]

admin.site.register(Organization)
admin.site.register(InstanceApplication, ApplicationAdmin)
