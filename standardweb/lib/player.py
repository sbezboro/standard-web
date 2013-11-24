from datetime import datetime, timedelta

from standardweb.lib import helpers as h

from standardweb.models import *


def get_server_data(server, player):
    """
    Returns a dict of all the data for a particular player on
    a particular server, or None if the player hasn't played on
    the given server yet.
    """
    stats = PlayerStats.get_object_or_none(server=server, player=player)
    if not stats:
        return stats

    pvp_kills = []
    pvp_deaths = []
    other_kills = []
    other_deaths = []

    pvp_kill_count = 0
    pvp_death_count = 0
    other_kill_count = 0
    other_death_count = 0

    nickname_map = {}

    deaths = DeathCount.objects.filter(server=server, victim=player).select_related('killer', 'death_type')
    kills = KillCount.objects.filter(server=server, killer=player).select_related('victim', 'kill_type')

    for death in deaths:
        if death.killer:
            pvp_deaths.append({
                'player': death.killer,
                'count': death.count
            })
            pvp_death_count += death.count
        else:
            other_deaths.append({
                'type': death.death_type.displayname,
                'count': death.count
            })
            other_death_count += death.count

    for kill in kills:
        other_kills.append({
            'type': kill.kill_type.displayname,
            'count': kill.count
        })
        other_kill_count += kill.count

    kills = DeathCount.objects.filter(server=server, killer=player).select_related('victim', 'death_type')

    for kill in kills:
        pvp_kills.append({
            'player': kill.victim,
            'count': kill.count
        })
        pvp_kill_count += kill.count

    pvp_kills = sorted(pvp_kills, key=lambda k: (-k['count'], (k['player'].displayname).lower()))
    pvp_deaths = sorted(pvp_deaths, key=lambda k: (-k['count'], (k['player'].displayname).lower()))
    other_deaths = sorted(other_deaths, key=lambda k: (-k['count'], k['type']))
    other_kills = sorted(other_kills, key=lambda k: (-k['count'], k['type']))

    online_now = datetime.utcnow() - timedelta(minutes=1) < stats.last_seen

    '''
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
    '''

    return {
        'rank': stats.get_rank(),
        'banned': stats.banned,
        'online_now': online_now,
        'first_seen': h.iso_date(stats.first_seen),
        'last_seen': h.iso_date(stats.last_seen),
        'time_spent': h.elapsed_time_string(stats.time_spent),
        'pvp_kills': pvp_kills,
        'pvp_deaths': pvp_deaths,
        'other_kills': other_kills,
        'other_deaths': other_deaths,
        'pvp_kill_count': pvp_kill_count,
        'pvp_death_count': pvp_death_count,
        'other_kill_count': other_kill_count,
        'other_death_count': other_death_count,
        'pvp_logs': stats.pvp_logs
    }
