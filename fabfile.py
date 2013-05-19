import getpass
import os
import sys

from fabric.api import run, local, cd, env, roles, execute, prefix
import requests

import standardweb.local_settings as settings

CODE_DIR = '/home/sbezboro/standard-web'
ENV_DIR = '/home/sbezboro/standard-web-env'
WEB_SERVICE = 'standard-web'

env.roledefs = {
    'web': ['standardsurvival.com']
}

def deploy():
    local("git pull")

    execute(update_and_restart_webs)

    rollbar_record_deploy()
    
    
@roles('web')
def update_and_restart_webs():
    with cd(CODE_DIR):
        with prefix('source %s/bin/activate' % ENV_DIR):
            run("git pull")
            result = run("pip install -r requirements.txt --quiet")
            if result.failed:
                abort('Could not install required packages. Aborting.')
            
            run('service %s restart' % WEB_SERVICE)


def rollbar_record_deploy():
    access_token = settings.ROLLBAR['access_token']
    environment = 'production'

    username = local('whoami', capture=True)
    revision = local('git log -n 1 --pretty=format:"%H"', capture=True)

    resp = requests.post('https://api.rollbar.com/api/1/deploy/', {
        'access_token': access_token,
        'environment': environment,
        'local_username': username,
        'rollbar_username': username,
        'revision': revision
    }, timeout=3)

    if resp.status_code == 200:
        print "Deploy recorded successfully."
    else:
        print "Error recording deploy:", resp.text
