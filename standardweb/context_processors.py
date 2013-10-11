from django.conf import settings

from standardweb.lib import helpers as h


def realtime(request):
    return {'rts_address': settings.RTS_ADDRESS}


def git_revision(request):
    return {'git_revision': h.git_revision}