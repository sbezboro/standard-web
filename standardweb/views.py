from django.conf import settings
from django.contrib.auth.views import login as django_login
from django.contrib.auth import logout as django_logout
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

from standardweb.lib import api
from standardweb.lib import helpers as h
from standardweb.models import *

from PIL import Image

from datetime import datetime, timedelta
import StringIO
import calendar
import json
import os.path
import shutil
import time
import urllib

import rollbar


def index(request):
    status = MojangStatus.objects.latest('timestamp')
    
    return render_to_response('index.html', {
        'status': status
    }, context_instance=RequestContext(request))


def login(request, **kwargs):
    if request.user.is_authenticated():
        return redirect('/')
    else:
        return django_login(request, **kwargs)


def logout(request):
    django_logout(request)
    return redirect('/')


def analytics(request):
    server = Server.objects.get(id=2)
    
    earliest_date = ServerStatus.objects.filter(server=server).order_by('timestamp')[1].timestamp
    
    cohorts = []
    weeks = (datetime.utcnow() - earliest_date).days / 7
    
    for i in xrange(weeks + 1):
        cohorts.append({'players': 0, 'active': [], 'inactive': 0, 'new': 0})
        
    players = MinecraftPlayer.objects.filter(stats__server_id=server.id).values('username', 'stats__first_seen', 'stats__last_seen')
    
    for player in players:
        username = player['username']
        first_seen = player['stats__first_seen']
        last_seen = player['stats__last_seen']
        
        difference = first_seen - earliest_date
        cohort = difference.days / 7
        cohorts[cohort]['new'] += 1
        
        difference = last_seen - earliest_date
        last_week = difference.days / 7
        if last_week == weeks: #still here this week
            cohorts[last_week]['active'].append(username)
        else:
            cohorts[last_week]['inactive'] += 1
        
        '''
        if cohort < weeks:
            cohorts[cohort].setdefault('returns', [0] * (weeks - cohort))
            
            for i in xrange(0, cohort):
                if datetime.utcnow() - timedelta(days = 7 * (i + 1)) < last_seen:
                    cohorts[cohort]['returns'][cohort - i - 1] += 1
                
                    if i == 0:
                        cohorts[cohort]['active'].append(player.username)
        '''
    
    return render_to_response('analytics.html', {
        'cohorts': cohorts
        }, context_instance=RequestContext(request))


