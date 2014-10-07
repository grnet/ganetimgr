from gevent.pool import Pool

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.db import close_connection
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import filesizeformat
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from ganeti.models import Instance, Cluster, InstanceAction
from util.client import GanetiApiError


def memsize(value):
    return filesizeformat(value * 1024 ** 2)


def disksizes(value):
    return [filesizeformat(v * 1024 ** 2) for v in value]


def get_instance_data(instance, cluster, node=None):
    instance.cpu_url = reverse(
        'graph',
        args=(cluster.slug, instance.name, 'cpu-ts')
    )
    instance.net_url = []
    for (nic_i, link) in enumerate(instance.nic_links):
        instance.net_url.append(
            reverse(
                'graph',
                args=(
                    cluster.slug,
                    instance.name,
                    'net-ts',
                    '/eth%s' % nic_i
                )
            )
        )
    return {
        'node': instance.pnode,
        'name': instance.name,
        'cluster': instance.cluster.slug,
        'cpu': instance.cpu_url,
        'network': instance.net_url,
    }


def get_nodes_with_graphs(cluster_slug, nodes=None):
    cluster = Cluster.objects.get(slug=cluster_slug)
    instances = Instance.objects.filter(cluster=cluster)
    response = []
    for i in instances:
        # if we have set a nodes, then we should check if the
        # instance belongs to them
        if not nodes:
            response.append(get_instance_data(i, cluster))
        else:
            for node in nodes:
                if i.pnode == node:
                    response.append(get_instance_data(i, cluster, node))
    return response


def prepare_clusternodes(cluster=None):
    if not cluster:
        clusters = Cluster.objects.all()
    else:
        clusters = Cluster.objects.filter(slug=cluster)
    p = Pool(15)
    nodes = []
    bad_clusters = []
    bad_nodes = []

    def _get_nodes(cluster):
        try:
            for node in cluster.get_cluster_nodes():
                nodes.append(node)
                if node['offline'] is True:
                    bad_nodes.append(node['name'])
        except (GanetiApiError, Exception):
            cluster._client = None
            bad_clusters.append(cluster)
        finally:
            close_connection()
    p.imap(_get_nodes, clusters)
    p.join()
    return nodes, bad_clusters, bad_nodes


def generate_json(instance, user):
    jresp_list = []
    i = instance
    inst_dict = {}
    if not i.admin_view_only:
        inst_dict['name_href'] = "%s" % (
            reverse(
                'instance-detail',
                kwargs={
                    'cluster_slug': i.cluster.slug, 'instance': i.name
                }
            )
        )
    inst_dict['name'] = i.name
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['cluster'] = i.cluster.slug
        inst_dict['pnode'] = i.pnode
    else:
        inst_dict['cluster'] = i.cluster.description
        inst_dict['clusterslug'] = i.cluster.slug
    inst_dict['node_group_locked'] = i.cluster.check_node_group_lock_by_node(
        i.pnode
    )
    inst_dict['memory'] = memsize(i.beparams['maxmem'])
    inst_dict['disk'] = ", ".join(disksizes(i.disk_sizes))
    inst_dict['vcpus'] = i.beparams['vcpus']
    inst_dict['ipaddress'] = [ip for ip in i.nic_ips if ip]
    if not user.is_superuser and not user.has_perm('ganeti.view_instances'):
        inst_dict['ipv6address'] = [ip for ip in i.ipv6s if ip]
    #inst_dict['status'] = i.nic_ips[0] if i.nic_ips[0] else "-"
    if i.admin_state == i.oper_state:
        if i.admin_state:
            inst_dict['status'] = "Running"
            inst_dict['status_style'] = "success"
        else:
            inst_dict['status'] = "Stopped"
            inst_dict['status_style'] = "important"
    else:
        if i.oper_state:
            inst_dict['status'] = "Running"
        else:
            inst_dict['status'] = "Stopped"
        if i.admin_state:
            inst_dict['status'] = "%s, should be running" % inst_dict['status']
        else:
            inst_dict['status'] = "%s, should be stopped" % inst_dict['status']
        inst_dict['status_style'] = "warning"
    if i.status == 'ERROR_nodedown':
        inst_dict['status'] = "Generic cluster error"
        inst_dict['status_style'] = "important"

    if i.adminlock:
        inst_dict['adminlock'] = True

    if i.isolate:
        inst_dict['isolate'] = True

    if i.needsreboot:
        inst_dict['needsreboot'] = True

    # When renaming disable clicking on instance for everyone
    if hasattr(i, 'admin_lock'):
        if i.admin_lock:
            try:
                del inst_dict['name_href']
            except KeyError:
                pass

    if i.joblock:
        inst_dict['locked'] = True
        inst_dict['locked_reason'] = "%s" % ((i.joblock).capitalize())
        if inst_dict['locked_reason'] in ['Deleting', 'Renaming']:
            try:
                del inst_dict['name_href']
            except KeyError:
                pass
    if 'cdrom_image_path' in i.hvparams.keys():
        if i.hvparams['cdrom_image_path'] and i.hvparams['boot_order'] == 'cdrom':
            inst_dict['cdrom'] = True
    inst_dict['nic_macs'] = ', '.join(i.nic_macs)
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['nic_links'] = ', '.join(i.nic_links)
        inst_dict['network'] = []
        for (nic_i, link) in enumerate(i.nic_links):
            if i.nic_ips[nic_i] is None:
                inst_dict['network'].append("%s" % (i.nic_links[nic_i]))
            else:
                inst_dict['network'].append(
                    "%s@%s" % (i.nic_ips[nic_i], i.nic_links[nic_i])
                )
        inst_dict['users'] = [
            {
                'user': user_item.username,
                'email': user_item.email,
                'user_href': "%s" % (
                    reverse(
                        "user-info",
                        kwargs={
                            'type': 'user',
                            'usergroup': user_item.username
                        }
                    )
                )
            } for user_item in i.users]
        inst_dict['groups'] = [
            {
                'group': group.name,
                'groupusers': [
                    "%s,%s" % (u.username, u.email) for u in group.userset
                ],
                'group_href':"%s" % (
                    reverse(
                        "user-info",
                        kwargs={
                            'type': 'group',
                            'usergroup': group.name
                        }
                    )
                )
            } for group in i.groups
        ]
    jresp_list.append(inst_dict)
    return jresp_list


