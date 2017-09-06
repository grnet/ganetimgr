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

sys.path.insert(1, "/srv/ganetimgr")
os.environ['DJANGO_SETTINGS_MODULE'] = 'ganetimgr.settings'
# Since Django1.8 you need to run django.setup() before importing django models
# outside of django
import django
django.setup()

from ganeti.models import Instance
from django.contrib.auth.models import User,Group
from django.core.mail import send_mail
from datetime import datetime, timedelta

LOGFILE='/var/log/vima_policy.log'
exclude_tag='vima:policy:exclude'
logging.basicConfig(level=logging.INFO, filename=LOGFILE, filemode="a+",
                    format="%(asctime)-15s %(levelname)-8s %(message)s")

broken_link_vms=[]
users={}

DAYS=180
IDLEDAYS=15 # Shutdown VMS 15 days after first email
WARNDAYS=15 # send warning email 15 days after shutdown
SHUTDAYS=15 # destroy vms 15 dayes after last warning

IdleSbj='Ανενεργός Λογαριασμός στην υπηρεσία ViMa της ΕΔΕΤ'
IdleMessage= u"""
Λαμβάνετε αυτό το email γιατί ο λογαριασμός σας στην ViMa με username %s
εμφανίζεται ανενεργός για περίοδο μεγαλύτερη των 6 μηνών.

Προκειμένου να διατηρήσετε ενεργό τον λογαριασμό σας, παρακαλώ επισκεφτείτε το
web portal της ViMa (https://vima.grnet.gr) και κάντε login με το username σας
εντός των επόμενων %s ημερολογιακών ημερών -- και στην συνέχεια τουλάχιστον μια
φορά κάθε έξι μήνες. Βεβαιωθείτε επίσης πως τα στοιχεία που έχετε δηλώσει στο
προφίλ σας είναι ενημερωμένα και ακριβή και απενεργοποιήστε η διαγράψτε VMs που
τυχόν δεν χρειάζεστε πλέον.

Σε περίπτωση που δεν επιβεβαιώσετε τον λογαριασμό σας μέσα στο προβλεπόμενο
διάστημα των %s ημερών, ο λογαριασμός θα απενεργοποιηθεί. VMs χωρίς ενεργούς
διαχειριστές θα απενεργοποιούνται (shutdown) αμέσως και θα διαγράφονται μόνιμα
μετά την πάροδο %s ακόμα ημερολογιακών ημερών.

Για οποιαδήποτε ερώτηση ή πληροφορία παρακαλούμε απευθυνθείτε στο support@grnet.gr.

Ευχαριστούμε για την κατανόηση και για την βοήθεια στην βέλτιστη αξιοποίηση των
πόρων της υπηρεσίας ViMa.

Για το NOC της ΕΔΕΤ,
"""
WarnSbj='URGENT: Ανενεργός Λογαριασμός στην υπηρεσία ViMa της ΕΔΕΤ'
WarnMessage= u"""
Λαμβάνετε αυτό το email γιατι ο λογαριασμός σας στην ViMa με username %s
εμφανίζεται ανενεργός για περίοδο μεγαλύτερη των 6 μηνών. Σε συνέχεια της
προηγούμενης ειδοποίησης που σας είχαμε στείλει πρίν απο %s ημέρες, τα VMs
σας, αν έχετε, απενεργοποιήθηκαν (shutdown) πρίν απο %s ημέρες.

Παρακαλούμε επιβεβαιώστε τον λογαριασμό σας κάνοντας ενα απλο login στο
web portal της υπηρεσίας ViMa μέσα στις επόμενες %s ημέρες. Σε αντίθετη
περίπτωση, μετα απο αυτό το χρονικό διάστημα,
τα VMs σας θα διαγραφούν οριστικά (delete).

Για οποιαδήποτε ερώτηση ή πληροφορία παρακαλούμε απευθυνθείτε στο
support@grnet.gr.

Ευχαριστούμε για την κατανόηση και για την βοήθεια στην βέλτιστη αξιοποίηση των
πόρων της υπηρεσίας ViMa.

Για το NOC της ΕΔΕΤ,
"""

