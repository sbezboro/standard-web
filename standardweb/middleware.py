from django.conf import settings
from django.http import HttpResponseRedirect

from standardweb.models import *

class IPTrackingMiddleware:
    def process_request(self, request):
        if request.path.endswith('.png'):
            return
        
        ip = request.META.get('REMOTE_ADDR')
        
        if request.user.is_authenticated() and ip:
            try:
                IPTracking.objects.get(ip=ip, user=request.user)
            except:
                existing_user_ip = IPTracking(ip=ip, user=request.user)
                existing_user_ip.save()
        
        return None

class SSLRedirectMiddleware:
    ssl_kwarg = 'SSL'

    def process_view(self, request, view_func, view_args, view_kwargs):
        if self.ssl_kwarg in view_kwargs:
            secure = view_kwargs[self.ssl_kwarg]
            del view_kwargs[self.ssl_kwarg]
        else:
            secure = False

        if settings.DEBUG or request.method == 'POST':
            return

        secure = secure or request.user.is_authenticated()

        if secure and not request.is_secure():
            return self._redirect(request, secure)

    def _redirect(self, request, secure):
        protocol = 'https' if secure else 'http'

        new_url = '%s://%s%s' % (protocol, settings.HOST, request.get_full_path())

        return HttpResponseRedirect(new_url)
