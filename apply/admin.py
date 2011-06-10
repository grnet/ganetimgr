from django.contrib import admin
from models import *
from django.forms import PasswordInput
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
                    "status", "backend_message", "filed"]
    list_filter = ["status", "cluster", "organization"]
    ordering = ["-filed", "hostname"]
    actions = make_fast_create_actions()

admin.site.register(Organization)
admin.site.register(InstanceApplication, ApplicationAdmin)
