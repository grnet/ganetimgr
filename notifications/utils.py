# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
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

from ganeti.models import Cluster, Instance
from django.template import Context, Template
from django.conf import settings
from django.core.mail.message import EmailMessage
from django.contrib.auth.models import User, Group
from gevent.pool import Pool


def send_emails(subject, body, emails):
    b = Template(body)
    p = Pool(20)

    def _send(subject, text, from_email, email):
        EmailMessage(subject, text, from_email, [email]).send()

    import ipdb; ipdb.set_trace()
    for email, instances in emails.items():
        text = b.render(Context({'instances': instances}))
        p.spawn(_send, subject, text, settings.SERVER_EMAIL, email)
    p.join()


def notify_instance_owners(instances, subject, message):
    # the vms that are facing the problem
    users = []
    # get only enabled clusters
    for c in Cluster.objects.filter(disabled=False):
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
        bcc_list,
        headers={
            'Reply-To': 'helpdesk@grnet.gr'
        }
    ).send()


def find_instances_emails(instances):
    mails = {}
    for instance in instances:
        users = instance.users
        if instance.groups:
            for group in instance.groups:
                for user in group.userset:
                    users.append(user)

        mails.update(
            {
                instance.name: [u.email for u in users]
            }
        )
    return mails


def get_mails(itemlist):
    mails = {}
    for i in itemlist:
        #User
        if i.startswith('u'):
            if mails.get('users'):
                mails.get('users').append(
                    User.objects.get(pk=i.replace('u_', '')).email
                )
            else:
                mails.update(
                    {
                        'users': [
                            User.objects.get(pk=i.replace('u_', '')).email
                        ]
                    }
                )

        #Group
        if i.startswith('g'):
            group = Group.objects.get(pk=i.replace('g_', ''))
            users = group.user_set.all()
            if mails.get('users'):
                mails.get('users').append(
                    [u.email for u in users]
                )
            else:
                mails.update(
                    {
                        'users': [
                            [u.email for u in users]
                        ]
                    }
                )

        #Instance
        if i.startswith('i'):
            instance = Instance.objects.get(name=i.replace('i_', ''))
            if mails.get('instances'):
                mails['instances'].update(find_instances_emails([instance]))
            else:
                mails.update(
                    {
                        'instances': find_instances_emails([instance])
                    }
                )

        # cluster
        if i.startswith('c'):
            cluster = Cluster.objects.get(pk=i.replace('c_', ''))
            instances = cluster.get_instances()
            if mails.get('instances'):
                mails['instances'].update(find_instances_emails(instances))
            else:
                mails.update(
                    {
                        'instances': find_instances_emails(instances)
                    }
                )
        # node
        if i.startswith('n'):
            cluster = Cluster.objects.get(pk=i.split('_')[3])
            node = cluster.get_node_info(i.split('_')[1])
            instances = []
            for instance in node.get('pinst_list'):
                try:
                    instances.append(Instance.objects.get(name=instance))
                except:
                    pass
            if mails.get('instances'):
                mails['instances'].update(find_instances_emails(instances))
            else:
                mails.update(
                    {
                        'instances': find_instances_emails(instances)
                    }
                )
        # nodegroup
        if i.startswith('ng'):
            cluster = Cluster.objects.get(pk=i.split('_')[3])
            nodegroup = cluster.get_node_group_info(i.split('_')[1])
            p = Pool(20)

            def _get_instances(node):
                for instance in node.get('pinst_list'):
                    try:
                        instances.append(Instance.objects.get(name=instance))
                    except:
                        pass
                return instances
            for node_name in nodegroup.get('node_list'):
                node = cluster.get_node_info(node_name)

            p.spawn(_get_instances, node)
            p.join()
            if mails.get('instances'):
                mails.update(
                    {
                        'instances': find_instances_emails(instances)
                    }
                )
            else:
                mails.update(
                    {
                        'instances': find_instances_emails(instances)
                    }
                )
    addresses = {}
    for key, val in mails.items():
        if key == 'instances':
            for k, v in val.items():
                for email in v:
                    if email:
                        if addresses.get(email):
                            addresses.get(email).append(k)
                        else:
                            addresses.update({
                                email: [k]
                            })
        elif key == 'users':
            for user in val:
                if user:
                    if not addresses.get(user):
                        addresses.update({user: None})
    return addresses

