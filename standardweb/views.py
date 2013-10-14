from django.conf import settings
from django.contrib.auth.views import login as django_login
from django.contrib.auth import logout as django_logout
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.cache import cache_page
from django.views.decorators.http import last_modified

from standardweb.lib import api
from standardweb.lib import helpers as h
from standardweb.lib import player as libplayer
from standardweb.models import *

from PIL import Image

from datetime import datetime, timedelta
import StringIO
import calendar
import json
import os.path
import urllib


@cache_page(60)
def index(request):
    from djangobb_forum.models import Forum
    status = MojangStatus.objects.latest('timestamp')
    
    news_forum = Forum.objects.get(pk=settings.NEWS_FORUM_ID)
    news_topic = news_forum.topics.filter(deleted=False).order_by('-created')[0]
    news_post = news_topic.posts.filter(deleted=False).order_by('created')[0]
    comments = news_topic.posts.count() - 1
    
    return render_to_response('index.html', {
        'status': status,
        'news_topic': news_topic,
        'news_post': news_post,
        'comments': comments
    }, context_instance=RequestContext(request))


def login(request, **kwargs):
    if request.user.is_authenticated():
        return redirect('/')
    else:
        return django_login(request, **kwargs)


def logout(request):
    django_logout(request)
    return redirect('/')


def analytics(request, server_id=None):
    server_id = int(server_id or 2)
    
    server = Server.objects.get(id=server_id)
    
    earliest_date = ServerStatus.objects.filter(server=server).order_by('timestamp')[1].timestamp
    
    cohorts = []
    weeks = (datetime.utcnow() - earliest_date).days / 7
    
    for i in xrange(weeks + 1):
        cohorts.append({'entrants': [], 'total_time_spent': 0, 'more_than_hour': 0, 'active': 0, 'returns': [], 'inactive': 0})
        
    players = MinecraftPlayer.objects.filter(stats__server_id=server.id).values('username', 'stats__first_seen', 'stats__last_seen', 'stats__time_spent')
    
    for player in players:
        username = player['username']
        first_seen = player['stats__first_seen']
        last_seen = player['stats__last_seen']
        time_spent = player['stats__time_spent']
        
        difference = first_seen - earliest_date
        entry_week = difference.days / 7
        cohorts[entry_week]['entrants'].append(username)
        cohorts[entry_week]['total_time_spent'] += time_spent
        
        if time_spent > 60:
            cohorts[entry_week]['more_than_hour'] += 1
        
        difference = last_seen - earliest_date
        last_week = difference.days / 7
        
        if last_week == weeks: #still here now
            cohorts[entry_week]['active'] += 1
        elif last_week == entry_week: #only seen this entry_week
            cohorts[entry_week]['inactive'] += 1
    for cohort in cohorts:
        if len(cohort['entrants']):
            minutes = cohort['total_time_spent'] / len(cohort['entrants'])
            cohort['average_time_spent'] = h.elapsed_time_string(minutes)
    
    return render_to_response('analytics.html', {
        'servers': Server.objects.all(),
        'server_id': server_id,
        'cohorts': cohorts
        }, context_instance=RequestContext(request))


def admin(request, server_id=None):
    server_id = int(server_id or 2)
    
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    
    return render_to_response('admin.html', {
        'servers': Server.objects.all(),
        'server_id': server_id
    }, context_instance=RequestContext(request))


def chat(request, server_id=None):
    server_id = int(server_id or 2)
    
    player = None
    if request.user.is_authenticated():
        try:
            player = MinecraftPlayer.objects.get(username=request.user.username)
        except:
            pass
    
    return render_to_response('chat.html', {
        'servers': Server.objects.all(),
        'server_id': server_id,
        'player': player
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


def player_graph(request, server_id=None):
    server_id = int(server_id or 2)
    server = Server.objects.get(id=server_id)
    
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


def player_list(request, server_id=None):
    stats = cache.get('minecraft-stats')
    
    if not stats:
        stats = {}
        
        try:
            server_id = int(server_id or 2)
            server = Server.objects.get(id=server_id)
            
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
                
                players.append((player, rank))
            
            stats['players'] = players
            stats['num_players'] = server_status['numplayers']
            stats['max_players'] = server_status['maxplayers']
            stats['tps'] = server_status['tps']
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
        return redirect('/')
    
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
    if not username:
        raise Http404
    
    if not server_id:
        return HttpResponseRedirect('/2/player/%s' % username)
    
    server_id = int(server_id)
    server = get_object_or_404(Server, pk=server_id)
    
    template = 'player.html'
    retval = {
        'server': server,
        'servers': Server.objects.all(),
        'username': username
    }
    
    player = MinecraftPlayer.get_object_or_none(username=username)
    if not player:
        # the username doesn't belong to any player seen on any server
        response = render_to_response(template, retval,
            context_instance=RequestContext(request))
        response.status_code = 404
        
        return response
    
    # the player has played on at least one server
    retval.update({
        'player': player
    })
    
    # grab all data for this player on the selected server
    data = libplayer.get_server_data(server, player)
    
    if not data:
        # the player has not played on the selected server
        retval.update({
            'noindex': True
        })
        
        return render_to_response(template, retval,
            context_instance=RequestContext(request))
    
    retval.update(data)
    
    return render_to_response(template, retval,
        context_instance=RequestContext(request))


def ranking(request, server_id=None):
    if not server_id:
        return HttpResponseRedirect('/2/ranking')
    
    server_id = int(server_id or 2)
    server = Server.objects.get(id=server_id)
    
    player_info = []
    player_stats = PlayerStats.objects.filter(server=server) \
                       .order_by('-time_spent')[:40] \
                       .select_related()
    
    for player_stat in player_stats:
        player_info.append({
            'username': player_stat.player.username,
            'nickname': player_stat.player.nickname,
            'nickname_html': player_stat.player.nickname_html,
            'time_spent': h.elapsed_time_string(player_stat.time_spent),
            'online': datetime.utcnow() - timedelta(minutes = 1) < player_stat.last_seen,
        })
    
    return render_to_response('ranking.html', {
        'servers': Server.objects.all(),
        'server': server,
        'player_info': player_info,
        }, context_instance=RequestContext(request))


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


def _last_modified_func(request, size=None, username=None):
    PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))
    path = '%s/faces/%s/%s.png' % (PROJECT_PATH, size, username)
    
    try:
        return datetime.utcfromtimestamp(os.path.getmtime(path))
    except:
        return None 


@last_modified(_last_modified_func)
def get_face(request, size=16, username=None):
    size = int(size)
    
    if size != 16 and size != 64:
        raise Http404

    PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))
    path = '%s/faces/%s/%s.png' % (PROJECT_PATH, size, username)
    
    image = None
    
    try:
        url = 'http://s3.amazonaws.com/MinecraftSkins/%s.png' % username
        resp = urllib.urlopen(url)
    except:
        try:
            image = Image.open(path)
        except IOError:
            pass
    else:
        if resp.getcode() == 200:
            last_modified = resp.info().getheader('Last-Modified')
            last_modified_date = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')

            try:
                file_date = datetime.utcfromtimestamp(os.path.getmtime(path))
            except:
                file_date = None

            if not file_date or last_modified_date > file_date \
                or datetime.utcnow() - file_date > timedelta(days=1):
                image = _extract_face(Image.open(StringIO.StringIO(resp.read())), size)
                image.save(path)
            else:
                image = Image.open(path)
    
    if not image:
        image = _extract_face(Image.open(PROJECT_PATH + '/static/images/char.png'), size)
        image.save(path)
    
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
