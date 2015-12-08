from fabric.api import cd, run, prefix
from utils.operations import try_to_execute
from fabric.operations import sudo


def collectstatic(path, venv=False):
    with cd(path):
        if venv:
            with prefix(venv):
                try_to_execute('./manage.py collectstatic --noinput')
        else:
            try_to_execute('./manage.py collectstatic --noinput')


def clean_pyc(path):
    with cd(path):
        sudo('find -name "*.pyc" -delete')


def db_config(settings):
    # grep the database settings from settings.py
    database_settings = run(" grep -A10 '\DATABASES = {' %s | grep -E 'NAME|ENGINE|PASSWO|HOST|PORT|USER'" % settings)
    db_settings = {}
    for s in database_settings.split('\n'):
        s = s.strip().split(',')[0].split(':')
        db_settings.update({s[0].split('\'')[1]: s[1].split('\'')[1]})
    return db_settings
