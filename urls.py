from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.contrib.auth.forms import AuthenticationForm
from django.views.generic import RedirectView
from djangobb_forum import settings as forum_settings

from standardweb import views
from standardweb import api


admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', views.index),
    url(r'^player_list', views.player_list),
    url(r'^^((?P<server_id>\d{1})/)?player_graph', views.player_graph),
    url(r'^faces/(?P<size>\d{2})/(?P<username>\w{0,50})\.png$', views.get_face),
    url(r'^((?P<server_id>\d{1})/)?player/(?P<username>\w{0,50})$', views.player),
    url(r'^search/$', views.search),
    url(r'^((?P<server_id>\d{1})/)?ranking$', views.ranking),
    url(r'^rankings$', RedirectView.as_view(url='/ranking')),
    url(r'^((?P<server_id>\d{1})/)?chat$', views.chat),
    url(r'^pvp_leaderboard$', views.pvp_leaderboard),
    
    url(r'^login$', views.login, {'template_name':'login.html', 'authentication_form': AuthenticationForm}, name='login'),
    url(r'^logout$', views.logout, name='logout'),
    
    url(r'^classic/player/(?P<username>\w{0,50})$', views.player, kwargs={'server_id': 1}),
    url(r'^classic/ranking$', views.ranking, kwargs={'server_id': 1}),
    
    url(r'^((?P<server_id>\d{1})/)?analytics$', views.analytics),
    url(r'^((?P<server_id>\d{1})/)?server-admin$', views.admin),
    
    (r'^500$', views.server_error),
    (r'^403$', views.forbidden),
)

for api_func in api.api_funcs:
    urlpatterns += patterns('standardweb.api',
        url(r'^api/v(?P<version>\d{1})/%s' % api_func.__name__, api_func.__name__),
    )
    
urlpatterns += patterns('', 
    (r'^forum/', include('djangobb_forum.urls', namespace='djangobb')),
    
    (r'^admin/', include(admin.site.urls)),
)

if (forum_settings.PM_SUPPORT):
    urlpatterns += patterns('', (r'^forum/pm/', include('messages.urls')),
)
    
handler403 = 'standardweb.views.forbidden'
handler500 = 'standardweb.views.server_error'