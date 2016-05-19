# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('registration', '0004_supervisedregistrationprofile'),
        ('apply', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomRegistrationProfile',
            fields=[
                ('registrationprofile_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='registration.RegistrationProfile')),
                ('admin_activation_key', models.CharField(max_length=40, verbose_name='admin activation key')),
                ('validated', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'registration profile',
                'verbose_name_plural': 'registration profiles',
            },
            bases=('registration.registrationprofile',),
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('first_login', models.BooleanField(default=True)),
                ('force_logout_date', models.DateTimeField(null=True, blank=True)),
                ('telephone', models.CharField(max_length=13, null=True, blank=True)),
                ('organization', models.ForeignKey(blank=True, to='apply.Organization', null=True)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
