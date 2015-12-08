import os
from fabric.api import run
from fabric.contrib.files import exists
from fabric.operations import sudo
from fabric.context_managers import settings


def get_real_path(project_dir, project):
    link = run('ls -la %s' % os.path.join(project_dir, project))
    return link.split('-> ')[-1]


def new_symlink(new_path, project_dir, project):
    if exists(os.path.join(project_dir, project)):
        sudo('rm %s' % os.path.join(project_dir, project))
    sudo('ln -s %s %s' % (new_path, os.path.join(project_dir, project)))


def try_to_execute(cmd):
    # in case of an error raises exception with
    # the error message
    with settings(warn_only=True):
        result = sudo(cmd)
    if result.failed:
        raise Exception(result.stdout)
