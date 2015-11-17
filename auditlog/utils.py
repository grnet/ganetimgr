from auditlog.models import AuditEntry
from django.contrib.auth.models import User


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def auditlog_entry(request, action, instance,
                   cluster, save=True, authorized=True):
    entry = AuditEntry(
        requester=User.objects.get(pk=request.user.id),
        ipaddress=get_client_ip(request),
        action=action,
        instance=instance,
        cluster=cluster,
        is_authorized=authorized
    )
    if save:
        entry.save()
    return entry
