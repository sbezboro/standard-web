import hashlib
import json

from django.conf import settings

from standardweb.lib import helpers as h


def realtime(request):
    rts_auth_data = {}

    if request.user.is_authenticated():
        user_id = request.user.id
        username = request.user.username
        is_superuser = request.user.is_superuser

        content = '-'.join([str(user_id), username, str(int(is_superuser))])

        token = hashlib.sha256(content + settings.RTS_SECRET).hexdigest()

        rts_auth_data = {
            'user_id': user_id,
            'username': username,
            'is_superuser': int(is_superuser),
            'token': token
        }

    result = {
        'rts_address': settings.RTS_ADDRESS,
        'rts_auth_data': json.dumps(rts_auth_data)
    }

    return result


def git_revision(request):
    return {'git_revision': h.git_revision}
