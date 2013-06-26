"""
Script that should run every minute. Collects and stores stats from all servers to the db.
"""

import glob
import json
import os
import sys
import urllib2
os.environ['DJANGO_SETTINGS_MODULE'] = 'standardweb.settings'

import rollbar

from django.conf import settings

from standardweb.models import *
from standardweb.lib import api
from standardweb.lib import helpers as h

from datetime import datetime, timedelta

def query(server):
    try:
        server_status = api.get_server_status(server)
    except:
        server_status = {}
    
    stats = []
    
    for player_info in server_status.get('players', []):
        try:
            player = MinecraftPlayer.objects.get(username=player_info.get('username'))
        except:
            player = MinecraftPlayer(username=player_info.get('username'))
            player.save()
        
        if server.id == 2:
            nickname_ansi = player_info.get('nickname_ansi')
            nickname = player_info.get('nickname')
            
            player.nickname_ansi = nickname_ansi
            player.nickname = nickname
            player.save()
        
        ip = player_info.get('address')
        
        if ip:
            try:
                existing_player_ip = IPTracking.objects.get(ip=ip, player=player)
            except:
                existing_player_ip = IPTracking(ip=ip, player=player)
                existing_player_ip.save()
        
        try:
            player_stats = PlayerStats.objects.get(server=server, player=player)
            player_stats.last_seen = datetime.utcnow()
        except:
            player_stats = PlayerStats(server=server, player=player)
        
        player_stats.time_spent += 1
        player_stats.save()
        
        stats.append({
            'username': player.username,
            'minutes': player_stats.time_spent,
            'rank': player_stats.get_rank()
        })
    
    api.send_player_stats(server, stats)
    
    banned_players = server_status.get('banned_players', [])
    PlayerStats.objects.filter(server=server, player__username__in=banned_players).update(banned=True)
    PlayerStats.objects.filter(server=server).exclude(player__username__in=banned_players).update(banned=False)
    
    player_count = server_status.get('numplayers', 0) or 0
    cpu_load = server_status.get('load', 0) or 0
    tps = server_status.get('tps', 0) or 0
    
    status = ServerStatus(server=server, player_count=player_count, cpu_load=cpu_load, tps=tps)
    status.save()

def main():
    for server in Server.objects.all():
        try:
            query(server)
        except:
            rollbar.report_exc_info(sys.exc_info())
    
    try:
        response = urllib2.urlopen('http://status.mojang.com/check')
        result = json.loads(response.read())
    
        website = result[0].get('minecraft.net') == 'green'
        login = result[1].get('login.minecraft.net') == 'green'
        session = result[2].get('session.minecraft.net') == 'green'
        account = result[3].get('account.mojang.com') == 'green'
        auth = result[4].get('auth.mojang.com') == 'green'
        skins = result[5].get('skins.minecraft.net') == 'green'
    except:
        website = False
        login = False
        session = False
        account = False
        auth = False
        skins = False
    
    mojang_status = MojangStatus(website=website,
                                 login=login, session=session,
                                 account=account,
                                 auth=auth,
                                 skins=skins)
    mojang_status.save()    


if __name__ == '__main__':
    rollbar.init(settings.ROLLBAR['access_token'], settings.ROLLBAR['environment'])
    
    try:
        main()
    except:
        rollbar.report_exc_info(sys.exc_info())