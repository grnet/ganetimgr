from django.test import TestCase, Client, RequestFactory
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from auditlog.utils import auditlog_entry
import json


class AuditlogTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('audittest', 'test@test.com', 'audittest')
        self.superuser = User.objects.create_user('audittestadmin', 'test@test.com', 'audittestadmin')
        self.superuser.is_staff = True
        self.superuser.is_superuser = True
        self.superuser.save()
        self.factory = RequestFactory()

    def test_auditlog_view(self):
        # dont allow access in unauthorized users
        res = self.client.get(reverse('auditlog'))
        self.assertEqual(res.status_code, 302)

        # users have access to their logs
        self.client.login(username='audittest', password='audittest')
        res = self.client.get(reverse('auditlog'))
        self.assertEqual(res.status_code, 200)

        res = self.client.get(reverse('auditlog_json'))
        self.assertEqual(res.status_code, 200)

        # admin users have access
        self.client.login(username='audittestadmin', password='audittestadmin')
        res = self.client.get(reverse('auditlog'))
        self.assertEqual(res.status_code, 200)

        res = self.client.get(reverse('auditlog_json'))
        self.assertEqual(res.status_code, 200)

        # the response should be empty
        response = json.loads(res.content)
        self.assertEqual(len(response['aaData']), 0)

        # lets create an audit entry
        # shudtdown instance 'test'
        # user = audittestadmin
        request = self.factory.get(reverse('auditlog_json'))
        request.user = self.superuser
        entry = auditlog_entry(request, "Shutdown", 'test', 'test')

        # get again the auditlog
        res = self.client.get(reverse('auditlog_json'))
        self.assertEqual(res.status_code, 200)
        response = json.loads(res.content)
        self.assertEqual(response['aaData'][0]['user'], entry.requester.username)

        # the response should not be empty this time
        response = json.loads(res.content)
        self.assertEqual(len(response['aaData']), 1)

        # do it again as a simple user
        # should not see anything
        self.client.login(username='audittest', password='audittest')

        res = self.client.get(reverse('auditlog_json'))
        self.assertEqual(res.status_code, 200)
        response = json.loads(res.content)

        # the response should be empty for a simple user
        response = json.loads(res.content)
        self.assertEqual(len(response['aaData']), 0)

        # but it sould have an entry for the superuser
        self.client.login(username='audittestadmin', password='audittestadmin')
        res = self.client.get(reverse('auditlog_json'))
        self.assertEqual(res.status_code, 200)
        response = json.loads(res.content)
        self.assertEqual(len(response['aaData']), 1)