def generate_json_light(instance, user):
    jresp_list = []
    i = instance
    inst_dict = {}
    if not i.admin_view_only:
        inst_dict['name_href'] = "%s" % (
            reverse(
                "instance-detail",
                kwargs={
                    'cluster_slug': i.cluster.slug,
                    'instance': i.name
                }
            )
        )
    inst_dict['name'] = i.name
    inst_dict['clusterslug'] = i.cluster.slug
    inst_dict['memory'] = i.beparams['maxmem']
    inst_dict['vcpus'] = i.beparams['vcpus']
    inst_dict['disk'] = sum(i.disk_sizes)
    if user.is_superuser or user.has_perm('ganeti.view_instances'):
        inst_dict['users'] = [
            {
                'user': user_item.username
            } for user_item in i.users
        ]
    jresp_list.append(inst_dict)
    return jresp_list


def clear_cluster_user_cache(username, cluster_slug):
    cache.delete("user:%s:index:instances" % username)
    cache.delete("cluster:%s:instances" % cluster_slug)


def notifyuseradvancedactions(
    user,
    cluster_slug,
    instance,
    action_id,
    action_value,
    new_operating_system
):
    action_id = int(action_id)
    if action_id not in [1, 2, 3]:
        action = {'action': _("Not allowed action")}
        return action
    cluster = get_object_or_404(Cluster, slug=cluster_slug)
    instance = cluster.get_instance_or_404(instance)
    reinstalldestroy_req = InstanceAction.objects.create_action(
        user,
        instance,
        cluster,
        action_id,
        action_value,
        new_operating_system
    )
    fqdn = Site.objects.get_current().domain
    url = "https://%s%s" % \
        (
            fqdn,
            reverse(
                "reinstall-destroy-review",
                kwargs={
                    'application_hash': reinstalldestroy_req.activation_key,
                    'action_id': action_id
                }
            )
        )
    email = render_to_string(
        "reinstall_mail.txt",
        {
            "instance": instance,
            "user": user,
            "action": reinstalldestroy_req.get_action_display(),
            "action_value": reinstalldestroy_req.action_value,
            "url": url,
            "operating_system": reinstalldestroy_req.operating_system
        }
    )
    if action_id == 1:
        action_mail_text = _("re-installation")
    if action_id == 2:
        action_mail_text = _("destruction")
    if action_id == 3:
        action_mail_text = _("rename")
    try:
        send_mail(
            _("%(pref)sInstance %(action)s requested: %(instance)s") % {
                "pref": settings.EMAIL_SUBJECT_PREFIX,
                "action": action_mail_text,
                "instance": instance.name
            },
            email,
            settings.SERVER_EMAIL,
            [user.email]
        )
    # if anything goes wrong do nothing.
    except:
        # remove entry
        reinstalldestroy_req.delete()
        action = {'action': _("Could not send email")}
    else:
        action = {'action': _("Mail sent")}
    return action
