from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse


class NotificationArchive(models.Model):
    recipients = models.ManyToManyField(User, related_name='notifications')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    sender = models.ForeignKey(User, blank=True, null=True)

    def __unicode__(self):
        return self.subject

    def get_absolute_url(self):
        return reverse('notification-details', kwargs={'notification': self.pk})

    class Meta():
        ordering = ['-date']
        permissions = (
            ("can_view_notif", "Can view all notifications"),
        )
