#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
vima_policy.py is a ganetimgr helper script

It has two main functions:
 - broken-url
 - and check-inactive

broken-url iterates all Ganeti instances that have an HTTP ISO attached and
then checks if the URL is valid (i.e. if the ISO is accessible). If it isn't it
notifies the owner to fix it.

check-inactive is used to find idle users and disable their resources.


Usage:

    vima_policy --broken-url  // Send mail to vima users having broken urls for
                              // virtual cdrom
    vima_policy --check-inactive // Find idle vima users

"""

import os
import sys
import argparse
import logging
import requests
from collections import defaultdict
from itertools import chain
from functools import partial
from datetime import datetime, timedelta

sys.path.insert(1, "/srv/ganetimgr")
os.environ['DJANGO_SETTINGS_MODULE'] = 'ganetimgr.settings'
# Since Django1.8 you need to run django.setup() before importing django models
# outside of django
import django
django.setup()

from django.contrib.auth.models import User, Group
from django.core.mail import send_mail
from django.db import close_old_connections
from django.conf import settings
from ganeti.models import Instance


LOGFILE = '/var/log/vima_policy.log'
logging.basicConfig(level=logging.INFO, filename=LOGFILE, filemode="a+",
                    format="%(asctime)-15s %(levelname)-8s %(message)s")

WARNDAYS = datetime.now() - timedelta(days=180)
IDLEDAYS = WARNDAYS + timedelta(weeks=3)
DESTROYDAYS = datetime.now() - timedelta(days=270)


WEEKLY_WARNING_1 = "warn_1"
WEEKLY_WARNING_2 = "warn_2"
WEEKLY_WARNING_3 = "warn_3"
EXPIRATION_WARNING = "warn_6"
DESTRUCTION_WARNING = "warn_9"

IdleSbj = 'Ανενεργός Λογαριασμός στην υπηρεσία ViMa της ΕΔΕΤ'
IdleMessage = u"""
Λαμβάνετε αυτό το email γιατί ο λογαριασμός σας στην ViMa με username {username}
εμφανίζεται ανενεργός από {last_login}.

