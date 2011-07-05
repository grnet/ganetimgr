# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        
        # Adding field 'Cluster.fast_create'
        db.add_column('ganeti_cluster', 'fast_create', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True), keep_default=False)
    
    
    def backwards(self, orm):
        
        # Deleting field 'Cluster.fast_create'
        db.delete_column('ganeti_cluster', 'fast_create')
    
    
    models = {
        'ganeti.cluster': {
            'Meta': {'object_name': 'Cluster'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'fast_create': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'port': ('django.db.models.fields.PositiveIntegerField', [], {'default': '5080'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'})
        }
    }
    
    complete_apps = ['ganeti']
