import re
import subprocess

from standardweb.lib import cache

from ansi2html import Ansi2HTMLConverter

from django.contrib import messages

ansi_converter = Ansi2HTMLConverter()
ansi_pat = re.compile(r'\x1b[^m]*m')


try:
    git_revision = subprocess.check_output('git log -n 1 --pretty=format:"%H"', shell=True)
except Exception, e:
    print 'Could not get git revision, ignoring: %s', e
    git_revision = ''


def iso_date(date):
    return date.strftime("%Y-%m-%d %H:%M:%SZ")

    
def elapsed_time_string(total_minutes):
    hours = int(total_minutes / 60)
    
    if not hours:
        return '%d %s' % (total_minutes, 'minute' if total_minutes == 1 else 'minutes')
    
    minutes = total_minutes % (hours * 60)
        
    return '%d %s %d %s' % (hours, 'hour' if hours == 1 else 'hours',
                            minutes, 'minute' if minutes == 1 else 'minutes')


def ansi_to_html(ansi):
    html = ansi_converter.convert(ansi, full=False)
    return '<span class="ansi-container">' + html + ('</span>' * html.count('<span')) + '</span>'


def strip_ansi(text):
    return ansi_pat.sub('', text) if text else None


@cache.CachedResult('mojang_status')
def mojang_status():
    from standardweb.models import MojangStatus
    return MojangStatus.objects.latest('timestamp')


def _flash(request, level, message, title=None):
    content = ''
    if title:
        content = '<h4>%s</h4>' % title
    content += message

    messages.add_message(request, level, content)


def flash_warning(request, message, title=None):
    _flash(request, messages.constants.WARNING, message, title=title)


def flash_info(request, message, title=None):
    _flash(request, messages.constants.INFO, message, title=title)
