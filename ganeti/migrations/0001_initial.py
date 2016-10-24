# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Cluster',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('hostname', models.CharField(max_length=128)),
                ('slug', models.SlugField()),
                ('port', models.PositiveIntegerField(default=5080)),
                ('description', models.CharField(max_length=128, null=True, blank=True)),
                ('username', models.CharField(max_length=64, null=True, blank=True)),
                ('password', models.CharField(max_length=64, null=True, blank=True)),
                ('fast_create', models.BooleanField(default=False, help_text=b'Allow fast instance creations on this cluster using the admin interface', verbose_name=b'Enable fast instance creation')),
                ('use_gnt_network', models.BooleanField(default=True, help_text=b'Set to True only if you use gnt-network.', verbose_name=b'Cluster uses gnt-network')),
                ('disable_instance_creation', models.BooleanField(default=False, help_text=b'True disables setting a network at the application review form and blocks instance creation', verbose_name=b'Disable Instance Creation')),
                ('disabled', models.BooleanField(default=False)),
            ],
            options={
                'permissions': (('view_instances', 'Can view all instances'),),
            },
        ),
        migrations.CreateModel(
            name='InstanceAction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('instance', models.CharField(max_length=255, blank=True)),
                ('action', models.IntegerField(choices=[(1, b'reinstall'), (2, b'destroy'), (3, b'rename'), (4, b'mailchange')])),
                ('action_value', models.CharField(max_length=255, null=True)),
                ('activation_key', models.CharField(max_length=40)),
                ('filed', models.DateTimeField(auto_now_add=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('operating_system', models.CharField(max_length=255, null=True)),
                ('applicant', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('cluster', models.ForeignKey(blank=True, to='ganeti.Cluster', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Network',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=255)),
                ('link', models.CharField(max_length=255)),
                ('mode', models.CharField(max_length=64, choices=[(b'bridged', b'Bridged'), (b'routed', b'Routed')])),
                ('cluster_default', models.BooleanField(default=False)),
                ('ipv6_prefix', models.CharField(max_length=255, null=True, blank=True)),
                ('cluster', models.ForeignKey(to='ganeti.Cluster')),
                ('groups', models.ManyToManyField(to='auth.Group', blank=True)),
            ],
        ),
    ]
