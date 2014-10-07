# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from ganeti.models import InstanceAction


def check_mail_change_pending(user):
    actions = []
    pending_actions = InstanceAction.objects.filter(applicant=user, action=4)
    for pending in pending_actions:
        if pending.activation_key_expired():
            continue
        actions.append(pending)
    if len(actions) == 0:
        return False
    elif len(actions) == 1:
        return True
    else:
        return False


def prepare_cluster_node_group_stack(cluster):
    cluster_info = cluster.get_cluster_info()
    len_instances = len(cluster.get_cluster_instances())
    res = {}
    res['slug'] = cluster.slug
    res['cluster_id'] = cluster.pk
    res['num_inst'] = len_instances
    res['description'] = cluster.description
    res['disk_templates'] = cluster_info['ipolicy']['disk-templates']
    res['node_groups'] = cluster.get_node_group_stack()
    return res
