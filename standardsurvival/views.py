from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.http import last_modified
from minecraft_query import MinecraftQuery
from minecraft_api import MinecraftJsonApi


from standardsurvival.models import *
import date_util

from PIL import Image

from datetime import datetime, timedelta
import StringIO
import calendar
import json
import os.path
import shutil
import time
import urllib


def index(request):
    status = MojangStatus.objects.latest('timestamp')
    
    return render_to_response('index.html', {
        'status': status
    }, context_instance=RequestContext(request))


def analytics(request):
    from django.db.models import Min
    earliest_date = MinecraftPlayer.objects.all().aggregate(Min('first_seen'))['first_seen__min']
    
    cohorts = []
    weeks = (datetime.utcnow() - earliest_date).days / 7
    
    for i in xrange(weeks + 1):
        cohorts.append({'players': 0, 'active': []})
        
    players = MinecraftPlayer.objects.all()
    
    for player in players:
        difference = datetime.utcnow() - player.first_seen
        cohort = difference.days / 7
        cohorts[cohort]['players'] += 1
        
        if cohort > 0:
            if not cohorts[cohort].get('returns'):
                cohorts[cohort]['returns'] = [0] * cohort
            
            for i in xrange(0, cohort):
                if datetime.utcnow() - timedelta(days = 7 * (i + 1)) < player.last_seen:
                    cohorts[cohort]['returns'][cohort - i - 1] += 1
                
                    if i == 0:
                        cohorts[cohort]['active'].append(player.username)
    
    return render_to_response('analytics.html', {
        'cohorts': cohorts
        }, context_instance=RequestContext(request))


def player_graph(request):
    weeks_ago = int(request.GET.get('weeks_ago', 0))
    if weeks_ago:
        graph_info = []
        new_players = 0
        statuses = ServerStatus.objects.filter(timestamp__gt=datetime.utcnow() - timedelta(days = weeks_ago * 7), timestamp__lt=datetime.utcnow() - timedelta(days = (weeks_ago - 1) * 7))
        new_players = MinecraftPlayer.objects.filter(first_seen__gt=datetime.utcnow() - timedelta(days = weeks_ago * 7), first_seen__lt=datetime.utcnow() - timedelta(days = (weeks_ago - 1) * 7));
        
        slices = []
        for i in xrange(int(timedelta(days = 7).total_seconds() / 10)):
            slices.append(0)
            
        for player in new_players:
            start = datetime.utcnow() - timedelta(days = weeks_ago * 7)
            slice = int((player.first_seen - start).total_seconds() / 600)
            slices[slice] += 1
        
        index = 0
        for status in statuses:
            if status.id % 10 == 0:
                graph_info.append({
                    'time': int(calendar.timegm(status.timestamp.timetuple()) * 1000),
                    'player_count': status.player_count,
                    'new_players': slices[index]
                })
                
                index += 1
            
        return HttpResponse(json.dumps(graph_info), mimetype="application/json")
    
    graph_info = cache.get('minecraft-graph-info')
    if not graph_info:
        graph_info = []
        #index = 0
        #average = 0
        #counts = []
        statuses = ServerStatus.objects.filter(timestamp__gt=datetime.utcnow() - timedelta(days = 7))
        
        average = statuses[0].player_count
        for status in statuses:
            #counts.append(status.player_count)
            #average = average - (counts[max(index - 5, 0)] / 5) + counts[index] / 5
            
            if status.id % 30 == 0:
                graph_info.append({
                    'time': int(calendar.timegm(status.timestamp.timetuple()) * 1000),
                    'player_count': status.player_count #average
                })
            
            #index = index + 1
        
        cache.set('minecraft-graph-info', graph_info, 60)
        
    return HttpResponse(json.dumps(graph_info), mimetype="application/json")


def player_list(request):
    stats = cache.get('minecraft-stats')
    
    if not stats:
        stats = {}

        try:
            api = MinecraftJsonApi(
                host = settings.MC_API_HOST, 
                port = settings.MC_API_PORT, 
                username = settings.MC_API_USERNAME, 
                password = settings.MC_API_PASSWORD, 
                salt = settings.MC_API_SALT
            )
            
            server_status = api.call('server_status')
            
            server_status['players'].sort(key=lambda x: (x.get('nickname') or x.get('username')).lower())
            
            players = []
            top10 = MinecraftPlayer.objects.order_by('-time_spent')[:10]
            for player_info in server_status['players']:
                try:
                    player = MinecraftPlayer.objects.get(username=player_info.get('username'))
                except:
                    player = MinecraftPlayer(username=player_info.get('username'))
                    player.save
                
                rank = None
                if player in top10:
                    for index, top10player in enumerate(top10):
                        if player == top10player:
                            rank = index + 1
                
                players.append({'username': player.username, 'nickname': player.nickname, 'rank': rank})
            
            stats['players'] = players
            stats['num_players'] = server_status['numplayers']
            stats['max_players'] = server_status['maxplayers']
        except:
            stats = None
        
        cache.set('minecraft-stats', stats, 5)
        
    return render_to_response('includes/playerlist.html', {
        'stats': stats},
        context_instance=RequestContext(request))


def pvp_leaderboard(request):
    from django.db.models import Count
    
    killers = MinecraftPlayer.objects.annotate(num_kills=Count('d_killer', distinct=True), num_deaths=Count('d_victim', distinct=True)).filter(d_victim__killer__isnull=False).order_by('-num_kills')[:40]
    
    return render_to_response('pvp_leaderboard.html', {
        'killers': killers
    },
    context_instance=RequestContext(request))

