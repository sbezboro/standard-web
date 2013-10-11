from datetime import datetime, timedelta

from standardweb.lib.constants import *
from standardweb.lib.cache import CachedResult
from standardweb.lib import helpers as h

from standardweb.models import *


@CachedResult('player-server-data', time=60)
def get_server_data(server, player):
    """
    Returns a dict of all the data for a particular player on
    a particular server, or None if the player hasn't played on
    the given server yet.
    """
    stats = PlayerStats.get_object_or_none(server=server, player=player)
    if not stats:
        return stats
    
    death_info = {}
    pvp_deaths = {}
        
    deaths = DeathEvent.objects.filter(server=server, victim=player).values('killer__username', 'killer__nickname', 'death_type__displayname')
    death_count = len(deaths)
    
    pvp_kill_count = len(DeathEvent.objects.filter(server=server, killer=player, victim__isnull=False))
    pvp_death_count = len(DeathEvent.objects.filter(server=server, victim=player, killer__isnull=False))
    other_death_count = len(DeathEvent.objects.filter(server=server, victim=player, killer__isnull=True))
    
    nicknames = {}
    
    for death in deaths:
        death_type = death.get('death_type__displayname')
        if death_type:
            death_info[death_type] = death_info.get(death_type, 0) + 1
    
        if death.get('killer__username'):
            username = death.get('killer__username')
            pvp_deaths[username] = pvp_deaths.get(username, 0) + 1
            
            nickname = death.get('killer__nickname')
            if nickname:
                nicknames[username] = nickname
            
            
    death_info = sorted([{'type': key, 'count': death_info[key]} for key in death_info], key=lambda k: (-k['count'], k['type']))
    pvp_deaths = sorted([{'username': key, 'nickname': nicknames.get(key), 'count': pvp_deaths[key]} for key in pvp_deaths], key=lambda k: (-k['count'], (k['nickname'] or k['username']).lower()))
    
    kill_info = {}
    pvp_kills = {}
    
    kills = KillEvent.objects.filter(server=server, killer=player).values('kill_type__displayname')
    kill_count = len(kills)
    
    other_kill_count = len(KillEvent.objects.filter(server=server, killer=player, victim__isnull=True))
    
    for kill in kills:
        kill_type = kill.get('kill_type__displayname')
        
        kill_info[kill_type] = kill_info.get(kill_type, 0) + 1
    
    kill_info = sorted([{'type': key, 'count': kill_info[key]} for key in kill_info], key=lambda k: (-k['count'], k['type']))
    
    kills = DeathEvent.objects.filter(server=server, killer=player).values('victim__username', 'victim__nickname')
    kill_count = kill_count + len(kills)
    for kill in kills:
        username = kill.get('victim__username')
        pvp_kills[username] = pvp_kills.get(username, 0) + 1
        
        nickname = kill.get('victim__nickname')
        if nickname:
            nicknames[username] = nickname
    
    pvp_kills = sorted([{'username': key, 'nickname': nicknames.get(key), 'count': pvp_kills[key]} for key in pvp_kills], key=lambda k: (-k['count'], (k['nickname'] or k['username']).lower()))
    
    online_now = datetime.utcnow() - timedelta(minutes=1) < stats.last_seen
    
    online_data = []
    last_week = datetime.utcnow() - timedelta(days=7)
    activities = PlayerActivity.objects.filter(server=server, player=player, timestamp__gt=last_week)
    
    for activity in activities:
        online_data.append((activity.timestamp, activity.activity_type))
    
    if activities:
        if online_data[0][1] == PLAYER_ACTIVITY_TYPES['exit']:
            online_data.insert((last_week, PLAYER_ACTIVITY_TYPES['enter']))
        
        if online_data[-1][1] == PLAYER_ACTIVITY_TYPES['enter']:
            online_data.append((datetime.utcnow(), PLAYER_ACTIVITY_TYPES['exit']))
    
    return {
        'rank': stats.get_rank(),
        'banned': stats.banned,
        'online_data': online_data,
        'online_now': online_now,
        'first_seen': h.iso_date(stats.first_seen),
        'last_seen': h.iso_date(stats.last_seen),
        'time_spent': h.elapsed_time_string(stats.time_spent),
        'death_info': death_info,
        'death_count': death_count,
        'kill_info': kill_info,
        'kill_count': kill_count,
        'pvp_kills': pvp_kills,
        'pvp_deaths': pvp_deaths,
        'pvp_death_count': pvp_death_count,
        'pvp_kill_count': pvp_kill_count,
        'other_death_count': other_death_count,
        'other_kill_count': other_kill_count,
        'pvp_logs': stats.pvp_logs
    }