BrokenSbj = 'Ανενεργά URLs σε vms της υπηρεσίας ViMA'
BrokenMessage = u"""
Αγαπητέ χρήστη της υπηρεσίας ViMA,

    Τα παρακάτω VM  σας χρησιμοποιούν ώς virtual cdrom, URLs τα οποία δεν ειναι
    ενεργα.
    Παρακαλούμε αφαιρέστε τα ή αντικαταστείστε τα με ενεργά URL.

%s

    Για οποιαδήποτε απορία, παρακαλώ επικοινωνήστε με το Γραφείο Αρωγής Χρηστών
    της ΕΔΕΤ  support@grnet.gr
"""

login_before = datetime.now() - timedelta(days=DAYS)
today = datetime.now().strftime('%Y%m%d')

def find_vm_owner(vm):
    """ Return a list with vm owners """
    owners=[]
    for u in vm.users:
        owners.append(u)
        for g in vm.groups:
            gusers=g.user_set.all()
            for i in gusers:
                owners.append(i)

    owners=list(set(owners))
    return owners


def sendemail(rcpt,sender,message, subj):
    if not dry_run:
        send_mail(subj, message, sender, rcpt)


def user_vms(usr):
    '''Return a list with usr's vms'''
    vms = Instance.objects.filter(user=usr.username)
    return vms


def deactivate_user(usr):
    '''Inactivate a django user'''
    if usr.is_active:
        usr.is_active=False
        usr.save()
    else:
        logging.info("User %s already inactive", usr.username)


def only_active_owner(vm, user):
    owners=find_vm_owner(vm)
    if len(owners) > 1 or len(owners) <1:
        return False
    else:
        if owners[0] == user:
            return True
        else:
            logging.info("Error, user %s not the owner of %s", user, vm)
            return False


def main():
    logging.info("#### The dry mode is %s", "ON" if dry_run else "OFF")
    logging.info("#### Script is checking for %s", "Broken URLS" if \
                  broken_url else "Inactive Users")
    if broken_url:
        for i in Instance.objects.all():
            if i.hvparams['cdrom_image_path']:
                u=i.hvparams['cdrom_image_path']
                try:
                    h=requests.head(u)
                    if not h.ok:
                        broken_link_vms.append(i)
                except requests.ConnectionError:
                    broken_link_vms.append(i)

        for vm in broken_link_vms:
            for vima_user in find_vm_owner(vm):
                if users.has_key(vima_user.email):
                    users[vima_user.email].append(vm)
                else:
                    users.update({vima_user.email: [vm]})

        for vima_user in users:
            urls= ""
            for v in users[vima_user]:
                urls += "\t%s cdrom url: %s\n" % (v.name,
                                                  v.hvparams['cdrom_image_path'])
            if not dry_run:
                sendemail([vima_user], 'noreply@grnet.gr',  BrokenMessage % urls, BrokenSbj)
            logging.info("Sent mail to %s for urls: %s" , vima_user,  urls)


    if check_inactive:
        for group in find_groups('shut_', SHUTDAYS):
            logging.info("Checking group: %s", group)
            check_group(group)

        for group in find_groups('warn_', IDLEDAYS):
            logging.info("Checking group: %s", group)
            check_group(group)

        for group in find_groups('idle_', IDLEDAYS):
            logging.info("Checking group: %s", group)
            check_group(group)

        inactive = User.objects.filter(is_active=True,
        last_login__lt=login_before).exclude(groups__name__startswith='idle_').\
        exclude(groups__name__startswith='shut_').exclude(groups__name__startswith='warn_')
        idlegrp='idle_' + today
        for user in inactive:
            if not dry_run:
                grp=Group.objects.get_or_create(name='idle_' + today)[0]
                user.groups.add(grp)
            logging.info("Sending mail to %s, last login at %s and adding him to %s \
                    group", user.username, user.last_login, idlegrp)
            if not user.email:
                logging.info("Error, user %s has no email address defined", user.username)
            else:
                sendemail([user.email], 'noreply@grnet.gr', IdleMessage % (
                    user.username, IDLEDAYS, IDLEDAYS, SHUTDAYS), IdleSbj)

    logging.info("##### End")