def search(request):
    query = request.GET.get('q')
    
    if not query:
        raise Http404
    
    players = MinecraftPlayer.objects.filter(Q(username__icontains=query) | Q(nickname__icontains=query))[:20]
    
    if len(players) == 1:
        return redirect('/player/%s' % players[0].username)
    
    player_info = []
    for player in players:
        player_info.append({'username': player.username, 'nickname': player.nickname})
    
    player_info.sort(key=lambda k: (k['nickname'] or k['username']).lower())
        
    return render_to_response('search.html', {
        'query': query,
        'player_info': player_info,
        }, context_instance=RequestContext(request))


def player(request, username):
    if not username:
        raise Http404
    
    try:
        player = MinecraftPlayer.objects.get(username=username)
    except Exception, e:
        return render_to_response('player.html', {
            'exists': False,
            'username': username,
            }, context_instance=RequestContext(request))
    
    death_info = {}
    pvp_deaths = {}
        
    deaths = DeathEvent.objects.filter(victim=player).values('killer__username', 'killer__nickname', 'death_type__displayname')
    death_count = len(deaths)
    
    pvp_kill_count = len(DeathEvent.objects.filter(killer=player, victim__isnull=False))
    pvp_death_count = len(DeathEvent.objects.filter(victim=player, killer__isnull=False))
    other_death_count = len(DeathEvent.objects.filter(victim=player, killer__isnull=True))
    
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
    
    kills = KillEvent.objects.filter(killer=player).values('kill_type__displayname')
    kill_count = len(kills)
    
    other_kill_count = len(KillEvent.objects.filter(killer=player, victim__isnull=True))
    
    for kill in kills:
        kill_type = kill.get('kill_type__displayname')
        
        kill_info[kill_type] = kill_info.get(kill_type, 0) + 1
    
    kill_info = sorted([{'type': key, 'count': kill_info[key]} for key in kill_info], key=lambda k: (-k['count'], k['type']))
    
    kills = DeathEvent.objects.filter(killer=player).values('victim__username', 'victim__nickname')
    kill_count = kill_count + len(kills)
    for kill in kills:
        username = kill.get('victim__username')
        pvp_kills[username] = pvp_kills.get(username, 0) + 1
        
        nickname = kill.get('victim__nickname')
        if nickname:
            nicknames[username] = nickname
        
    
    pvp_kills = sorted([{'username': key, 'nickname': nicknames.get(key), 'count': pvp_kills[key]} for key in pvp_kills], key=lambda k: (-k['count'], (k['nickname'] or k['username']).lower()))
    
    online_now = datetime.utcnow() - timedelta(minutes = 1) < player.last_seen
    
    players = MinecraftPlayer.objects.filter(time_spent__gte=player.time_spent).exclude(id=player.id)
    rank = len(players) + 1
    
    return render_to_response('player.html', {
        'exists': True,
        'username': player.username,
        'nickname': player.nickname,
        'banned': player.banned,
        'online_now': online_now,
        'first_seen': date_util.iso_date(player.first_seen),
        'last_seen': date_util.iso_date(player.last_seen),
        'time_spent': date_util.elapsed_time_string(player.time_spent),
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
        'rank': rank,
        }, context_instance=RequestContext(request))


def ranking(request):
    player_info = []
    players = MinecraftPlayer.objects.order_by('-time_spent')[:40]
    
    for player in players:
        player_info.append({
            'username': player.username,
            'nickname': player.nickname,
            'time_spent': date_util.elapsed_time_string(player.time_spent),
            'online': datetime.utcnow() - timedelta(minutes = 1) < player.last_seen,
        })
    
    return render_to_response('ranking.html', {
        'player_info': player_info,
        }, context_instance=RequestContext(request))


def last_modified_func(request, size=None, username=None):
    PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))
    path = '%s/faces/%s/%s.png' % (PROJECT_PATH, size, username)
    
    try:
        return datetime.fromtimestamp(os.path.getmtime(path))
    except:
        return None 


def _extract_face(image, size):
    try:
        pix = image.load()
        for x in xrange(8, 16):
            for y in xrange(8, 16):
                # apply head accessory for non-transparent pixels
                if pix[x + 32, y][3] > 1:
                    pix[x, y] = pix[x + 322, y]
    except:
        pass
    
    return image.crop((8, 8, 16, 16)).resize((size, size))


@last_modified(last_modified_func)
def get_face(request, size=16, username=None):
    size = int(size)
    
    if size != 16 and size != 64:
        raise Http404

    PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))
    
    image = None
    
    try:
        url = 'http://s3.amazonaws.com/MinecraftSkins/%s.png' % username
        image_response = urllib.urlopen(url)
        
        if image_response.getcode() == 200:
            last_modified = image_response.info().getheader('Last-Modified')
            last_modified_date = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
            
            path = '%s/faces/%s/%s.png' % (PROJECT_PATH, size, username)
            
            try:
                file_date = datetime.fromtimestamp(os.path.getmtime(path))
            except:
                file_date = None
            
            if not file_date or last_modified_date > file_date:
                image = _extract_face(Image.open(StringIO.StringIO(image_response.read())), size)
                image.save(path)
            else:
                image = Image.open(path)
    except:
        pass
    
    image = image or _extract_face(Image.open(PROJECT_PATH + '/static/images/char.png'), size)
    
    tmp = StringIO.StringIO()
    image.save(tmp, 'PNG')
    tmp.seek(0)
    data = tmp.getvalue()
    tmp.close()

    return HttpResponse(data, mimetype="image/png")


def server_error(request, template_name='500.html'):
    return render_to_response(template_name, context_instance=RequestContext(request))
