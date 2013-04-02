from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.contrib.auth.forms import AuthenticationForm
from django.views.generic import RedirectView
from djangobb_forum import settings as forum_settings

from standardsurvival import views
from standardsurvival import api


admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', views.index),
    url(r'^player_list', views.player_list),
    url(r'^player_graph', views.player_graph),
    url(r'^faces/(?P<size>\d{2})/(?P<username>\w{0,50}).png', views.get_face),
    url(r'^faces/(?P<username>\w{0,50}).png', views.get_face),
    url(r'^player/(?P<username>\w{0,50})', views.player),
    url(r'^search/$', views.search),
    url(r'^ranking$', views.ranking),
    url(r'^rankings$', RedirectView.as_view(url='/ranking')),
    url(r'^pvp_leaderboard$', views.pvp_leaderboard),
    
    url(r'^classic/player/(?P<username>\w{0,50})', views.player, kwargs={'classic': True}),
    url(r'^classic/ranking$', views.ranking, kwargs={'classic': True}),
    
    url(r'^analytics$', views.analytics),
    url(r'^server-admin$', views.admin),
    
    (r'^500/$', views.server_error),
)
    
urlpatterns += patterns('',
    url(r'^api/log_death', api.log_death),
    url(r'^api/log_kill', api.log_kill),
    url(r'^api/link', api.link),
    url(r'^api/rank_query', api.rank_query),
    url(r'^api/auth_session_key', api.auth_session_key),
)
    
urlpatterns += patterns('', 
    (r'^forum/', include('djangobb_forum.urls', namespace='djangobb')),
    
    url(r'^forum/account/signin/$', 'django.contrib.auth.views.login',{'template_name':'djangobb_forum/signin.html', 'authentication_form': AuthenticationForm}, name='signin'),
    url(r'^forum/account/signout/$', 'djangobb_forum.views.signout', name='signout'),
    url(r'^forum/account/register/$', 'djangobb_forum.views.register', name='register'),
    url(r'^forum/account/password_reset/$', 'djangobb_forum.views.register', name='password_reset'),
    
    (r'^admin/', include(admin.site.urls)),
)

if (forum_settings.PM_SUPPORT):
    urlpatterns += patterns('', (r'^forum/pm/', include('django_messages.urls')),
    )
    
handler500 = 'standardsurvival.views.server_error'