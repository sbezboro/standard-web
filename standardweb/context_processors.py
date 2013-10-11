from django.conf import settings

def realtime(request):
    return {'rts_address': settings.RTS_ADDRESS}