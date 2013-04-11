from django.conf import settings
from django.contrib.sites.models import Site

from minecraft_api import MinecraftJsonApi

from standardweb.models import *

import rollbar

import sys

apis = {}

def _global_console_command(command):
    for server in Server.objects.all():
        api = get_api(server.address)
        
        api.call('runConsoleCommand', command)


def get_api(host):
    if not apis.get(host):
        apis[host] = MinecraftJsonApi(
            host = host, 
            port = settings.MC_API_PORT, 
            username = settings.MC_API_USERNAME, 
            password = settings.MC_API_PASSWORD, 
            salt = settings.MC_API_SALT
        )
    
    return apis[host]


def get_server_status(server):
    api = get_api(server.address)
    
    return api.call('server_status')
    

def announce_player_time(server, player_name, minutes):
    api = get_api(server.address)
    
    api.call('player_time', player_name, minutes)


def forum_post(username, forum_name, topic_name, path):
    base_url = Site.objects.get_current().domain
    
    for server in Server.objects.all():
        try:
            api = get_api(server.address)
            
            api.call('forum_post',
                     username,
                     forum_name,
                     topic_name,
                     '%s%s' % (base_url, path))
        except:
            rollbar.report_exc_info(sys.exc_info())


def set_donator(username):
    _global_console_command('permissions player addgroup %s donator' % username)

