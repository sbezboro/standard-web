from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt

from functools import wraps

from standardsurvival.models import *
import date_util

from djangobb_forum.models import Profile as ForumProfile

import json


def api(function):
    @wraps(function)
    def decorator(request, *args, **kwargs):
        server_id = request.REQUEST.get('server-id')
        secret_key = request.REQUEST.get('secret-key')
        
        cache_key = 'api-%s-%s' % (server_id, secret_key)
        request.server = cache.get(cache_key)
        if not request.server:
            try:
                request.server = Server.objects.get(id=server_id, secret_key=secret_key)
                cache.set(cache_key, request.server, 3600)
            except:
                return HttpResponseForbidden()
        
        return function(request, *args, **kwargs)
    
    return decorator


@api
@csrf_exempt
def log_death(request):
    type = request.POST.get('type')
    victim_name = request.POST.get('victim')
    killer_name = request.POST.get('killer')
    
    try:
        victim = MinecraftPlayer.objects.get(username=victim_name)
    except:
        victim = MinecraftPlayer(username=victim_name)
        victim.save()
    
    if victim_name == killer_name:
        type = 'suicide'
        
    try:
        death_type = DeathType.objects.get(type=type)
    except:
        death_type = DeathType(type=type)
        death_type.save()
    
    if type == 'player':
        try:
            killer = MinecraftPlayer.objects.get(username=killer_name)
        except:
            killer = MinecraftPlayer(username=killer_name)
            killer.save()
        
        death_event = DeathEvent(server=request.server, death_type=death_type, victim=victim, killer=killer)
    else:
        death_event = DeathEvent(server=request.server, death_type=death_type, victim=victim)
    
    death_event.save()
    
    return HttpResponse()


@api
@csrf_exempt
def log_kill(request):
    type = request.POST.get('type')
    killer_name = request.POST.get('killer')
    
    try:
        killer = MinecraftPlayer.objects.get(username=killer_name)
    except:
        killer = MinecraftPlayer(username=killer_name)
        killer.save()
        
    try:
        kill_type = KillType.objects.get(type=type)
    except:
        kill_type = KillType(type=type)
        kill_type.save()
    
    kill_event = KillEvent(server=request.server, kill_type=kill_type, killer=killer)
    
    kill_event.save()
    
    return HttpResponse()

@api
@csrf_exempt
def link(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    
    try:
        player = MinecraftPlayer.objects.get(username=username)
        
        try:
            user = User.objects.get(username=username)
            user.set_password(password)
            user.save()
            
            return HttpResponse('Your forum password has been changed!')
        except:
            user = User.objects.create_user(username, password=password)
            profile = ForumProfile(user=user, player=player, language='en', time_zone=-5)
            profile.save()
            
    except Exception as e:
        return HttpResponseNotFound()
    
    return HttpResponse('Your username has been linked to a forum account!')


@api
@csrf_exempt
def rank_query(request):
    username = request.GET.get('username')
    exact = int(request.GET.get('exact', 0))
    
    try:
        if exact:
            player = MinecraftPlayer.objects.get(username=username)
        else:
            players = MinecraftPlayer.objects.filter(Q(username__icontains=username) | Q(nickname__icontains=username))
            player_info = sorted([x for x in players], key=lambda k: len(k.nickname or k.username))
            player = player_info[0]
        
        stats = PlayerStats.objects.get(server=request.server, player=player)
        rank = stats.rank()
        
        time = date_util.elapsed_time_string(stats.time_spent)
        
        response_data = {
            'result': 1,
            'rank': rank,
            'time': time,
        }
        
        if not exact:
            response_data['username'] = player.username
            
    except Exception as e:
        response_data = {
            'result': 0
        }
    
    return HttpResponse(json.dumps(response_data), mimetype="application/json")