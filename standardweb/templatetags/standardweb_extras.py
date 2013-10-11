import os

from django import template

register = template.Library()


PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))

STATIC_PATH = '/static'

_mtime_cache = {}
def _get_mtime(path):
    if path not in _mtime_cache:
        full_path = os.path.join('%s%s/%s' % (PROJECT_PATH, STATIC_PATH, path))

        try:
            stat = os.stat(full_path)
        except OSError:
            return None
        else:
            _mtime_cache[path] = int(stat.st_mtime)

    return _mtime_cache[path]


@register.simple_tag
def static_url(path):
    ts_string = ''
    mtime = _get_mtime(path)

    if mtime:
        ts_string = '?ts=%d' % mtime

    return '%s/%s%s' % (STATIC_PATH, path, ts_string)
