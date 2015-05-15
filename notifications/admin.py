from django.contrib import admin
from notifications.models import NotificationArchive


class NotificationArchiveAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'date', )

admin.site.register(NotificationArchive, NotificationArchiveAdmin)
