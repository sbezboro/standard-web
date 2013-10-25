from django.conf import settings
from django.contrib.sessions import middleware
from django.http import HttpResponseRedirect

from importlib import import_module

from standardweb.models import *
from standardweb.lib.cache import CachedResult


SESSION_PATHS_BLACKLIST = ['/api/', '/faces/']

class IPTrackingMiddleware:
    @CachedResult('ip-lookup', time=300)
    def _lookup_ip(self, ip, user_id):
        try:
            IPTracking.objects.get(ip=ip, user_id=user_id)
        except:
            ip_tracking = IPTracking(ip=ip, user_id=user_id)
            ip_tracking.save()

        return True

    def process_request(self, request):
        if request.path.endswith('.png'):
            return
        
        ip = request.META.get('REMOTE_ADDR')
        
        if request.user.is_authenticated() and ip:
            self._lookup_ip(ip, request.user.id)
        
        return None


class SSLRedirectMiddleware:
    ssl_kwarg = 'SSL'

    def process_view(self, request, view_func, view_args, view_kwargs):
        if self.ssl_kwarg in view_kwargs:
            secure = view_kwargs[self.ssl_kwarg]
            del view_kwargs[self.ssl_kwarg]
        else:
            secure = False

        if not settings.USE_SSL or request.method == 'POST':
            return

        secure = secure or request.user.is_authenticated()

        if secure and not self._is_secure(request):
            return self._redirect(request, secure)

    def _is_secure(self, request):
        return request.is_secure() or 'HTTP_X_FORWARDED_PROTOCOL' in request.META

    def _redirect(self, request, secure):
        protocol = 'https' if secure else 'http'

        new_url = '%s://%s%s' % (protocol, settings.HOST, request.get_full_path())

        return HttpResponseRedirect(new_url)


class SessionMiddleware(middleware.SessionMiddleware):
    """
    Temp session middleware to transfer cookies from 'sessionid' to 'djangosessionid',
    then eventually back to 'sessionid'
    """
    def process_request(self, request):
        engine = import_module(settings.SESSION_ENGINE)
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME, None)

        #if session_key is None:
        #    session_key = request.COOKIES.get(settings.OLD_SESSION_COOKIE_NAME, None)

        if any(request.path_info.startswith(x) for x in SESSION_PATHS_BLACKLIST):
            request.session = {}
        else:
            request.session = engine.SessionStore(session_key)