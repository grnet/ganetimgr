from django.core.management.base import BaseCommand
from django.core.exceptions import ImproperlyConfigured
from apply.models import Organization, InstanceApplication
from django.conf import settings
from django.core.mail import mail_admins
from django.contrib.auth.models import User
from ganeti.utils import get_user_instances
from optparse import make_option

import requests
import json


def get_invalid_instances():
    text = ''
    invalid = Organization.objects.filter(synced=False)
    if invalid:
        inst_appl = {}
        admin = User.objects.filter(is_superuser=True)[0]
        instances = get_user_instances(admin)['instances']

        for org in invalid:
            applications = InstanceApplication.objects.filter(
                organization_id=org.id)
            if applications:
                inst_appl[org.tag] = [
                    application.hostname
                    for application in applications
                    if application.hostname in instances
                ]

        text = (
            'The following organizations no longer exist in GRNET '
            'members database or have been marked as invalid:\n\n'
        )
        for org in invalid:
            text += '%s (TAG: %s)\n' % (org.title, org.tag)
            text += 'Active Instances:\n'
            try:
                active_instances = inst_appl[org.tag]
            except:
                active_instances = None
            if active_instances:
                text += ''.join(('---%s\n' % application) for application in active_instances)
            else:
                text += '---(None)\n'
            text += '\n'
    return text


class Command(BaseCommand):
    help = 'Export valid peers and related information. \n'

    option_list = BaseCommand.option_list + (
        make_option(
            '--lognew',
            action='store_true',
            help=(
                'If specified, sends an email with the newly '
                'imported organizations.\n'
            ),
        ),
        make_option(
            '--loginvalid',
            action='store_true',
            help=(
                'If specified, sends an email with the invalid '
                'organizations (according to members database) and '
                'the active instances that belong to users from those '
                'organizations\n'
            ),
        )
    )

    def handle(self, *args, **kwargs):

        mail_text = ''

        if hasattr(settings, 'ORGANIZATIONS_SYNC_URL'):
            res = requests.get(settings.ORGANIZATIONS_SYNC_URL, verify=False)
        else:
            raise ImproperlyConfigured(
                'You need to set ORGANIZATIONS_SYNC_URL in settings')
        if res.ok:
            res.encoding = 'utf-8'
            data = json.loads(res.text)

            text = 'Newly imported Organizations: \n\n'

            for organization in data:
                try:
                    org = Organization.objects.get(
                        tag=organization['peer_tag'])
                except:
                    org = Organization.objects.create()
                    text += '---%s (TAG:%s)\n' % (
                        organization['peer_name'],
                        organization['peer_tag']
                    )
                # probably need to check for MultipleObjectsReturned error, but
                # we deliberately skip it so that the exception is thrown
                # and execution is stopped.
                org.title = organization['peer_name']
                org.tag = organization['peer_tag']
                org.phone = organization['phone']
                org.website = organization['domain_name']
                org.email = organization['email']
                org.synced = True
                org.save()

            if kwargs.get('lognew'):
                mail_text += text + '\n\n'

            if kwargs.get('loginvalid'):
                mail_text += get_invalid_instances()

            if mail_text:
                mail_admins(
                    'ViMa organization synchronization',
                    mail_text,
                    fail_silently=False
                )
            Organization.objects.all().update(synced=False)
        else:
            raise ImproperlyConfigured('Could not get data from %s: %s' % (
                settings.ORGANIZATIONS_SYNC_URL,
                res.status_code
            ))
