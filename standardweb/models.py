from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from datetime import datetime

from standardweb.lib import helpers as h


class StandardModel(models.Model):
    class Meta:
        abstract = True
    
    @classmethod
    def get_object_or_none(cls, **kwargs):
        try:
            return cls.objects.get(**kwargs)
        except ObjectDoesNotExist, e:
            return None
        except:
            raise

    @classmethod
    def factory(cls, **kwargs):
        obj = cls.get_object_or_none(**kwargs)
        if not obj:
            obj = cls(**kwargs)
            obj.save()

        return obj


class MinecraftPlayer(StandardModel):
    username = models.CharField(max_length=30, unique=True)
    nickname = models.CharField(max_length=30, null=True)
    nickname_ansi = models.CharField(max_length=256, null=True)
    
    def __str__(self):
        return self.displayname
    
    @property
    def nickname_html(self):
        return h.ansi_to_html(self.nickname_ansi) if self.nickname_ansi else None
    
    @property
    def displayname(self):
        return self.nickname or self.username
    
    @property
    def displayname_html(self):
        return self.nickname_html if self.nickname else self.username
    
    @property
    def forum_profile(self):
        try:
            return self.djangobb_profile.get()
        except:
            return None
    
    @property
    def last_seen(self):
        return PlayerStats.objects.get(player=self, server=2).last_seen
    

class VeteranStatus(StandardModel):
    player = models.ForeignKey('MinecraftPlayer')
    rank = models.IntegerField(default=0)


class Server(StandardModel):
    name = models.CharField(max_length=30)
    address = models.CharField(max_length=50)
    secret_key = models.CharField(max_length=10)


class PlayerStats(StandardModel):
    player = models.ForeignKey('MinecraftPlayer', related_name='stats')
    server = models.ForeignKey('Server')
    time_spent = models.IntegerField(default=0)
    first_seen = models.DateTimeField(default=datetime.utcnow)
    last_seen = models.DateTimeField(default=datetime.utcnow)
    last_login = models.DateTimeField(default=datetime.utcnow, null=True)
    banned = models.BooleanField(default=False)
    pvp_logs = models.IntegerField(default=0)
    
    def get_rank(self):
        above = PlayerStats.objects.filter(server=self.server, time_spent__gte=self.time_spent).exclude(player_id=self.player_id)
        return len(above) + 1


class ServerStatus(StandardModel):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    player_count=models.IntegerField(default=0)
    cpu_load = models.FloatField(default=0)
    tps = models.FloatField(default=0)


class MojangStatus(StandardModel):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    website = models.BooleanField(default=True)
    login = models.BooleanField(default=True)
    session = models.BooleanField(default=True)
    account =models.BooleanField(default=True)
    auth = models.BooleanField(default=True)
    skins = models.BooleanField(default=True)


class DeathType(StandardModel):
    type = models.CharField(max_length=100)
    displayname = models.CharField(max_length=100)


class KillType(StandardModel):
    type = models.CharField(max_length=100)
    displayname = models.CharField(max_length=100)


class DeathEvent(StandardModel):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    death_type = models.ForeignKey('DeathType', related_name='death_type')
    victim = models.ForeignKey('MinecraftPlayer', related_name='d_victim')
    killer = models.ForeignKey('MinecraftPlayer', related_name='d_killer', null=True)


class KillEvent(StandardModel):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    kill_type = models.ForeignKey('KillType', related_name='kill_type')
    killer = models.ForeignKey('MinecraftPlayer', related_name='k_killer')


class DeathCount(StandardModel):
    server = models.ForeignKey('Server')
    death_type = models.ForeignKey('DeathType', related_name='dc_death_type', db_index=True)
    victim = models.ForeignKey('MinecraftPlayer', related_name='dc_victim')
    killer = models.ForeignKey('MinecraftPlayer', related_name='dc_killer', null=True)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('server', 'victim', 'death_type', 'killer')

    @classmethod
    def increment(cls, server, death_type, victim, killer):
        death_count, created = cls.objects.get_or_create(server=server,
                                                         death_type=death_type,
                                                         victim=victim,
                                                         killer=killer)
        death_count.count += 1
        death_count.save()


class KillCount(StandardModel):
    server = models.ForeignKey('Server')
    kill_type = models.ForeignKey('KillType', related_name='kc_kill_type', db_index=True)
    killer = models.ForeignKey('MinecraftPlayer', related_name='kc_killer')
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('server', 'killer', 'kill_type')

    @classmethod
    def increment(cls, server, kill_type, killer):
        kill_count, created = cls.objects.get_or_create(server=server,
                                                        kill_type=kill_type,
                                                        killer=killer)
        kill_count.count += 1
        kill_count.save()


class MaterialType(StandardModel):
    type = models.CharField(max_length=32, unique=True)
    displayname = models.CharField(max_length=64)


class OreDiscoveryEvent(StandardModel):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    player = models.ForeignKey('MinecraftPlayer', related_name='ode_player')
    material_type = models.ForeignKey('MaterialType', db_index=True)
    x = models.IntegerField()
    y = models.IntegerField()
    z = models.IntegerField()


class OreDiscoveryCount(StandardModel):
    server = models.ForeignKey('Server')
    player = models.ForeignKey('MinecraftPlayer', related_name='odc_player')
    material_type = models.ForeignKey('MaterialType', db_index=True)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('server', 'player', 'material_type')

    @classmethod
    def increment(cls, server, material_type, player):
        ore_count, created = cls.objects.get_or_create(server=server,
                                                       material_type=material_type,
                                                       player=player)
        ore_count.count += 1
        ore_count.save()


class OreSmeltCount(StandardModel):
    server = models.ForeignKey('Server')
    player = models.ForeignKey('MinecraftPlayer', related_name='osc_player')
    material_type = models.ForeignKey('MaterialType', db_index=True)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('server', 'player', 'material_type')

    @classmethod
    def increment(cls, server, material_type, player, amount):
        ore_count, created = cls.objects.get_or_create(server=server,
                                                       material_type=material_type,
                                                       player=player)
        ore_count.count += amount
        ore_count.save()


class IPTracking(StandardModel):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    ip = models.IPAddressField()
    player = models.ForeignKey('MinecraftPlayer', related_name='ip', null=True)
    user = models.ForeignKey(User, null=True)


class PlayerActivity(StandardModel):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    player = models.ForeignKey('MinecraftPlayer')
    activity_type = models.IntegerField()
