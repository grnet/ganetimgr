import os

from datetime import datetime

from fabric.api import cd, run, abort
from fabric.contrib.files import exists
from fabric.operations import sudo


def get_new_version(project_name, target, repository, tag):
    '''
    Fetches selected tag and puts it under the selected
    directory
    '''
    dir_name = '%s-%s' % (project_name, datetime.today().strftime('%Y%m%d%H%M'))
    with cd('/tmp'):
        # remove junk dirs
        if exists(project_name):
            run('rm -rf %s' % project_name)
        if exists(dir_name):
            run('rm -rf %s' % dir_name)
        # fresh clone
        run('git clone %s --quiet' % repository)
        with cd(project_name):
            try:
                # archive tag
                run('git archive --format=tar --prefix=%s/ %s | (cd /tmp/ && tar xf -) ' % (dir_name, tag))
            except:
                abort('Make sure %s exists in the repository.' % tag)
        # rm cloned code
        run('rm -rf %s' % project_name)
        # move into the proper dir
        if exists(os.path.join(target, dir_name)):
            sudo('rm -r %s' % os.path.join(target, dir_name))
        sudo('mv %s %s' % (dir_name, target))
    return os.path.join(target, dir_name)
