from django.contrib import admin
from models import *
from django.forms import PasswordInput

class ClusterAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'description')

    #def formfield_for_dbfield(self, db_field, **kwargs):
    #    if db_field.name == 'password':
    #        kwargs['widget'] = PasswordInput
    #    return db_field.formfield(**kwargs)


class NetworkAdmin(admin.ModelAdmin):
    list_display = ('description', 'cluster', 'cluster_default', 'mode', 'link')
    list_filter = ('cluster',)


admin.site.register(Cluster, ClusterAdmin)
admin.site.register(Network, NetworkAdmin)
