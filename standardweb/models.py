from django.contrib.auth.models import User
from django.db import models
from datetime import datetime

from ansi2html import Ansi2HTMLConverter
ansi_converter = Ansi2HTMLConverter()

from standardweb.lib import helpers as h

class MinecraftPlayer(models.Model):
    username = models.CharField(max_length=30, unique=True)
    nickname = models.CharField(max_length=30, null=True)
    nickname_ansi = models.CharField(max_length=256, null=True)
    
    def __str__(self):
        return self.nickname or self.username
    
    @property
    def nickname_html(self):
        return ansi_converter.convert(self.nickname_ansi, full=False) if self.nickname_ansi else None
    
    @property
    def displayname_html(self):
        return self.nickname_html if self.nickname else self.username
    
    @property
    def last_seen(self):
        return PlayerStats.objects.get(player=self, server=2).last_seen
    

class VeteranStatus(models.Model):
    player = models.ForeignKey('MinecraftPlayer')
    rank = models.IntegerField(default=0)
    
class Server(models.Model):
    name = models.CharField(max_length=30)
    address = models.CharField(max_length=50)
    secret_key = models.CharField(max_length=10)

class PlayerStats(models.Model):
    player = models.ForeignKey('MinecraftPlayer', related_name='stats')
    server = models.ForeignKey('Server')
    time_spent = models.IntegerField(default=0)
    first_seen = models.DateTimeField(default=datetime.utcnow)
    last_seen = models.DateTimeField(default=datetime.utcnow)
    last_login = models.DateTimeField(default=datetime.utcnow, null=True)
    banned = models.BooleanField(default=False)
    
    def get_rank(self):
        above = PlayerStats.objects.filter(server=self.server, time_spent__gte=self.time_spent).exclude(player_id=self.player_id)
        return len(above) + 1

class ServerStatus(models.Model):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    player_count=models.IntegerField(default=0)
    cpu_load = models.FloatField(default=0)
    tps = models.FloatField(default=0)
    
class MojangStatus(models.Model):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    website = models.BooleanField(default=True)
    login = models.BooleanField(default=True)
    session = models.BooleanField(default=True)
    account =models.BooleanField(default=True)
    auth = models.BooleanField(default=True)
    skins = models.BooleanField(default=True)
    
class DeathType(models.Model):
    type = models.CharField(max_length = 100)
    displayname = models.CharField(max_length = 100)
    
class KillType(models.Model):
    type = models.CharField(max_length = 100)
    displayname = models.CharField(max_length = 100)

class DeathEvent(models.Model):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    death_type = models.ForeignKey('DeathType', related_name = 'death_type')
    victim = models.ForeignKey('MinecraftPlayer', related_name = 'd_victim')
    killer = models.ForeignKey('MinecraftPlayer', related_name = 'd_killer', null=True)
    
class KillEvent(models.Model):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    kill_type = models.ForeignKey('KillType', related_name = 'kill_type')
    killer = models.ForeignKey('MinecraftPlayer', related_name = 'k_killer')
    victim = models.ForeignKey('MinecraftPlayer', related_name = 'k_victim', null=True)

class IPTracking(models.Model):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    ip = models.IPAddressField()
    player = models.ForeignKey('MinecraftPlayer', related_name='ip', null=True)
    user = models.ForeignKey(User, null=True)

class PlayerActivity(models.Model):
    timestamp = models.DateTimeField(default=datetime.utcnow)
    server = models.ForeignKey('Server')
    player = models.ForeignKey('MinecraftPlayer')
    activity_type = models.IntegerField()


'''
class FactionRelation(models.Model):
    faction1 = models.ForeignKey('Faction', related_name = 'faction1')
    faction2 = models.ForeignKey('Faction', related_name = 'faction2')
    relation_type = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ('faction1', 'faction2')
    
class MinecraftFaction(models.Model):
    name = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=100)
    allies = models.ManyToManyField('self', through='FactionRelation', symmetrical=False)
    enemies = models.ManyToManyField('self', through='FactionRelation', symmetrical=False)
'''