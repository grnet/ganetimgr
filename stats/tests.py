from django.test import TestCase, Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from ganeti.models import Cluster


class LoginTestCase(TestCase):
    # inject these two functions
    def login_user(self):
        return self.client.login(username=self.user_username, password=self.user_password)

    def login_superuser(self):
        return self.client.login(username=self.superuser_username, password=self.superuser_password)


class StatsTestCase(LoginTestCase):

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
        self.cluster = Cluster.objects.create(
            hostname='test.example.com',
            slug='test'
        )

    def test_applications(self):
        # applications
        # should get a redirect to the login page
        res = self.client.get(reverse('stats_ajax_apps'))
        self.assertEqual(res.status_code, 302)

        self.login_user()
        res = self.client.get(reverse('stats_ajax_apps'))
        self.assertEqual(res.status_code, 200)

        self.login_superuser()
        res = self.client.get(reverse('stats_ajax_apps'))
        self.assertEqual(res.status_code, 200)

    def test_instances(self):
        # instances
        # should get a redirect to the login page
        res = self.client.get(reverse('stats_ajax_instances'))
        self.assertEqual(res.status_code, 302)

        self.login_user()
        res = self.client.get(reverse('stats_ajax_instances'))
        self.assertEqual(res.status_code, 200)

        self.login_superuser()
        res = self.client.get(reverse('stats_ajax_instances'))
        self.assertEqual(res.status_code, 200)

    def test_cluster_instances(self):
        # instances per cluster
        # should get a redirect to the login page
        res = self.client.get(reverse('stats_ajax_vms_pc', kwargs={'cluster_slug': 'test_non_existent'}))
        self.assertEqual(res.status_code, 302)

        self.login_user()
        res = self.client.get(reverse('stats_ajax_vms_pc', kwargs={'cluster_slug': 'test_non_existent'}))
        # non existent cluster
        self.assertEqual(res.status_code, 404)

        self.login_superuser()
        # non existent cluster
        res = self.client.get(reverse('stats_ajax_vms_pc', kwargs={'cluster_slug': 'test_non_existent'}))
        self.assertEqual(res.status_code, 404)

        res = self.client.get(reverse('stats_ajax_vms_pc', kwargs={'cluster_slug': self.cluster.slug}))






