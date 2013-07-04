# -*- coding: utf-8 -*- vim:encoding=utf-8:
# vim: tabstop=4:shiftwidth=4:softtabstop=4:expandtab
import warnings
warnings.simplefilter("ignore", DeprecationWarning)
from django.core.management.base import BaseCommand, CommandError
import time, datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.core.mail.message import EmailMessage



class Command(BaseCommand):
    args = ''
    help = 'Fetches the idle users; users that have not logged in for the last %s days' %(settings.IDLE_ACCOUNT_NOTIFICATION_DAYS)

    def handle(self, *args, **options):
        idle_users = []
        idle_users.extend([u.email for u in User.objects.filter(is_active=True, last_login__lte=datetime.datetime.now()-datetime.timedelta(days=int(settings.IDLE_ACCOUNT_NOTIFICATION_DAYS))) if u.email])
        idle_users = list(set(idle_users))
        
        if idle_users:
            email = render_to_string("idle_account.txt",
                                 {"site": Site.objects.get_current(),
                                  "days": settings.IDLE_ACCOUNT_NOTIFICATION_DAYS})
        
            self.send_new_mail(_("%sIdle Account Notification") % settings.EMAIL_SUBJECT_PREFIX,
                  email, settings.SERVER_EMAIL, [], idle_users)
        
        
    def send_new_mail(subject, message, from_email, recipient_list, bcc_list):
        return EmailMessage(subject, message, from_email, recipient_list, bcc_list).send() 