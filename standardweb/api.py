from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound

from functools import wraps

from standardweb.models import *
from standardweb.lib import helpers as h

from djangobb_forum.models import Profile as ForumProfile

import json

import rollbar


api_funcs = []

# Base API function decorator that builds a list of view functions for use in urls.py. 
def api_func(function):
    function.csrf_exempt = True
    api_funcs.append(function)
    
    @wraps(function)
    def decorator(request, *args, **kwargs):
        version = int(kwargs['version'])
        if version < 1 or version > 1:
            return HttpResponseNotFound()
        
        del kwargs['version']
        return function(request, *args, **kwargs)
    
    return decorator


# API function decorator for any api operation exposed to a Minecraft server.
# This access must be authorized by server-id/secret-key pair combination.
def server_api(function):
    @wraps(function)
    def decorator(request, *args, **kwargs):
        if request.META.has_key('HTTP_AUTHORIZATION'):
            auth = request.META['HTTP_AUTHORIZATION'].split(' ')[1]
            server_id, secret_key = auth.strip().decode('base64').split(':')
        else:
            # provided for backward compatibility, to be removed soon
            server_id = request.REQUEST.get('server-id')
            secret_key = request.REQUEST.get('secret-key')
        
        cache_key = 'api-%s-%s' % (server_id, secret_key)
        server = cache.get(cache_key)
        if not server:
            try:
                server = Server.objects.get(id=server_id, secret_key=secret_key)
                cache.set(cache_key, server, 3600)
            except:
                pass

        if not server:
            rollbar.report_message('API access denied!', level='error', request=request)
            return HttpResponseForbidden()
        
        return function(request, *args, **kwargs)
    
    return decorator


@api_func
@server_api
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


@api_func
@server_api
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

@api_func
@server_api
def link(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    
    try:
        player = MinecraftPlayer.objects.get(username=username)
        
        try:
            user = User.objects.get(username=username)
            user.set_password(password)
            user.save()
            
            return HttpResponse('Your website password has been changed!')
        except:
            user = User.objects.create_user(username, password=password)
            profile = ForumProfile(user=user, player=player, language='en', time_zone=-5)
            profile.save()
            
    except Exception as e:
        return HttpResponseNotFound()
    
    rollbar.report_message('Website account created', level='info', request=request)
    return HttpResponse('Your username has been linked to a website account!')


@api_func
@server_api
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
        rank = stats.get_rank()
        
        time = h.elapsed_time_string(stats.time_spent)
        
        try:
            veteran_status = VeteranStatus.objects.get(player=player)
            veteran_rank = veteran_status.rank
        except:
            veteran_rank = None
        
        response_data = {
            'result': 1,
            'rank': rank,
            'time': time,
            'minutes': stats.time_spent
        }
        
        if veteran_rank:
            response_data['veteran_rank'] = veteran_rank
        
        if not exact:
            response_data['username'] = player.username
            
    except Exception as e:
        response_data = {
            'result': 0
        }
    
    return HttpResponse(json.dumps(response_data), content_type="application/json")


@api_func
def auth_session_key(request):
    """
    Authenticates a Django session key and returns its corresponding user_id and username.
    Also authorizes admin access if 'is-admin' is set in the request.
    """
    
    from django.contrib.sessions.models import Session
    from django.contrib.auth.models import User
    
    try:
        session_key = request.POST.get('session-key')
        elevated = bool(request.POST.get('elevated'))
        
        session = Session.objects.get(session_key=session_key)
        user_id = session.get_decoded().get('_auth_user_id')
        user = User.objects.get(pk=user_id)
        request.user = user
    except:
        rollbar.report_message('Bad auth request!', level='error', request=request)
        return HttpResponseBadRequest()
    
    if elevated and (not request.user or not request.user.is_superuser):
        rollbar.report_message('Session key not authorized for admin access!',
                               level='critical', request=request)
        return HttpResponseForbidden()
    
    rollbar.report_message('Session key authenticated', level='info', request=request)
    return HttpResponse(json.dumps({
        'user_id': user.id,
        'username': user.username
    }), content_type="application/json")


@api_func
def servers(request):
    servers = [{
        'id': server.id,
        'address': server.address
    } for server in Server.objects.all()]
    
    return HttpResponse(json.dumps(servers), content_type="application/json")

