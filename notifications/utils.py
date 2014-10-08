# TODO: Create a view that does this in the UI
from ganeti.models import Cluster
from django.conf import settings
from django.core.mail.message import EmailMessage


def notify_instance_owners(instances, subject, message):
    # the vms that are facing the problem
    users = []
    for c in Cluster.objects.all():
        for i in c.get_all_instances():
            if i.name in instances:
                for u in i.users:
                    users.append(u.email)

    bcc_list = users
    subject = '%s %s' % (settings.EMAIL_SUBJECT_PREFIX, subject)
    recipient_list = []
    from_email = settings.SERVER_EMAIL
    return EmailMessage(
        subject,
        message,
        from_email,
        recipient_list,
        bcc_list
    ).send()

