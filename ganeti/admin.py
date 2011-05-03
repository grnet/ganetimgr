from django.contrib import admin
from models import *
from django.forms import PasswordInput

class ClusterAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'description')

    #def formfield_for_dbfield(self, db_field, **kwargs):
    #    if db_field.name == 'password':
    #        kwargs['widget'] = PasswordInput
    #    return db_field.formfield(**kwargs)

admin.site.register(Cluster, ClusterAdmin)
