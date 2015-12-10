from django.test import TestCase, Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from apply.models import (
    InstanceApplication,
    PENDING_CODES,
    SshPublicKey,
    Organization
)

from ganeti.models import Cluster


class ApplicationTestCase(TestCase):
    def setUp(self):
        from apply.forms import InstanceApplicationReviewForm
        self.client = Client()
        self.user = User.objects.create_user('applytest', 'test@test.com', 'applytest')
        self.superuser = User.objects.create_user('applytestadmin', 'test@test.com', 'applytestadmin')
        self.superuser.is_staff = True
        self.superuser.is_superuser = True
        self.superuser.save()

    def test_application_urls(self):
        self.client.login(username='applytest', password='applytest')
        res = self.client.get(reverse('apply'))
        self.assertEqual(res.status_code, 200)
        # a user is redirected to the login page
        # if he access an administrative page
        # he has no right to see.
        res = self.client.get(reverse('application-list'))
        self.assertEqual(res.status_code, 302)

        res = self.client.get(reverse('application-save'))
        self.assertEqual(res.status_code, 302)

        res = self.client.get(reverse('application-review', kwargs={'application_id': 1}))
        self.assertEqual(res.status_code, 302)

    def test_application_urls_admin(self):
        self.client.login(username='applytestadmin', password='applytestadmin')
        res = self.client.get(reverse('apply'))
        self.assertEqual(res.status_code, 200)

        res = self.client.get(reverse('application-list'))
        self.assertEqual(res.status_code, 200)

        # try to see an unexistent application
        res = self.client.get(reverse('application-review', kwargs={'application_id': 100}))
        self.assertEqual(res.status_code, 404)

    def test_ajax_urls(self):
        # test if ajax urls from form work
        self.client.login(username='applytest', password='applytest')
        # this should return 400
        res = self.client.get(reverse('operating_systems_json'))
        self.assertEqual(res.status_code, 400)
        # ajax simulation
        res = self.client.get(reverse('operating_systems_json'), {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)

        res = self.client.get(reverse('cluster_ng_stack'))
        self.assertEqual(res.status_code, 302)

        self.client.login(username='applytestadmin', password='applytestadmin')
        res = self.client.get(reverse('cluster_ng_stack'))
        self.assertEqual(res.status_code, 400)

        res = self.client.get(reverse('cluster_ng_stack'), {'cluster_id': 1})
        self.assertEqual(res.status_code, 404)

    def send_application_review(self, data, application):
        # accept instance
        return self.client.post(
            reverse(
                'application-review',
                kwargs={
                    'application_id': application.id
                }),
            data
        )

    def create_dummy_cluster(self):
        cluster = Cluster.objects.create(hostname='test.example.com', slug='test')
        cluster.id = 100
        cluster.save()
        return cluster

    def test_user_application(self):
        self.client.login(username='applytest', password='applytest')
        # create an application
        data = {
            'hostname': 'test2.example.com',
            'memory': 1024,
            'vcpus': 1,
            'disk_size': 5,
            'operating_system': 'noop',
            'comments': 'test',
            'accept_tos': 'on',
            'admin_contact_name': 'asd',
            'admin_contact_email': 'asd@sad.ad',
            'admin_contact_phone': '12123489',
        }
        res = self.client.post(reverse('apply'), data)
        # redirect means form is valid
        self.assertEqual(res.status_code, 302)
        # lets make sure the application has been saved
        application = InstanceApplication.objects.get(hostname='test2.example.com')
        # lets see if the application shows up for the admin
        self.client.login(username='applytestadmin', password='applytestadmin')
        # make sure the admin can edit the application
        res = self.client.get(
            reverse(
                'application-review',
                kwargs={
                    'application_id': application.id
                })
        )
        self.assertEqual(res.status_code, 200)
        # approve form
        form = res.context['appform']
        # make sure the form is currently invalid
        self.assertEqual(form.is_valid(), False)
        # make sure the form is InstanceApplicationReviewForm
        self.assertEqual(form.__class__.__name__, 'InstanceApplicationReviewForm')

        cluster = self.create_dummy_cluster()

        # try to accept instance with missing fields that are required
        # only in accept.

        # initialize the form and add the extra data.
        form = form.__class__(data)
        self.assertEqual(form.is_valid(), False)
        self.assertEqual('cluster' in form.errors.keys(), True)
        self.assertEqual('netw' in form.errors.keys(), True)
        self.assertEqual('node_group' in form.errors.keys(), True)
        self.assertEqual('disk_template' in form.errors.keys(), True)

        # initialize the form and add the extra data.
        data['cluster'] = cluster.id
        form = form.__class__(data)
        form.fields['cluster'].choices.append((100, 100))
        form.fields['netw'].choices.append(('test::test', 'test::test'))
        form.fields['disk_template'].choices.append(('test', 'test'))
        form.fields['node_group'].choices.append(('test', 'test'))
        form.fields['vgs'].choices.append(('test', 'test'))
        form.data['netw'] = 'test::test'
        form.data['disk_template'] = 'test'
        form.data['node_group'] = 'test'
        form.data['vgs'] = 'test'
        self.assertEqual(form.is_valid(), True)

        # accept instance
        res = self.send_application_review(form.data, application)
        self.assertEqual(res.status_code, 200)
        # make sure the application has pending code
        self.assertEqual(application.status in PENDING_CODES, True)

        # reject instance
        form.data['reject'] = 'reject'
        # we have to make sure the form ignores cluster, netw etc
        # in case of rejection
        form.data['cluster'] = ''
        form.data['netw'] = ''
        form.data['disk_template'] = ''
        form.data['node_group'] = ''
        form.data['vgs'] = ''

        # make the request
        res = self.send_application_review(form.data, application)
        form = res.context['appform']
        self.assertEqual('admin_comments' in form.errors.keys(), True)

        # send the form properly
        form.data['admin_comments'] = 'test'
        res = self.send_application_review(form.data, application)
        self.assertEqual(res.status_code, 302)

        # make sure the application has pending code
        self.assertEqual(application.status in PENDING_CODES, True)

        # ssh_keys
        res = self.client.get(reverse(
            "instance-ssh-keys",
            kwargs={
                "application_id": application.id,
                "cookie": application.cookie
            }
        ))
        self.assertEqual(res.content, '')

        # create an ssh key for user
        key = SshPublicKey(
            key_type='test',
            key='test',
            comment='test',
            owner=User.objects.get(username='applytest'),
            fingerprint='test'
        )
        key.save()
        res = self.client.get(reverse(
            "instance-ssh-keys",
            kwargs={
                "application_id": application.id,
                "cookie": application.cookie
            }
        ))
        self.assertEqual(key.key_line(), res.content)

    def test_admin_form(self):
        cluster = self.create_dummy_cluster()
        self.client.login(username='applytestadmin', password='applytestadmin')
        res = self.client.get(reverse('apply'))
        self.assertEqual(res.status_code, 200)
        form = res.context['form']
        self.assertEqual(form.__class__.__name__, 'InstanceApplicationReviewForm')
        form = form.__class__({'bound': 'bound'})
        res = self.client.post(
            reverse(
                'application-save',
            ),
            form.data
        )
        form = res.context['form']
        self.assertEqual('hostname' in form.errors.keys(), True)
        self.assertEqual('cluster' in form.errors.keys(), True)
        self.assertEqual('netw' in form.errors.keys(), True)
        self.assertEqual('disk_template' in form.errors.keys(), True)
        self.assertEqual('node_group' in form.errors.keys(), True)
        self.assertEqual('memory' in form.errors.keys(), True)
        self.assertEqual('vcpus' in form.errors.keys(), True)
        self.assertEqual('operating_system' in form.errors.keys(), True)
        self.assertEqual('disk_size' in form.errors.keys(), True)
        data = {
            'hostname': 'test.example.com',
            'cluster': cluster.pk,
            'netw': 'test::test',
            'disk_template': 'test',
            'node_group': 'test',
            'vgs': 'test',
            'memory': '512',
            'vcpus': '1',
            'operating_system': 'noop',
            'disk_size': '2'
        }
        res = self.client.post(
            reverse(
                'application-save',
            ),
            data
        )
        # make sure the form has been processed
        self.assertEqual(res.status_code, 200)


class UserTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('usertest', 'usertest@test.com', 'usertest')

        self.superuser = User.objects.create_user('usertestadmin', 'test@test.com', 'usertestadmin')
        self.superuser.is_staff = True
        self.superuser.is_superuser = True
        self.superuser.save()

    def test_get_user_info(self):
        # get info for user or group

        # simple users must be redirected
        self.client.login(username='usertest', password='usertest')
        res = self.client.get(reverse('user-info', args=('test', 'test')))
        self.assertEqual(res.status_code, 302)

        # admins should make a valid request
        self.client.login(username='usertestadmin', password='usertestadmin')
        res = self.client.get(reverse('user-info', args=('test', 'test')))
        self.assertEqual(res.status_code, 400)

        # which should contain a group or user that exists
        res = self.client.get(reverse('user-info', args=('group', 'test')))
        self.assertEqual(res.status_code, 404)

        res = self.client.get(reverse('user-info', args=('user', 'test')))
        self.assertEqual(res.status_code, 404)

        res = self.client.get(reverse('user-info', args=('user', 'usertest')))
        self.assertEqual(res.status_code, 200)

    def test_idle_users(self):
        # idle users
        self.client.login(username='usertest', password='usertest')
        res = self.client.get(reverse('idle_accounts'))
        self.assertEqual(res.status_code, 403)

        self.client.login(username='usertestadmin', password='usertestadmin')
        res = self.client.get(reverse('idle_accounts'))
        self.assertEqual(res.status_code, 200)

    def test_profile_page(self):
        self.client.login(username='usertest', password='usertest')
        res = self.client.get(reverse('profile'))
        self.assertEqual(res.status_code, 200)

    def test_user_access(self):
        # make sure email change is not accessible from
        # unauthorized users
        res = self.client.get(reverse('mail-change'))
        self.assertEqual(res.status_code, 302)

        res = self.client.get(reverse('profile'))
        self.assertEqual(res.status_code, 302)

    def test_user_mail_change(self):
        self.client.login(username='usertest', password='usertest')
        res = self.client.get(reverse('mail-change'))
        self.assertEqual(res.status_code, 200)

        form = res.context['form']
        mail = res.context['mail']
        changed = res.context['changed']
        pending = res.context['pending']

        self.assertEqual(form.__class__.__name__, 'EmailChangeForm')
        self.assertEqual(mail, 'usertest@test.com')
        self.assertEqual(changed, False)
        self.assertEqual(pending, False)
        res = self.client.post(
            reverse('mail-change'),
            {
                'email1': 'test-changed@example.com',
                'email2': 'test-changed@example.com'
            }
        )
        self.assertEqual(res.status_code, 200)
        pending = res.context['pending']
        self.assertEqual(pending, True)

    def test_user_set_mail(self):
        # register a new user without email
        User.objects.create_user('usertestemail', password='usertestemail')
        self.client.login(username='usertestemail', password='usertestemail')
        res = self.client.post(
            reverse('mail-change'),
            {
                'email1': 'test-changed@example.com',
                'email2': 'test-changed@example.com'
            }
        )
        self.assertEqual(res.status_code, 200)
        changed = res.context['changed']
        self.assertEqual(changed, True)

    def test_name_change(self):
        self.client.login(username='usertest', password='usertest')
        res = self.client.post(
            reverse('name-change'),
            {
                'name': 'tester',
                'surname': 'testious'
            }
        )
        self.assertEqual(res.context['name'], 'tester testious')

        user = User.objects.get(username='usertest')
        self.assertEqual(user.first_name, 'tester')
        self.assertEqual(user.last_name, 'testious')

    def test_other_change(self):
        # create dummy organization
        org = Organization.objects.create(
            title='testOrg'
        )
        self.client.login(username='usertest', password='usertest')
        res = self.client.post(
            reverse('other-change'),
            {
                'telephone': '12345',
                'organization': org.pk
            }
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['changed'], True)

        user = User.objects.get(username='usertest')
        self.assertEqual(user.userprofile.telephone, '12345')
        self.assertEqual(user.userprofile.organization, org)

    def test_keys(self):
        # create a key
        data = {
            'ssh_pubkey': "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAklOUpkDHrfHY17SbrmTIpNLTGK9Tjom/BWDSUGPl+nafzlHDTYW7hdI4yZ5ew18JH4JW9jbhUFrviQzM7xlELEVf4h9lFX5QVkbPppSwg0cda3Pbv7kOdJ/MTyBlWXFCR+HAo3FXRitBqxiX1nKhXpHAZsMciLq8V6RjsNAQwdsdMFvSlVK/7XAt3FaoJoAsncM1Q9x5+3V0Ww68/eIFmb1zuUFljQJKprrX88XypNDvjYNby6vw/Pb0rwert/EnmZ+AW4OZPnTPI89ZPmVMLuayrD2cE86Z/il8b+gw3r3+1nKatmIkjn2so1d01QraTlMqVSsbxNrRFi9wrf+M7Q== test@test.local"
        }
        self.client.login(username='usertest', password='usertest')
        res = self.client.post(
            reverse('user-keys'),
            data
        )
        key = res.context['keys'][0]
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['keys']), 1)
        self.assertEqual(
            key.key_line().rstrip('\n'),
            data.get('ssh_pubkey')
        )

        # delete the key
        # try to access an unexistent entry
        res = self.client.get(
            reverse('delete-key', args=(100, )),
        )
        self.assertEqual(res.status_code, 404)

        # try to delete other users key

        self.client.login(username='usertestadmin', password='usertestadmin')
        res = self.client.get(
            reverse('delete-key', args=(key.id, )),
        )
        self.assertEqual(res.status_code, 403)

        # try to delete my key
        self.client.login(username='usertest', password='usertest')
        res = self.client.get(
            reverse('delete-key', args=(key.id, )),
        )
        self.assertEqual(res.status_code, 302)
