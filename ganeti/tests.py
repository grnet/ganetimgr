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


class ClusterTestCase(LoginTestCase):

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

    def test_jobdetails(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('jobdets-popup'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to the instances page
        self.login_user()
        res = self.client.get(reverse('jobdets-popup'))
        self.assertEqual(res.status_code, 302)

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
        self.assertEqual(res.status_code, 302)


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
        self.assertEqual(res.status_code, 302)

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
        self.assertEqual(res.status_code, 302)

        # should get a 200
        self.login_superuser()
        res = self.client.get(reverse('clusterdetails'))
        self.assertEqual(res.status_code, 200)

    def test_clusterdetails_json(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('clusterdetails_json'))
        self.assertEqual(res.status_code, 403)

        # should get a 403
        self.login_user()
        res = self.client.get(reverse('clusterdetails_json'))
        self.assertEqual(res.status_code, 403)

        # should get a 200
        self.login_superuser()
        res = self.client.get(reverse('clusterdetails_json'))
        self.assertEqual(res.status_code, 200)


class GraphsTestCase(LoginTestCase):
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

    def test_graphs(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('cluster-get-nodes-graphs'))
        self.assertEqual(res.status_code, 302)

        # should get a 403
        self.login_user()
        res = self.client.get(reverse('cluster-get-nodes-graphs'))
        self.assertEqual(res.status_code, 403)

        # should get a 200
        self.login_superuser()
        res = self.client.get(reverse('cluster-get-nodes-graphs'))
        self.assertEqual(res.status_code, 200)

        # try to give cluster slug
        res = self.client.get(reverse('cluster-get-nodes-graphs', kwargs={'cluster_slug': self.cluster.slug}))
        self.assertEqual(res.status_code, 200)

        # try to give a non-existent cluster slug
        res = self.client.get(reverse('cluster-get-nodes-graphs', kwargs={'cluster_slug': 'nonexistenttest'}))
        self.assertEqual(res.status_code, 404)


class InstancesTestCase(LoginTestCase):
    # the tests we can do here are really limited because this part
    # of the app is heavilly dependent in the ganeti rapi. We can
    # just make sure that we get the proper error messages
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

    def test_tags(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('instance-tags', kwargs={'instance': 'test.test.test'}))
        self.assertEqual(res.status_code, 302)

        # should get a 404
        self.login_user()
        res = self.client.get(reverse('instance-tags', kwargs={'instance': 'test.test.test'}))
        self.assertEqual(res.status_code, 404)

        # should get a 404
        self.login_superuser()
        res = self.client.get(reverse('instance-tags', kwargs={'instance': 'test.test.test'}))
        self.assertEqual(res.status_code, 404)

    def test_instances_json(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('user-instances-json'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to the login page
        self.login_user()
        res = self.client.get(reverse('user-instances-json'))
        self.assertEqual(res.status_code, 200)

        # should get a redirect to the login page
        self.login_superuser()
        res = self.client.get(reverse('user-instances-json'))
        self.assertEqual(res.status_code, 200)

    def test_stats_json(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('user-stats-json'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to the login page
        self.login_user()
        res = self.client.get(reverse('user-stats-json'))
        self.assertEqual(res.status_code, 200)

        # should get a redirect to the login page
        self.login_superuser()
        res = self.client.get(reverse('user-stats-json'))
        self.assertEqual(res.status_code, 200)

    def test_lock(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('lock', kwargs={'instance': 'test'}))
        self.assertEqual(res.status_code, 302)

        # should get a redirect instances
        self.login_user()
        res = self.client.get(reverse('lock', kwargs={'instance': 'test'}))
        self.assertEqual(res.status_code, 302)

        # should raise 404 for superuser
        # because instance does not exist
        self.login_superuser()
        res = self.client.get(reverse('lock', kwargs={'instance': 'test'}))
        self.assertEqual(res.status_code, 404)

    def test_isolate(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('isolate', kwargs={'instance': 'test'}))
        self.assertEqual(res.status_code, 302)

        # should get a redirect instances
        self.login_user()
        res = self.client.get(reverse('isolate', kwargs={'instance': 'test'}))
        self.assertEqual(res.status_code, 302)

        # should raise 404 for superuser
        # because instance does not exist
        self.login_superuser()
        res = self.client.get(reverse('isolate', kwargs={'instance': 'test'}))
        self.assertEqual(res.status_code, 404)


class JobsTestCase(LoginTestCase):
    # the tests we can do here are really limited because this part
    # of the app is heavilly dependent in the ganeti rapi. We can
    # just make sure that we get the proper error messages
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

    def test_jobs(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('jobs'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect instances
        self.login_user()
        res = self.client.get(reverse('jobs'))
        self.assertEqual(res.status_code, 403)

        # should raise 404 for superuser
        # because instance does not exist
        self.login_superuser()
        res = self.client.get(reverse('jobs'))
        self.assertEqual(res.status_code, 200)

    def test_jobs_json(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('jobs_json'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect instances
        self.login_user()
        res = self.client.get(reverse('jobs_json'))
        self.assertEqual(res.status_code, 403)

        # should raise 404 for superuser
        # because instance does not exist
        self.login_superuser()
        res = self.client.get(reverse('jobs_json'))
        self.assertEqual(res.status_code, 200)


class NodegroupsTestCase(LoginTestCase):
    # the tests we can do here are really limited because this part
    # of the app is heavilly dependent in the ganeti rapi. We can
    # just make sure that we get the proper error messages
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

    def test_fromnet(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('ng_from_net'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to login
        self.login_user()
        res = self.client.get(reverse('ng_from_net'))
        self.assertEqual(res.status_code, 302)

        # requires network_id in get params
        self.login_superuser()
        res = self.client.get(reverse('ng_from_net'))
        self.assertEqual(res.status_code, 400)

        # should raise 404 for superuser
        # because network does not exist
        res = self.client.get(reverse('ng_from_net'), {'network_id': 1})
        self.assertEqual(res.status_code, 404)

    def test_cluster_ng_stack(self):
        # should get a redirect to the login page
        res = self.client.get(reverse('cluster_ng_stack'))
        self.assertEqual(res.status_code, 302)

        # should get a redirect to login
        self.login_user()
        res = self.client.get(reverse('cluster_ng_stack'))
        self.assertEqual(res.status_code, 302)

        # should raise bad request
        self.login_superuser()
        res = self.client.get(reverse('cluster_ng_stack'))
        self.assertEqual(res.status_code, 400)

        # should raise 404 for superuser
        # because cluster does not exist
        res = self.client.get(reverse('cluster_ng_stack'), {'cluster_id': '120'})
        self.assertEqual(res.status_code, 404)

        # should return 200 (with error message)
        res = self.client.get(reverse('cluster_ng_stack'), {'cluster_id': self.cluster.pk})
        self.assertEqual(res.status_code, 200)
