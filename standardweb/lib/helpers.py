import re
import time
from datetime import datetime, timedelta

ansi_pat = re.compile(r'\x1b[^m]*m')

def iso_date(date):
    return date.strftime("%Y-%m-%d %H:%M:%SZ")
    
def elapsed_time_string(minutes):
    hours = int(minutes / 60)
    
    string = ''
    
    if hours > 0:
        if hours == 1:
            string = '1 hour '
        else:
            string = str(hours) + ' hours '
    
    if hours > 0:
        minutes = minutes % (hours * 60)
    
    if minutes == 1:
        string = string + '1 minute'
    else:
        string = string + str(minutes) + ' minutes'
    
    return string

def strip_ansi(text):
    return ansi_pat.sub('', text) if text else None
