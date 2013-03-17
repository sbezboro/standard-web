import glob
import json
import os
import sys
import urllib2
os.environ['DJANGO_SETTINGS_MODULE'] = 'standardsurvival.settings'

from django.conf import settings

from standardsurvival.models import *
from minecraft_api import MinecraftJsonApi

from datetime import datetime, timedelta

try:
    api = MinecraftJsonApi(
        host = settings.MC_API_HOST, 
        port = settings.MC_API_PORT, 
        username = settings.MC_API_USERNAME, 
        password = settings.MC_API_PASSWORD, 
        salt = settings.MC_API_SALT
    )
    
    server_status = api.call('server_status')
except:
    server_status = {}

for player_info in server_status.get('players', []):
    try:
        player = MinecraftPlayer.objects.get(username=player_info.get('username'))
        player.last_seen = datetime.utcnow()
        player.banned = False
    except:
        player = MinecraftPlayer(username=player_info.get('username'))
    
    player.nickname = player_info.get('nickname')
    
    player.time_spent = player.time_spent + 1
    player.save()
    
    if player.time_spent % 6000 == 0:
        api.call('player_time', player.username, player.time_spent)

banned_players = MinecraftPlayer.objects.filter(username__in=server_status.get('banned_players', [])).update(banned=True)

player_count = server_status.get('numplayers', 0)
cpu_load = os.getloadavg()[0]

status = ServerStatus(player_count=player_count, cpu_load=cpu_load)
status.save()

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

mojang_status = MojangStatus(website = website, login = login, session = session, account = account, auth = auth, skins = skins)
mojang_status.save()