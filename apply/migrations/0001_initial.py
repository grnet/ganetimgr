# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
from django.conf import settings
import apply.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InstanceApplication',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('hostname', models.CharField(max_length=255)),
                ('memory', models.IntegerField()),
                ('disk_size', models.IntegerField()),
                ('vcpus', models.IntegerField()),
                ('operating_system', models.CharField(max_length=255, verbose_name='operating system')),
                ('hosts_mail_server', models.BooleanField(default=False)),
                ('comments', models.TextField(null=True, blank=True)),
                ('admin_comments', models.TextField(null=True, blank=True)),
                ('admin_contact_name', models.CharField(max_length=255, null=True, blank=True)),
                ('admin_contact_phone', models.CharField(max_length=64, null=True, blank=True)),
                ('admin_contact_email', models.EmailField(max_length=254, null=True, blank=True)),
                ('instance_params', jsonfield.fields.JSONField(null=True, blank=True)),
                ('job_id', models.IntegerField(null=True, blank=True)),
                ('status', models.IntegerField(choices=[(100, b'pending'), (101, b'approved'), (102, b'submitted'), (103, b'processing'), (104, b'failed'), (105, b'created successfully'), (106, b'refused'), (107, b'discarded')])),
                ('backend_message', models.TextField(null=True, blank=True)),
                ('cookie', models.CharField(default=apply.models.generate_cookie, max_length=255, editable=False)),
                ('filed', models.DateTimeField(auto_now_add=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('applicant', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': (('view_applications', 'Can view all applications'),),
            },
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=255)),
                ('website', models.CharField(max_length=255, null=True, blank=True)),
                ('email', models.EmailField(max_length=254, null=True, blank=True)),
                ('tag', models.SlugField(max_length=255, null=True, blank=True)),
                ('phone', models.CharField(max_length=255, null=True, blank=True)),
                ('users', models.ManyToManyField(to=settings.AUTH_USER_MODEL, null=True, blank=True)),
            ],
            options={
                'ordering': ['title'],
                'verbose_name': 'organization',
                'verbose_name_plural': 'organizations',
            },
        ),
        migrations.CreateModel(
            name='SshPublicKey',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key_type', models.CharField(max_length=12)),
                ('key', models.TextField()),
                ('comment', models.CharField(max_length=255, null=True, blank=True)),
                ('fingerprint', models.CharField(max_length=255, null=True, blank=True)),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['fingerprint'],
            },
        ),
        migrations.AddField(
            model_name='instanceapplication',
            name='organization',
            field=models.ForeignKey(blank=True, to='apply.Organization', null=True),
        ),
        migrations.AddField(
            model_name='instanceapplication',
            name='reviewer',
            field=models.ForeignKey(related_name='application_reviewer', default=None, blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]
