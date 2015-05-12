# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ipaddress', models.CharField(max_length=255, null=True, blank=True)),
                ('action', models.CharField(max_length=255)),
                ('instance', models.CharField(max_length=255)),
                ('cluster', models.CharField(max_length=50)),
                ('job_id', models.IntegerField(null=True, blank=True)),
                ('recorded', models.DateTimeField(auto_now_add=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('is_authorized', models.BooleanField(default=True)),
                ('requester', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
