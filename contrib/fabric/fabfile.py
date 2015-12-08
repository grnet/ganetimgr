# fab --fabfile=ganetimgr deploy:tag='v1.6' -H ganetimgr.vm.grnet.gr -u staurosk

from __future__ import with_statement
import os

from fabric.api import run, cd, abort
from fabric.contrib.files import exists
from fabric.operations import sudo
from fabric.contrib.console import confirm
from fabric.utils import warn

from utils import services, database, git, django, operations
repository = 'https://github.com/grnet/ganetimgr/'

project_name = __file__.split('/')[-1].split('.')[0]


def stop():
    services.stop_beanstalk
    services.stop_redis
    sudo('touch /srv/maintenance.on')


def check_if_old(project_dir):
    return exists(os.path.join(project_dir, project_name))


def create_db_dict(config_files):
    for f in config_files:
        if 'settings.py' in f:
            settings_file = f.split('.dist')[0]
            if exists(settings_file):
                break
            else:
                warn('No settings file found from previous installation')
                return False
    return django.db_config(settings_file)


def dump_db(config_files):
    db_settings = create_db_dict(config_files)
    success = False
    dump_path = '/tmp/%s.sql' % project_name
    if db_settings:
        success = database.dump_mysql(db_settings, dump_path)
    if not success:
        warn('Could not get db dump...')
        if not confirm('Continue?'):
            abort('Aborting...')
    return dump_path if success else False


def get_files_from_old_instance(project_dir):
    realpath = operations.get_real_path(project_dir, project_name)
    previous_config = [f.split('.dist')[0] for f in get_dist_files(os.path.join(project_dir, realpath))]
    return previous_config


def get_dist_files(path):
    return run('find %s -name *.dist' % path).split()


def configure(config_files, path):
    dist_files = get_dist_files(path)
    new_config_files = []
    for f in dist_files:
        # copy dist file to installation
        sudo('cp %s %s' % (f, f.split('.dist')[0]))
        new_config_files.append(f.split('.dist')[0])
    if not config_files:
        config_files = new_config_files
        old_config = False
    else:
        old_config = True
    for f in config_files:
        name = f.split('/')[-1]
        for d in dist_files:

            if name in d and old_config:
                # check if there are differences in between new
                # dist files and old ones
                try:
                    run('diff %s %s.dist' % (d, f))
                except:
                    # if diff has an output
                    same_dist = False
                else:
                    same_dist = True

                if not same_dist:
                    same_dist = confirm('Dist files differ. Apply old %s?' % ' '.join(config_files))
                # copy file from previous installation if it exists
                # and the user tells you to (in case of differences)
                if same_dist and exists(f):
                    warn('Copying old %s' % f.split('/')[-1])
                    sudo('cp %s %s' % (f, d.split('.dist')[0]))
                else:
                    warn('Copying %s' % d)
                    sudo('cp %s %s' % (d, d.split('.dist')[0]))
    for f in config_files:
        if not confirm('Please make sure %s is configured!' % d.split('.dist')[0]):
            return False
    with cd(path):
        while True:
            # we have to execute the following commands in order
            # to move on. In case they fail we have to do some more
            # editing in settings py probably.
            try:
                operations.try_to_execute('./manage.py syncdb --noinput')
                operations.try_to_execute('./manage.py migrate')
                operations.try_to_execute('./manage.py collectstatic --noinput')
            except Exception as e:
                if not confirm('%s. Retry?' % e):
                    return False
            else:
                return True


def rollback_db(project_dir='/srv/', dump_path='/tmp/%s.sql' % project_name):
    config_files = get_dist_files('%s/%s/' % (project_dir, project_name))
    db_settings = create_db_dict(config_files)
    database.recreate_mysql(db_settings)
    with cd('%s/%s/' % (project_dir, project_name)):
        operations.try_to_execute('./manage.py syncdb --noinput')
        operations.try_to_execute('./manage.py migrate')
        # translations
        operations.try_to_execute('./manage.py compilemessages')
    database.import_mysql(db_settings, dump_path)


def start():
    services.start_beanstalk()
    services.start_redis()
    services.restart_gunicorn()
    # sudo('watcher')
    services.restart_nginx()
    if exists('/srv/maintenance.on'):
        sudo('rm /srv/maintenance.on')


def remove_old_installations(project_dir):
    with cd(project_dir):
        result = run("ls -t | grep ganetimgr-| awk 'NR>4'")
        files = result.split()
        if confirm('delete theses directories? %s' % files):
            sudo("rm -r `ls -t | grep ganetimgr-| awk 'NR>4'`")


def deploy(tag='master', project_dir='/srv/'):
    config_files = []
    # stop running services
    stop()
    # check if there is an old instance under /srv/ganetimgr
    if check_if_old(project_dir):
        config_files = get_files_from_old_instance(project_dir)
        dump_path = dump_db(config_files)
    path = git.get_new_version(project_name, project_dir, repository, tag)
    if configure(config_files, path):
        operations.new_symlink(path, project_dir, project_name)
        django.collectstatic(os.path.join(project_dir, project_name))
    else:
        if check_if_old(project_dir):
            if confirm('Rollback?'):
                # in case ther is an old installation we have to just restart
                # the services.
                if dump_path:
                    rollback_db(project_dir, dump_path)
    django.clean_pyc(os.path.join(project_dir, project_name))
    if confirm('remove old installations (keeps the last 3)?', default=True):
        remove_old_installations(project_dir)
    start()