Προκειμένου να διατηρήσετε ενεργό τον λογαριασμό σας, παρακαλώ επισκεφτείτε το
web portal της ViMa (https://vima.grnet.gr) και κάντε login με το username σας 
και στην συνέχεια τουλάχιστον μια φορά κάθε έξι μήνες. Βεβαιωθείτε επίσης πως 
τα στοιχεία που έχετε δηλώσει στο προφίλ σας είναι ενημερωμένα και ακριβή και 
απενεργοποιήστε η διαγράψτε VMs που τυχόν δεν χρειάζεστε πλέον.

Σε περίπτωση που δεν επιβεβαιώσετε τον λογαριασμό σας μέσα στο προβλεπόμενο
διάστημα, ο λογαριασμός θα απενεργοποιηθεί. VMs χωρίς ενεργούς
διαχειριστές θα απενεργοποιούνται (shutdown) αμέσως και θα διαγράφονται μόνιμα
μετά την πάροδο 270 ημερολογιακών ημερών.

Για οποιαδήποτε ερώτηση ή πληροφορία παρακαλούμε απευθυνθείτε στο support@grnet.gr.

Ευχαριστούμε για την κατανόηση και για την βοήθεια στην βέλτιστη αξιοποίηση των
πόρων της υπηρεσίας ViMa.

Για το NOC της ΕΔΕΤ,
"""

WarnSbj = 'URGENT: Ανενεργός Λογαριασμός στην υπηρεσία ViMa της ΕΔΕΤ'
WarnMessage = u"""
Λαμβάνετε αυτό το email γιατι ο λογαριασμός σας στην ViMa με username {username}
εμφανίζεται ανενεργός για περίοδο μεγαλύτερη των 6 μηνών. Σε συνέχεια της
προηγούμενης ειδοποίησης που σας είχαμε στείλει, τα VMs
σας, αν έχετε, απενεργοποιήθηκαν (shutdown).

Παρακαλούμε επιβεβαιώστε τον λογαριασμό σας κάνοντας ενα απλο login στο
web portal της υπηρεσίας ViMa μέσα στις επόμενες ημέρες. Σε αντίθετη
περίπτωση, μετα απο αυτό το χρονικό διάστημα, τα VMs σας θα διαγραφούν οριστικά (delete).

Για οποιαδήποτε ερώτηση ή πληροφορία παρακαλούμε απευθυνθείτε στο
support@grnet.gr.

Ευχαριστούμε για την κατανόηση και για την βοήθεια στην βέλτιστη αξιοποίηση των
πόρων της υπηρεσίας ViMa.

Για το NOC της ΕΔΕΤ,
"""


ReactivateSubj = 'Ανανέωση tickets σχετικά με VMs της υπηρεσίας ViMa'
ReactivateMessage = u"""
Τα tickets σχετικά με τα ακόλουθα vms μπορούν να κλείσουν καθώς ένας από τους χρήστες 
είναι πλέον ενεργός:

{vms}
"""

ShutdownSubj = 'Άνοιγμα νέων tickets σχετικά με VMs της υπηρεσίας ViMa'
ShutdownMessage = u"""
Για τα ακόλουθα vms όλοι οι χρήστες πλέον θεωρούνται expired. Τα vms έγιναν 
shutdown και θα πρέπει να ανοιχτούν αντίστοιχα tickets:

{vms}
"""

DestroySubj = 'Ανανέωση tickets σχετικά με VMs της υπηρεσίας ViMa'
DestroyMessage = u"""
Τα tickets σχετικά με τα ακόλουθα vms μπορούν να κλείσουν καθώς όλοι οι χρήστες πλέον 
είναι ανενεργοί. Τα vms θα πρέπει να καταστραφούν: 

{vms}
"""

BrokenSbj = 'Ανενεργά URLs σε vms της υπηρεσίας ViMA'
BrokenMessage = u"""
Αγαπητέ χρήστη της υπηρεσίας ViMA,

    Τα παρακάτω VM  σας χρησιμοποιούν ώς virtual cdrom, URLs τα οποία δεν ειναι
    ενεργα.
    Παρακαλούμε αφαιρέστε τα ή αντικαταστείστε τα με ενεργά URL.

{info}

    Για οποιαδήποτε απορία, παρακαλώ επικοινωνήστε με το Γραφείο Αρωγής Χρηστών
    της ΕΔΕΤ  support@grnet.gr
"""

exclude_tag = 'vima:policy:exclude'
expired_tag = "vima:policy:expired"
destroy_tag = "vima:policy:destroy"


class MiniInstance(object):
    def __init__(self, tags, users, groups, cluster, name):
        self.tags = tags
        self.users = users
        self.groups = groups
        self.cluster = cluster
        self.name = name

    def __repr__(self):
        return self.name


def group_user_instances():
    """
    Create a dictionary with usernames as keys and custom instances as values
    to provide fast user-vms lookup
    """
    user_grp_instances = defaultdict(list)
    for vm in Instance.objects.all():
        for user in vm.users:
            user_grp_instances[user.username].append(
                MiniInstance(vm.tags, vm.users, vm.groups,
                             vm.cluster, vm.name))

    return user_grp_instances


user_groupped_instances = group_user_instances()


def find_vm_owner(vm):
    """ Return a list with vm owners """
    owners = []

    for u in vm.users:
        owners.append(u)
        for g in vm.groups:
            gusers = g.user_set.all()
            for i in gusers:
                owners.append(i)

    return set(owners)


def deactivate_users(users):
    User.objects.filter(
        username__in=[x for x in users]).update(is_active=False)


def check_broken_urls():
    def has_broken_url(vm):
        if vm.hvparams['cdrom_image_path']:
            try:
                return not requests.head(vm.hvparams['cdrom_image_path']).ok
            except requests.ConnectionError:
                return True

    logging.info("#### Script is checking for Broken URLS")
    broken = filter(lambda vm: has_broken_url(vm), Instance.objects.all())

    vms_per_user = defaultdict(list)
    for users, instance in map(lambda vm: (find_vm_owner(vm), vm), broken):
        for user in users:
            vms_per_user[user].append(instance)

    return vms_per_user


def send_broken_url_mails(user, vms):
    urls = "\n".join(map(
        lambda x: "\t{vm} cdrom url: {url}\n".format(
            vm=x.name, url=x.hvparams['cdrom_image_path']),
        vms))

    send_mail(BrokenSbj, BrokenMessage.format(info=urls),
              "noreply@grnet.gr", (user.email,))

    logging.info("Sent mail to {0} for urls: {1}".format(user.email, urls))


def fetch_idle_users(users_base):
    return users_base.filter(last_login__lte=IDLEDAYS, last_login__gt=WARNDAYS)


def fetch_expired_users(users_base):
    return users_base.filter(last_login__lte=WARNDAYS,
                             last_login__gt=DESTROYDAYS)


def fetch_tbdestroyed_users(users_base):
    return users_base.filter(last_login__lte=DESTROYDAYS)


def fetch_inactive_users():
    logging.info("#### Script is checking for Inactive Users")

    active_users = User.objects.filter(is_active=True)

    return tuple(map(
        lambda x: x(active_users),
        (fetch_idle_users, fetch_expired_users, fetch_tbdestroyed_users)))


def categorize_inactive_users(inactive_users):
    def weekly_categorize(u):
        weeks = ((IDLEDAYS - u.last_login).days // 7) + 1
        return "warn_{0}".format(weeks) if weeks < 3 else "warn_3"

    categorized_users = defaultdict(list)
    weekly, expired, tbdeactivated = inactive_users

    for user in weekly:
        categorized_users[weekly_categorize(user)].append(user)

    categorized_users[EXPIRATION_WARNING].extend(expired)
    categorized_users[DESTRUCTION_WARNING].extend(tbdeactivated)

    return categorized_users


def update_groups(categorized_inactive):
    close_old_connections()
    logging.info("Updating groups with current inactive users")
    for category, users in categorized_inactive.items():
        Group.objects.get(name=category).user_set.clear()
        Group.objects.get(name=category).user_set.add(*users)


def get_fresh_categorized_users(categorized_inactive):
    tbnotified = defaultdict(list)
    for category, users in categorized_inactive.items():
        user_ids = [u.id for u in users]
        aff_users = (set(users)
                     - set(Group.objects.get(name=category).user_set.exclude(
                                                            id__in=user_ids)))
        tbnotified[category].extend([x.username for x in aff_users])
    return tbnotified


def notify_freshly_inactive(fresh_inactive):
    def notify(uname, subject, message):
        user = User.objects.get(username=uname)
        send_mail(subject,
                  message.format(username=uname,
                                 last_login=user.last_login.ctime()),
                  "noreply@grnet.gr", [user.email])

    for username in chain(*map(
            lambda x: fresh_inactive[x],
            (WEEKLY_WARNING_1, WEEKLY_WARNING_2, WEEKLY_WARNING_3))):
        notify(username, IdleSbj, IdleMessage)

    for username in fresh_inactive[EXPIRATION_WARNING]:
        notify(username, WarnSbj, WarnMessage)


def activated_users(categorized_inactive):
    return (set(Group.objects.get(name=EXPIRATION_WARNING).user_set.all())
            - (set(categorized_inactive[EXPIRATION_WARNING]).union(
                set(categorized_inactive[DESTRUCTION_WARNING]))))


def fetch_filtered_vms(users, filter_func):
    return filter(
        lambda x: filter_func(x),
        chain(*map(lambda username: user_groupped_instances[username], users)))


def notify_internal(subject, message, vms):
    if vms:
        send_mail(subject,
                  message.format(vms="\n".join(
                      map(lambda vm: vm.name, vms))),
                  "noreply@grnet.gr",
                  ["support@grnet.gr"]
                  + [x[-1] for x in getattr(settings, "MANAGERS", [])])


def should_activate(vm):
    return expired_tag in vm.tags


def is_vm_expired(vm, expired_users):
    return (all(map(lambda x: x.issubset(expired_users),
                    (set(vm.users),
                     set(chain(*map(lambda g: g.user_set.all(), vm.groups))))))
            and exclude_tag not in vm.tags)


def activate(vms):
    for vm in vms:
        vm.cluster.untag_instance(vm.name, [expired_tag])


def shutdown(vms):
    for vm in vms:
        vm.cluster.tag_instance(vm.name, [expired_tag])
        vm.cluster.shutdown_instance(vm.name)


def destroy(vms):
    for vm in vms:
        vm.cluster.tag_instance(vm.name, [destroy_tag])


def create_user_groups():
    logging.info("Creating (if not already) user groups")
    for x in (WEEKLY_WARNING_1, WEEKLY_WARNING_2, WEEKLY_WARNING_3,
              EXPIRATION_WARNING, DESTRUCTION_WARNING):
        Group.objects.get_or_create(name=x)


def fetch_inactivity_actions(categorized_inactive):
    def craft_action_pending_vms(users, action_func):
        return tuple(fetch_filtered_vms(users, action_func))

    fresh_inactive = get_fresh_categorized_users(categorized_inactive)

    expired_users = set(
        chain(*map(lambda group: categorized_inactive[group],
                   [EXPIRATION_WARNING, DESTRUCTION_WARNING]))
    ).union(set(User.objects.filter(is_active=False)))

    return {
        "users": {
            "fresh-inactive": [
                fresh_inactive,
                [("notifying inactive users", notify_freshly_inactive)]
            ],
            "for-deactivation": [
                fresh_inactive[DESTRUCTION_WARNING],
                [("deactivating inactive users", deactivate_users)]
            ]
        },
        "vms": {
            "activation": [
                craft_action_pending_vms(activated_users(categorized_inactive),
                                         should_activate),
                [("activating vms", activate),
                 ("sending internal emails",
                  lambda vms: notify_internal(
                      subject=ReactivateSubj,
                      message=ReactivateMessage, vms=vms))]
            ],
            "shutdown": [
                craft_action_pending_vms(
                    fresh_inactive[EXPIRATION_WARNING],
                    partial(is_vm_expired, expired_users=expired_users)),
                [("shutting down vms", shutdown),
                 ("sending internal emails",
                  lambda vms: notify_internal(
                      subject=ShutdownSubj, message=ShutdownMessage, vms=vms))]
            ],
            "destruction": [
                craft_action_pending_vms(
                    fresh_inactive[DESTRUCTION_WARNING],
                    partial(is_vm_expired, expired_users=expired_users)),
                [("marking vms for destruction", destroy),
                 ("sending internal emails",
                  lambda vms: notify_internal(
                      subject=DestroySubj, message=DestroyMessage, vms=vms))]
            ]
        }
    }


def main(dry_run=False, check_inactive=False, check_urls=False):
    def run_if(func, checker):
        if checker:
            func()

    def run_actions():
        logging.info("Running actions about {0}".format(name))
        for info, action in actions:
            logging.info(info)
            action(affected)

    def findings_msg():
        return ("For the group {grp}, the {name} findings are the following:\n"
                "{aff}".format(grp=group, name=name, aff=affected))

    def log_actions():
        logging.info(findings_msg())

    def report_actions():
        print(findings_msg())

    def report_broken_urls():
        print("VMs that have broken urls are the following (per user): {0}"
              .format(broken_urls.items()))

    def notify_broken_urls():
        logging.info("Sending broken url emails")
        for user, vms in broken_urls.items():
            send_broken_url_mails(user, vms)

    logging.info("#### The dry mode is %s", "ON" if dry_run else "OFF")

    if check_urls:
        broken_urls = check_broken_urls()
        run_if(report_broken_urls, dry_run)
        run_if(notify_broken_urls, not dry_run)

    if check_inactive:
        run_if(create_user_groups, not dry_run)
        categorized_inactive_users = categorize_inactive_users(
            fetch_inactive_users())
        groupped_actions = fetch_inactivity_actions(categorized_inactive_users)

        for group, action_group in groupped_actions.items():
            for name, (affected, actions) in action_group.items():
                report_actions() if dry_run else log_actions()
                run_if(run_actions, not dry_run)

        run_if(lambda: update_groups(categorized_inactive_users), not dry_run)

    logging.info("##### End")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", help="Test script",
                        action="store_true", default=False)
    parser.add_argument("--broken-url",
                        help="Find users with broken cdrom URL",
                        action="store_true")
    parser.add_argument("--check-inactive", help="Find idle vim users",
                        action="store_true")
    args = parser.parse_args()

    main(args.dry_run, args.check_inactive, args.broken_url)
