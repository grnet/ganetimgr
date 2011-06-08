from django.contrib import admin
from models import *
from django.forms import PasswordInput

def submit_applications(modeladmin, request, queryset):
    gnt = Cluster.objects.get(hostname="gnt.ypepth.grnet.gr")
    for app in queryset:
        if app.status == STATUS_PENDING:
            app.approve()

        if app.status == STATUS_APPROVED:
            app.cluster = gnt
            app.save()
            app.submit()

submit_applications.short_description = "Approve and submit to test cluster"

class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["hostname", "applicant", "organization", "cluster",
                    "status", "backend_message", "filed"]
    list_filter = ["status", "cluster", "organization"]
    ordering = ["-filed", "hostname"]
    actions = [submit_applications]

admin.site.register(Organization)
admin.site.register(InstanceApplication, ApplicationAdmin)
