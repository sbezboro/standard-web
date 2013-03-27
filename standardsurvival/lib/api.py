from django.conf import settings
from django.contrib.sites.models import Site

from minecraft_api import MinecraftJsonApi

from standardsurvival.models import *

import rollbar


def get_api(host):
    return MinecraftJsonApi(
        host = host, 
        port = settings.MC_API_PORT, 
        username = settings.MC_API_USERNAME, 
        password = settings.MC_API_PASSWORD, 
        salt = settings.MC_API_SALT
    )


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
