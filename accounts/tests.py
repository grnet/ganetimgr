from django.test import TestCase, Client
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.models import User


class AccountsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # create a user
        self.user = User(
            email='test@test.com',
            username='test',
        )
        self.user.save()

    def test_registration_url(self):
        res = self.client.get(reverse('registration_register'))
        self.assertEqual(res.status_code, 200)

    def test_login_url(self):
        res = self.client.get(settings.LOGIN_URL, follow=True)
        self.assertEqual(res.status_code, 200)

    def test_activate_url(self):
        res = self.client.get(
            reverse(
                'registration_activate',
                kwargs={'activation_key': 'test'}
            )
        )
        self.assertEqual(res.status_code, 200)

    def test_register(self):
        data = {
            'name': 'test2',
            'surname': 'Test2',
            'phone': '1212',
            'email': 'test2@test.com',
            'username': 'test2',
            'recaptcha': 'test',
            'password1': 'test',
            'password2': 'test',
        }
        res = self.client.post(reverse('registration_register'), data)
        # make sure the user is redirected - form is valid
        self.assertEqual(res.status_code, 302)

        # there should be the user we just created in the db
        user = User.objects.get(email='test2@test.com')

        # make sure this new user is not active
        self.assertFalse(user.is_active)

    def test_user_profile(self):
        # there should also be a user profile
        self.user.userprofile.first_login
