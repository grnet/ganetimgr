import requests
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup
import json
from gevent.pool import Pool

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.db import close_old_connections
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import filesizeformat
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from ganeti.models import Cluster, Instance, InstanceAction

from util.client import GanetiApiError


def memsize(value):
    return filesizeformat(value * 1024 ** 2)


def disksizes(value):
    return [filesizeformat(v * 1024 ** 2) for v in value]


def build_instance_list(instances, tag=None):
    if tag:
        result = []
        for i in instances:
            if tag in i.tags:
                result.append(i.name)
    else:
        result = [i.name for i in instances]
    return result


def get_user_instances(user, admin=True, tag=None):
    '''
    Return a list of users instances.
    if admin is false the result will be the instances
    of the user regardless the fact that he has access to all
    of them.
    '''

    instances = []
    error = False

    def _get_instances(cluster):
        try:
            instances.extend(
                build_instance_list(cluster.get_user_instances(user, admin), tag)
            )
        except (GanetiApiError, Exception):
            error = True
        finally:
            close_old_connections()
    p = Pool(20)
    clusters = Cluster.objects.filter(disabled=False)
    p.map(_get_instances, clusters)
    return {'instances': instances, 'errors': error}


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
        # get only enabled clusters
        clusters = Cluster.objects.filter(disabled=False)
    else:
        clusters = Cluster.objects.filter(slug=cluster.slug)
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
            close_old_connections()
    p.map(_get_nodes, clusters)
    return nodes, bad_clusters, bad_nodes


def generate_json(instance, user, locked_nodes):
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
        if i.snodes:
            inst_dict['snodes'] = i.snodes
    else:
        inst_dict['cluster'] = i.cluster.description
        inst_dict['clusterslug'] = i.cluster.slug
    inst_dict['node_group_locked'] = i.pnode in locked_nodes
    inst_dict['memory'] = memsize(i.beparams['maxmem'])
    inst_dict['disk'] = ", ".join(disksizes(i.disk_sizes))
    inst_dict['vcpus'] = i.beparams['vcpus']
    inst_dict['ipaddress'] = [ip for ip in i.nic_ips if ip]
    if not user.is_superuser and not user.has_perm('ganeti.view_instances'):
        inst_dict['ipv6address'] = [ip for ip in i.ipv6s if ip]
    # inst_dict['status'] = i.nic_ips[0] if i.nic_ips[0] else "-"
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
        "instances/emails/reinstall_mail.txt",
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


try:
    from ganetimgr.settings import OPERATING_SYSTEMS_URLS
except ImportError:
    OPERATING_SYSTEMS_URLS = False
else:
    from ganetimgr.settings import OPERATING_SYSTEMS_PROVIDER, OPERATING_SYSTEMS_SSH_KEY_PARAM

try:
    from ganetimgr.settings import SNF_OPERATING_SYSTEMS_URLS
except ImportError:
    SNF_OPERATING_SYSTEMS_URLS = False
else:
    from ganetimgr.settings import OPERATING_SYSTEMS_PROVIDER, OPERATING_SYSTEMS_SSH_KEY_PARAM

try:
    from ganetimgr.settings import OPERATING_SYSTEMS
except ImportError:
    OPERATING_SYSTEMS = False

try:
    from ganetimgr.settings import SNF_IMG_PROPERTIES
except ImportError:
    SNF_IMG_PROPERTIES = False

try:
    from ganetimgr.settings import SNF_IMG_PASSWD
except ImportError:
    SNF_IMG_PASSWD = None


def discover_snf_images():
    snf_images = {}
    if SNF_OPERATING_SYSTEMS_URLS:
        for url in SNF_OPERATING_SYSTEMS_URLS:
            try:
                raw_response = requests.get(url)
            except ConnectionError:
                # fail silently if url is unreachable
                break
            else:
                if raw_response.ok:
                    soup = BeautifulSoup(raw_response.text)
                    extensions = {
                        'img': 'diskdump',
                    }
                    for link in soup.findAll('a'):
                        try:
                            # lets see if the link we've got is an image
                            extension = link.attrs.get('href').split('.')[-1]
                        except IndexError:
                            continue
                        else:
                            if extension in extensions.keys():
                                # in case we have an images lets store it
                                img = '%s%s' % (url, link.attrs.get('href'))
                            else:
                                continue
                            re = requests.get(
                                '%s%s.dsc' % (
                                    url,
                                    link.attrs.get('href')
                                )
                            )
                            if re.ok:
                                description = re.text.strip()
                            else:
                                description = link.attrs.get('href')
                            snf_images.update(
                                {
                                    img: {
                                        'description': description,
                                        'provider': 'snf-image+default',
                                        'osparams': {
                                            'img_id': img,
                                            'img_format': extensions.get(extension),
                                        },
                                        'ssh_key_users': 'root',
                                    },
                                }
                            )
                            if SNF_IMG_PROPERTIES:
                                snf_images.get(img).get('osparams').update(
                                    {
                                        'img_properties': SNF_IMG_PROPERTIES
                                    }
                                )
                            if SNF_IMG_PASSWD is not None:
                                snf_images.get(img).get('osparams').update(
                                    {
                                        'img_passwd': SNF_IMG_PASSWD
                                    }
                                )

        return snf_images
    else:
        return {}


