from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import last_modified
from minecraft_query import MinecraftQuery

from standardsurvival.models import *
import date_util

from djangobb_forum.models import Profile as ForumProfile

from PIL import Image

from datetime import datetime, timedelta
import StringIO
import calendar
import urllib
import json

@csrf_exempt
def log_death(request):
    type = request.REQUEST.get('type')
    victim_name = request.REQUEST.get('victim')
    killer_name = request.REQUEST.get('killer')
    
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
        
        death_event = DeathEvent(death_type=death_type, victim=victim, killer=killer)
    else:
        death_event = DeathEvent(death_type=death_type, victim=victim)
    
    death_event.save()
    
    return HttpResponse()

@csrf_exempt
def log_kill(request):
    type = request.REQUEST.get('type')
    killer_name = request.REQUEST.get('killer')
    
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
    
    kill_event = KillEvent(kill_type=kill_type, killer=killer)
    
    kill_event.save()
    
    return HttpResponse()

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
        
        players = MinecraftPlayer.objects.filter(time_spent__gte=player.time_spent).exclude(id=player.id)
        rank = len(players) + 1
        
        time = date_util.elapsed_time_string(player.time_spent)
        
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