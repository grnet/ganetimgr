*************************
Development documentation
*************************

The following instructions are meant *only* for developers. Do NOT use them to setup a production ganetimgr service.

python packages
###############

A requirements.txt file is included in order to help you install the required python dependencies.
You can do that by running::

    pip install -r requirements.txt

How to update/test
##################

We have created a fabric sript in order to set up and deploy ganetimgr. It is included under "contrib/fabric/". One can use it by running::

    fab deploy:tag='v1.6.0' -H ganetimgr.example.com -u user

You will need to have fabric installed though.

This scrip will connect to the specified server and try to set up ganetimgr under "/srv/ganetimgr" which will be a symlink to the actual directory.

In general it performs the following steps:

 - stop redis, beanstalk, touch "/srv/maintenance.on"
 - git clone, git archive under "/tmp" and move to "/srv/ganetimgr<year><month><day><hour><minute>"
 - check if there is an old installation under /srv/ganetimgr and get all the dist files in order to compare them with the newer version
 - create a buckup of the database
 - If no differences have been found between the two versions of ganetimgr, the old configuration files (whatever has also a dist file) will be copied to the new installation.
 - "/srv/ganetimgr" will be point to the new installation
 - management commands (migrate, collectstatic) will be run
 - fabric will ask your permission to remove old installations
 - restart nginx, gunicorn, redis, beanstalk, rm "maintenance.on"
 - in case something goes wrong it will try to make a rollback
 - in case no older installations exist or the dist files, it will ask you to log in the server and edit the settings, while waiting for your input.
