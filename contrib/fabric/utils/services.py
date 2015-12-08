from fabric.operations import sudo


def stop_beanstalk():
    sudo('service beanstalkd stop')


def start_beanstalk():
    sudo('service beanstalkd start')


def restart_beanstalk():
    stop_beanstalk()
    start_beanstalk()


def stop_redis():
    sudo('service redis-server stop')


def start_redis():
    sudo('service redis-server start')


def restart_redis():
    stop_redis()
    start_redis()


def stop_nginx():
    sudo('/etc/init.d/nginx stop')


def start_nginx():
    sudo('/etc/init.d/nginx start')


def restart_nginx():
    stop_nginx()
    start_nginx()


def stop_gunicorn():
    sudo('/etc/init.d/gunicorn stop')


def start_gunicorn(app=None):
    sudo('/etc/init.d/gunicorn start %s' % (app or ''))


def restart_gunicorn(app=None):
    stop_gunicorn()
    start_gunicorn(app)


def stop_uwsgi(app=None):
    sudo('/etc/init.d/uwsgi stop %s' % (app or ''))


def start_uwsgi(app=None):
    sudo('/etc/init.d/uwsgi stop %s' % (app or ''))


def restart_uwsgi(app=None):
    stop_uwsgi(app)
    start_uwsgi(app)
