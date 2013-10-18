from django.conf import settings
from django.contrib.sites.models import Site

from minecraft_api import MinecraftJsonApi

from standardweb.models import *
from standardweb.lib.constants import *

import rollbar

apis = {}

def _global_console_command(command):
    for server in Server.objects.all():
        api = get_api(server.address)
        
        api.call('runConsoleCommand', command)


def _api_call(server, type, data=None):
    api = get_api(server.address)
    
    if data:
        result = api.call(type, {
            'data': data
        })
    else:
        result = api.call(type)
    
    if result.get('result') == API_CALL_RESULTS['exception']:
        extra_data = {
            'server_id': server.id,
            'message': result.get('message'),
            'data': data
        }
        
        rollbar.report_message('Exception while calling server API', level='error',
                               extra_data=extra_data)
    
    return result


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
    return _api_call(server, 'server_status').get('data')


def send_player_stats(server, stats):
    _api_call(server, 'player_stats', data=stats)


def send_stats(server, data):
    _api_call(server, 'stats', data=data)


def forum_post(username, forum_name, topic_name, path):
    base_url = Site.objects.get_current().domain
    
    for server in Server.objects.all():
        try:
            data = {
                'username': username,
                'forum_name': forum_name,
                'topic_name': topic_name,
                'path': '%s%s' % (base_url, path)
            }
            _api_call(server, 'forum_post', data=data)
        except:
            rollbar.report_exc_info()


def set_donator(username):
    _global_console_command('permissions player addgroup %s donator' % username)

