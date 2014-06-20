#
# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright © 2010-2014 Greek Research and Technology Network (GRNET S.A.)
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD
# TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
# OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF
# USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
# TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.

from django.db import models
from django.contrib.auth.models import User


class AuditEntry(models.Model):
    requester = models.ForeignKey(User)
    ipaddress = models.CharField(max_length=255, null=True, blank=True)
    action = models.CharField(max_length=255)
    instance = models.CharField(max_length=255)
    cluster = models.CharField(max_length=50)
    job_id = models.IntegerField(null=True, blank=True)
    recorded = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __unicode__(self):
        return "%s %s %s" %(self.requester, self.action, self.instance)
    
    def update(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)
        self.save()