def find_groups(text, days):
    groups=[]
    allgroups = [i.name for i in Group.objects.filter(name__startswith=text)]
    for tmpgroup in allgroups:
        tmp=datetime.strptime(tmpgroup[len(text):], '%Y%m%d') +timedelta(
            days=days)
        if tmp < datetime.now():
            groups.append(tmpgroup)
        else:
            logging.info("Ignoring Group %s", tmpgroup)
    return groups


def check_group(grp):
    users= [i for i in User.objects.filter(groups__name=grp)]
    for user in users:
        logging.info("Info: User %s last login %s before %s", user.username,
                     user.last_login, login_before)
        if user.last_login < login_before:
            logging.info("User %s loggeid before %s, checking", user.username,
                         login_before)
            vms = user_vms(user)
            if len(vms) > 0:
                if grp.startswith('idle_'):
                    logging.info("Added user %s in group %s", user.username,
                                 'warn_' + today)
                    if not dry_run:
                        tmpgrp=Group.objects.get_or_create(name="warn_" + today)[0]
                        user.groups.add(tmpgrp)
                    logging.info("User %s has vms, shut them down", user.username)
                    #- shutdown vms
                    for vm in vms:
                        if not exclude_tag in vm.tags:
                            if only_active_owner(vm, user):
                                if not dry_run:
                                    vm.cluster.shutdown_instance(vm.name)
                                logging.info("Shutting down vm %s", vm.name)
                            else:
                                logging.info("%s Not the only owner of vm %s",
                                             user.username, vm.name)
                        else:
                                logging.info("VM %s tagged with %s and ignored"\
                                "from vima_policy", vm.name, exclude_tag)

                elif grp.startswith('warn_'):
                    logging.info("Info: Send warning  mail to user %s (group=%s)",
                    user.username, grp)
                    logging.info("Info: Add user %s to group %s",
                    user.username, 'shut_' + today)
                    if not dry_run:
                        ### send email
                        sendemail([user.email],
                                  'support@grnet.gr',
                                  WarnMessage % (user.username, IDLEDAYS + WARNDAYS, WARNDAYS, SHUTDAYS),
                                  WarnSbj)
                        ### Add to group shut_today
                        tmpgrp=Group.objects.get_or_create(name="shut_" + today)[0]
                        user.groups.add(tmpgrp)

                elif grp.startswith('shut_'):
                    for vm in vms:
                        if not exclude_tag in vm.tags:
                            if only_active_owner(vm, user):
                                if not dry_run:
                                    vm.cluster.destroy_instance(vm.name)
                                logging.info("VM %s with owner %s has been "\
                                "destroyed", vm.name, user.username)
                            else:
                                logging.info("%s Not the only owner of vm %s",
                                             user.username, vm.name)
                        else:
                                logging.info("VM %s tagged with %s and ignored"\
                                "from vima_policy", vm.name, exclude_tag)

                    if not dry_run:
                        deactivate_user(user)
                    logging.info("Deactivating user %s", user.username)
            else: #User has no vms
                logging.info("User %s  deactivated. Last login: %s, Last "\
                             "notified on %s", user.username, user.last_login,
                             grp)
                if not dry_run:
                    deactivate_user(user)

        ''' Remove user from group '''
        logging.info("Remove %s from group %s", user.username, grp)
        if not dry_run:
            group=Group.objects.get(name=grp)
            group.user_set.remove(user)
            group.save()

    ''' Delete group '''
    logging.info("Deleting group %s ", grp)
    if not dry_run:
        grp=Group.objects.get(name=grp)
        grp.delete()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", help="Test script",
                        action="store_true")
    parser.add_argument("--broken-url", help="Find users with broken"\
                        "cdrom URL", action="store_true")
    parser.add_argument("--check-inactive", help="Find idle vim users",
                        action="store_true")
    args = parser.parse_args()
    dry_run = args.dry_run
    check_inactive = args.check_inactive
    broken_url = args.broken_url

    main()
    sys.exit(0)
