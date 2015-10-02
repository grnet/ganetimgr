from django.test import TestCase, Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from ganeti.models import Cluster


class ClusterTestCase(TestCase):
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

    def login_user(self):
        return self.client.login(username=self.user_username, password=self.user_password)

    def login_superuser(self):
        return self.client.login(username=self.superuser_username, password=self.superuser_password)

    def test_jobdetails(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('jobdets-popup'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to the instances page
        self.login_user()
        res = self.client.get(reverse('jobdets-popup'))
        self.assertRedirects(res, '/')

        # should get a 404 because of no get params
        self.login_superuser()
        res = self.client.get(reverse('jobdets-popup'))
        self.assertEqual(res.status_code, 404)

        # 404 because no job id
        res = self.client.get(reverse('jobdets-popup'), {'cluster': self.cluster.slug})
        self.assertEqual(res.status_code, 404)

        # the following returns an error message telling us
        # ganetimgr cannot connect with the specified cluster
        res = self.client.get(
            reverse('jobdets-popup'),
            {
                'cluster': self.cluster.slug,
                'jobid': 1
            }
        )
        self.assertEqual(res.status_code, 200)

    def test_instance_popup(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('instance-popup'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to the instances page
        self.login_user()
        res = self.client.get(reverse('instance-popup'))
        self.assertRedirects(res, '/')

        # should get a 404 because of no get params
        self.login_superuser()
        res = self.client.get(reverse('instance-popup'))
        self.assertEqual(res.status_code, 404)

        # 404 because no instance
        res = self.client.get(reverse('instance-popup'), {'cluster': self.cluster.slug, 'instance': 'test'})
        self.assertEqual(res.status_code, 404)

    def test_cluster_nodes(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('cluster-nodes'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to the instances page
        self.login_user()
        res = self.client.get(reverse('cluster-nodes'))
        self.assertRedirects(res, '/')

        # should get a 200
        self.login_superuser()
        res = self.client.get(reverse('cluster-nodes'))
        self.assertEqual(res.status_code, 200)

    def test_cluster_nodes_json(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('cluster-nodes-json'))
        self.assertEqual(res.status_code, 302)

        # should get a 403
        self.login_user()
        res = self.client.get(reverse('cluster-nodes-json'))
        self.assertEqual(res.status_code, 403)

        # should get a 200
        self.login_superuser()
        res = self.client.get(reverse('cluster-nodes-json'))
        self.assertEqual(res.status_code, 200)

    def test_clusterdetails(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('clusterdetails'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to the instances page
        self.login_user()
        res = self.client.get(reverse('clusterdetails'))
        self.assertRedirects(res, '/')

        # should get a 200
        self.login_superuser()
        res = self.client.get(reverse('clusterdetails'))
        self.assertEqual(res.status_code, 200)

    def test_clusterdetails_json(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('clusterdetails_json'))
        self.assertEqual(res.status_code, 302)

        # should get a 403
        self.login_user()
        res = self.client.get(reverse('clusterdetails_json'))
        self.assertEqual(res.status_code, 403)

        # should get a 200
        self.login_superuser()
        res = self.client.get(reverse('clusterdetails_json'))
        self.assertEqual(res.status_code, 200)