def discover_available_operating_systems():
    operating_systems = {}
    if OPERATING_SYSTEMS_URLS:
        for url in OPERATING_SYSTEMS_URLS:
            try:
                raw_response = requests.get(url)
            except ConnectionError:
                # fail silently if url is unreachable
                continue
            else:
                if raw_response.ok:
                    soup = BeautifulSoup(raw_response.text)
                    extensions = {
                        '.tar.gz': 'tarball',
                        '.img': 'qemu',
                        '-root.dump': 'dump',
                    }
                    architectures = ['-x86_', '-amd' '-i386']
                    for link in soup.findAll('a'):
                        try:
                            if '.' + '.'.join(link.attrs.get('href').split('.')[-2:]) == '.tar.gz':
                                extension = '.tar.gz'
                            elif '.' + '.'.join(link.attrs.get('href').split('.')[-1:]) == '.img':
                                extension = '.img'
                            else:
                                extension = '.' + '.'.join(link.attrs.get('href').split('.')[-1:])
                        # in case of false link
                        except IndexError:
                            pass
                        else:
                            # if the file is tarball, qemu or dump then it is valid
                            if extension in extensions.keys() or '-root.dump' in link.attrs.get('href'):
                                re = requests.get(url + link.attrs.get('href') + '.dsc')
                                if re.ok:
                                    name = re.text
                                else:
                                    name = link.attrs.get('href')
                                for arch in architectures:
                                    if arch in link.attrs.get('href'):
                                        img_id = link.attrs.get('href').replace(extension, '').split(arch)[0]
                                        architecture = arch
                                        break
                                description = name
                                img_format = extensions[extension]
                                if link.attrs.get('href').split('-')[0] == 'nomount':
                                    operating_systems.update({
                                        img_id: {
                                            'description': description,
                                            'provider': OPERATING_SYSTEMS_PROVIDER,
                                            'ssh_key_param': OPERATING_SYSTEMS_SSH_KEY_PARAM,
                                            'arch': architecture,
                                            'osparams': {
                                                'img_id': img_id,
                                                'img_format': img_format,
                                                'img_nomount': 'yes',
                                            }
                                        }
                                    })
                                else:
                                    operating_systems.update({
                                        img_id: {
                                            'description': description,
                                            'provider': OPERATING_SYSTEMS_PROVIDER,
                                            'ssh_key_param': OPERATING_SYSTEMS_SSH_KEY_PARAM,
                                            'arch': architecture,
                                            'osparams': {
                                                'img_id': img_id,
                                                'img_format': img_format,
                                            }
                                        }
                                    })
        return operating_systems
    else:
        return {}


def get_operating_systems_dict():
    if OPERATING_SYSTEMS:
        return OPERATING_SYSTEMS
    else:
        return {}


def operating_systems():
    # check if results exist in cache
    response = cache.get('operating_systems')
    # if no items in cache
    if not response:
        dictionary = get_operating_systems_dict()
        discovery = discover_available_operating_systems()
        snf_discovery = discover_snf_images()
        operating_systems = sorted(dict(
            discovery.items() + dictionary.items() + snf_discovery.items()
        ).items())
        # move 'none' on the top of the list for ui purposes.
        for os in operating_systems:
            if os[0] == 'none':
                operating_systems.remove(os)
                operating_systems.insert(0, os)
        response = json.dumps({'status': 'success', 'operating_systems': operating_systems})
        # add results to cache for one day
        cache.set('operating_systems', response, timeout=86400)
    return response


# find os info given its img_id
def get_os_details(img_id):
    oss = json.loads(operating_systems()).get('operating_systems')
    for os in oss:
        if os[0] == img_id:
            return os[1]
    return False


def refresh_cluster_cache(cluster, instance):
    cluster.force_cluster_cache_refresh(instance)
    for u in User.objects.all():
        cache.delete("user:%s:index:instances" % u.username)
    nodes, bc, bn = prepare_clusternodes()
    cache.set('allclusternodes', nodes, 180)
    cache.set('badclusters', bc, 180)
    cache.set('badnodes', bn, 180)


def clusterdetails_generator(slug):
    cluster_profile = {}
    cluster_profile['slug'] = slug
    cluster = Cluster.objects.get(slug=slug)
    cluster_profile['description'] = cluster.description
    cluster_profile['hostname'] = cluster.hostname
    # We want to fetch info about the cluster per se, networks,
    # nodes and nodegroups plus a really brief instances outline.
    # Nodegroups
    nodegroups = cluster.get_node_group_stack()
    nodes = cluster.get_cluster_nodes()
    # Networks
    networks = cluster.get_networks()
    # Instances later on...
    cluster_profile['clusterinfo'] = cluster.get_cluster_info()
    cluster_profile['clusterinfo']['mtime'] = str(cluster_profile['clusterinfo']['mtime'])
    cluster_profile['clusterinfo']['ctime'] = str(cluster_profile['clusterinfo']['ctime'])
    cluster_profile['nodegroups'] = nodegroups
    cluster_profile['nodes'] = nodes
    cluster_profile['networks'] = networks
    return cluster_profile


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


def prepare_tags(taglist):
    tags = []
    for i in taglist:
        # User
        if i.startswith('u'):
            tags.append(
                "%s:user:%s" % (
                    settings.GANETI_TAG_PREFIX, User.objects.get(
                        pk=i.replace('u_', '')
                    ).username
                )
            )
        # Group
        if i.startswith('g'):
            tags.append("%s:group:%s" % (
                settings.GANETI_TAG_PREFIX,
                Group.objects.get(pk=i.replace('g_', '')).name
            ))
    return list(set(tags))


def format_ganeti_api_error(e):
    if e.args[0][0] == '(':
        message = e.args[0].split(',')[1].replace('(', '').replace(')', '')
    else:
        message = e.args[0]
    return message
