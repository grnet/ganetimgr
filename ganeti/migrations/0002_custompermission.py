# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ganeti', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomPermission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
                'managed': False,
                'permissions': (('view_all_graphs', 'Can view all graphs'),),
            },
        ),
    ]
