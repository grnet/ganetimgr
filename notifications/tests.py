from django.test import TestCase, Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from notifications.forms import MessageForm


class LoginTestCase(TestCase):
    # inject these two functions
    def login_user(self):
        return self.client.login(username=self.user_username, password=self.user_password)

    def login_superuser(self):
        return self.client.login(username=self.superuser_username, password=self.superuser_password)


class NoficationsTestCase(LoginTestCase):

    def setUp(self):
        self.client = Client()
        self.user_username = 'ganetitest'
        self.user_password = 'ganetitest'
        self.superuser_username = 'ganetitestadmin'
        self.superuser_password = 'ganetitestadmin'
        self.user = User.objects.create_user(self.user_username, 'test@test.com', self.user_password)
        self.superuser = User.objects.create_user(self.superuser_username, 'test@test.com', self.superuser_password)
        self.superuser.is_staff = True
        self.superuser.is_superuser = True
        self.superuser.save()

    def test_usergroups(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('usergroups'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect
        self.login_user()
        res = self.client.get(reverse('usergroups'))
        self.assertEqual(res.status_code, 403)

        self.login_superuser()
        res = self.client.get(reverse('usergroups'))
        self.assertEqual(res.status_code, 400)

        res = self.client.get(reverse('usergroups'), {'q': 'test', 'type': 'test'})
        self.assertEqual(res.status_code, 200)

    def test_notify(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('notify'))
        self.assertEqual(res.status_code, 302)

        # should get 403
        self.login_user()
        res = self.client.get(reverse('notify'))
        self.assertEqual(res.status_code, 403)

        self.login_superuser()
        res = self.client.get(reverse('notify'))
        self.assertEqual(res.status_code, 200)

        res = self.client.get(reverse('notify'), {'instance': 'test.test.test'})
        self.assertEqual(res.status_code, 200)

        # post form validate
        data = {
            'search_for': 'users',
            'subject': 'test',
            'message': 'This is a test',
            'recipient_list': 'ganetitestadmin,ganetitest'
        }
        form = MessageForm(data)
        self.assertEqual(form.is_valid(), True)
