from fabric.api import run
from fabric.operations import sudo


def dump_mysql(settings, target):
    try:
        sudo('mysqldump -u %s --password=%s %s -h %s -P %s > %s' % (
            settings.get('USER'),
            settings.get('PASSWORD'),
            settings.get('NAME'),
            settings.get('HOST') or 'localhost',
            settings.get('PORT') or '13306',
            target
        ))
    except:
        return False
    else:
        return True


def drop_mysql(settings):
    sudo("mysql -u %s --password=%s -h %s -P %s -e 'DROP DATABASE %s'" % (
        settings.get('USER'),
        settings.get('PASSWORD'),
        settings.get('HOST') or 'localhost',
        settings.get('PORT') or '13306',
        settings.get('NAME')
    ))


def create_mysql(settings):
    sudo("mysql -u %s --password=%s -h %s -P %s -e 'CREATE DATABASE %s'" % (
        settings.get('USER'),
        settings.get('PASSWORD'),
        settings.get('HOST') or 'localhost',
        settings.get('PORT') or '13306',
        settings.get('NAME'),
    ))


def import_mysql(settings, dump_path):
    run('mysql -u %s --password=%s -h %s -P %s %s < %s' %
        (
            settings.get('USER'),
            settings.get('PASSWORD'),
            settings.get('HOST') or 'localhost',
            settings.get('PORT') or '13306',
            settings.get('NAME'),
            dump_path
        ))


def recreate_mysql(settings):
    drop_mysql(settings)
    create_mysql(settings)
