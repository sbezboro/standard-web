from standardweb.models import *

class IPTrackingMiddleware:
    def process_request(self, request):
        ip = request.META.get('REMOTE_ADDR')
        
        if request.user.is_authenticated() and ip:
            try:
                existing_user_ip = IPTracking.objects.get(ip=ip, user=request.user)
            except:
                existing_user_ip = IPTracking(ip=ip, user=request.user)
                existing_user_ip.save()
        
        return None
