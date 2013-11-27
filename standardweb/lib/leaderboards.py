from standardweb.models import *


def build_kill_leaderboard(server, type, title):
    kill_type = KillType.objects.get(type=type)
    kills = KillCount.objects.filter(server=server, kill_type=kill_type) \
                .select_related('killer')
    if kills:
        kills = sorted(kills, key=lambda x: (-x.count, x.killer.displayname.lower()))
        return (title, kills)

    return None