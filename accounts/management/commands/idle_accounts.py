# -*- coding: utf-8 -*- vim:encoding=utf-8:
# vim: tabstop=4:shiftwidth=4:softtabstop=4:expandtab

# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import warnings
warnings.simplefilter("ignore", DeprecationWarning)
from django.core.management.base import BaseCommand
import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.core.mail.message import EmailMessage


class Command(BaseCommand):
    args = ''
    help = 'Fetches the idle users; users that have not logged in for the last %s days' % (
        settings.IDLE_ACCOUNT_NOTIFICATION_DAYS
    )

    def handle(self, *args, **options):
        idle_users = []
        idle_users.extend(
            [u.email for u in User.objects.filter(
                is_active=True,
                last_login__lte=datetime.datetime.now() - datetime.timedelta(
                    days=int(settings.IDLE_ACCOUNT_NOTIFICATION_DAYS)
                )
            ) if u.email])
        idle_users = list(set(idle_users))

        if idle_users:
            email = render_to_string(
                "users/emails/idle_account.txt",
                {
                    "site": Site.objects.get_current(),
                    "days": settings.IDLE_ACCOUNT_NOTIFICATION_DAYS
                }
            )

            self.send_new_mail(
                _("%sIdle Account Notification") % settings.EMAIL_SUBJECT_PREFIX,
                email,
                settings.SERVER_EMAIL,
                [],
                idle_users
            )

    def send_new_mail(
        self,
        subject,
        message,
        from_email,
        recipient_list,
        bcc_list
    ):
        return EmailMessage(subject, message, from_email, recipient_list, bcc_list).send()
