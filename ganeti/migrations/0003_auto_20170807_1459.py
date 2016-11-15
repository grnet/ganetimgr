# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ganeti', '0002_custompermission'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='custompermission',
            options={'managed': False, 'permissions': (('view_all_graphs', 'Can view all graphs'), ('can_isolate', 'Can Isolate'), ('can_lock', 'Can Lock'))},
        ),
    ]