def admin(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    
    return render_to_response('admin.html', {
        'servers': Server.objects.all(),
        'rts_address': settings.RTS_ADDRESS
    }, context_instance=RequestContext(request))


def chat(request):
    return render_to_response('chat.html', {
        'servers': Server.objects.all(),
        'rts_address': settings.RTS_ADDRESS
    }, context_instance=RequestContext(request))


def _get_player_graph_data(server, show_new_players=False, granularity=15, start_date=None, end_date=None):
    end_date = end_date or datetime.utcnow()
    start_date = start_date or end_date - timedelta(days = 7)
    
    statuses = ServerStatus.objects.filter(server=server,
                                           timestamp__gt=start_date,
                                           timestamp__lt=end_date).order_by('timestamp')
    
    if show_new_players:
        new_players = PlayerStats.objects.filter(server=server,
                                                 first_seen__gt=start_date,
                                                 first_seen__lt=end_date)
        
        # see how many new players joined in each slice of time
        slices = [0 for i in xrange(int((end_date - start_date).total_seconds() / (60 * granularity)))]
            
        for stats in new_players:
            slice = int((stats.first_seen - start_date).total_seconds() / (60 * granularity))
            slices[slice] += 1
    
    index = 0
    points = []
    for status in statuses:
        if index % granularity == 0:
            data = {
                'time': int(calendar.timegm(status.timestamp.timetuple()) * 1000),
                'player_count': status.player_count
            }
            
            if show_new_players:
                data['new_players'] = slices[index / granularity]
            
            points.append(data)
            
        index += 1
    
    points.sort(key=lambda x: x['time'])
    
    return {
        'start_time': int(calendar.timegm(start_date.timetuple()) * 1000),
        'end_time': int(calendar.timegm(end_date.timetuple()) * 1000),
        'points': points
    }


def player_graph(request):
    server = Server.objects.get(id=2)
    
    week_index = int(request.GET.get('weekIndex', -1))
    if week_index >= 0:
        first_status = ServerStatus.objects.filter(server=server).order_by('timestamp')[1]
        
        timestamp = first_status.timestamp + week_index * timedelta(days=7)
        start_date = timestamp
        end_date = timestamp + timedelta(days=7)
        
        graph_data = _get_player_graph_data(server, show_new_players=True,
                                            start_date=start_date, end_date=end_date)
    else:
        graph_data = cache.get('minecraft-graph-data')
        if not graph_data:
            graph_data = _get_player_graph_data(server, show_new_players=False)
            
            cache.set('minecraft-graph-info', graph_data, 60)
    
    return HttpResponse(json.dumps(graph_data), mimetype="application/json")


def player_list(request):
    stats = cache.get('minecraft-stats')
    
    if not stats:
        stats = {}

        try:
            server = Server.objects.get(id=2)
            
            server_status = api.get_server_status(server)
            
            server_status['players'].sort(key=lambda x: (x.get('nickname') or x.get('username')).lower())
            
            players = []
            top10_player_ids = PlayerStats.objects.filter(server=server).order_by('-time_spent')[:10].values_list('player', flat=True)
            for player_info in server_status['players']:
                try:
                    player = MinecraftPlayer.objects.get(username=player_info.get('username'))
                except:
                    player = MinecraftPlayer(username=player_info.get('username'))
                    player.save()
                
                rank = None
                if player.id in top10_player_ids:
                    for index, top10player_id in enumerate(top10_player_ids):
                        if player.id == top10player_id:
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


def player(request, username, server_id=None):
    server_id = int(server_id or 2)
    if not username:
        raise Http404
    
    try:
        server = Server.objects.get(id=server_id)
    except:
        raise Http404
    
    try:
        player = MinecraftPlayer.objects.get(username=username)
        player_stats = PlayerStats.objects.get(server=server, player=player)
    except Exception, e:
        return render_to_response('player.html', {
            'exists': False,
            'servers': Server.objects.all(),
            'server_id': server_id,
            'username': username,
            }, context_instance=RequestContext(request))
    
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
    
    online_now = datetime.utcnow() - timedelta(minutes = 1) < player_stats.last_seen
    
    rank = player_stats.rank()
    
    return render_to_response('player.html', {
        'exists': True,
        'servers': Server.objects.all(),
        'server_id': server_id,
        'username': player.username,
        'nickname': player.nickname,
        'banned': player_stats.banned,
        'online_now': online_now,
        'first_seen': h.iso_date(player_stats.first_seen),
        'last_seen': h.iso_date(player_stats.last_seen),
        'time_spent': h.elapsed_time_string(player_stats.time_spent),
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


def ranking(request, server_id=None):
    server_id = int(server_id or 2)
    server = Server.objects.get(id=server_id)
    
    player_info = []
    player_stats = PlayerStats.objects.filter(server=server).order_by('-time_spent')[:40]
    
    for player_stat in player_stats:
        player_info.append({
            'username': player_stat.player.username,
            'nickname': player_stat.player.nickname,
            'time_spent': h.elapsed_time_string(player_stat.time_spent),
            'online': datetime.utcnow() - timedelta(minutes = 1) < player_stat.last_seen,
        })
    
    return render_to_response('ranking.html', {
        'servers': Server.objects.all(),
        'server_id': server_id,
        'player_info': player_info,
        }, context_instance=RequestContext(request))


def _last_modified_func(request, size=None, username=None):
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
                    pix[x, y] = pix[x + 32, y]
    except:
        pass
    
    return image.crop((8, 8, 16, 16)).resize((size, size))


@last_modified(_last_modified_func)
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


def forbidden(request, template_name='403.html'):
    from djangobb_forum.models import Ban
    
    data = {}
    
    if not request.user.is_active:
        try:
            ban = Ban.objects.get(user=request.user)
        except:
            ban = None
    
        if ban:
            data['reason'] = ban.reason
        
    return render_to_response(template_name, data, context_instance=RequestContext(request))


def server_error(request, template_name='500.html'):
    return render_to_response(template_name, context_instance=RequestContext(request))
