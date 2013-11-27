from standardweb.models import *

import operator


def build_kill_leaderboard(server, type):
    kill_type = KillType.objects.get(type=type)
    kills = KillCount.objects.filter(server=server, kill_type=kill_type) \
                .select_related('killer')
    if kills:
        return sorted([(x.count, x.killer) for x in kills], key=lambda x: (-x[0], x[1].displayname.lower()))

    return None


def build_block_discovery_leaderboard(server, type):
    material_type = MaterialType.objects.get(type=type)
    discoveries = OreDiscoveryCount.objects.filter(server=server, material_type=material_type) \
                        .select_related('player')

    if discoveries:
        return sorted([(x.count, x.player) for x in discoveries], key=lambda x: (-x[0], x[1].displayname.lower()))

    return None
