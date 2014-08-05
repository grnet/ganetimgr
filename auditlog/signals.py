import django.dispatch
from django.contrib.auth.models import User
from auditlog.models import *
audit_entry = django.dispatch.Signal()


def store_audit_entry(sender, *args, **kwargs):
    if 'user' in kwargs.keys():
        user = kwargs['user']
    if 'ipaddress' in kwargs.keys():
        ipaddress = kwargs['ipaddress']
    if 'action' in kwargs.keys():
        action = kwargs['action']
    if 'instance' in kwargs.keys():
        instance = kwargs['instance']
    if 'cluster' in kwargs.keys():
        cluster = kwargs['cluster']    
    auditlog = AuditEntry(requester=User.objects.get(pk=user), ipaddress=ipaddress, action=action, instance=instance, cluster=cluster)
    auditlog.save

audit_entry.connect(store_audit_entry)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip