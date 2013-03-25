from django.db import models
from datetime import datetime

class MinecraftPlayer(models.Model):
    username = models.CharField(max_length=30, unique=True)
    nickname = models.CharField(max_length=30, null=True)
    
    def __str__(self):
        return self.username
    
class Server(models.Model):
    name = models.CharField(max_length=30)
    address = models.CharField(max_length=50)

class PlayerStats(models.Model):
    player = models.ForeignKey('MinecraftPlayer')
    server = models.ForeignKey('Server')
    time_spent = models.IntegerField(default = 0)
    first_seen = models.DateTimeField(default = datetime.utcnow)
    last_seen = models.DateTimeField(default = datetime.utcnow)
    last_login = models.DateTimeField(default = datetime.utcnow, null=True)
    banned = models.BooleanField(default=False)
    
    def rank(self, server_id):
        above = PlayerStats.objects.filter(server=server_id, time_spent__gte=self.time_spent).exclude(player_id=self.player_id)
        return len(above) + 1
    

class ServerStatus(models.Model):
    timestamp = models.DateTimeField(default = datetime.utcnow)
    server = models.ForeignKey('Server')
    player_count = models.IntegerField(default = 0)
    cpu_load = models.FloatField(default = 0)
    
class MojangStatus(models.Model):
    timestamp = models.DateTimeField(default = datetime.utcnow)
    website = models.BooleanField(default=True)
    login = models.BooleanField(default=True)
    session = models.BooleanField(default=True)
    account = models.BooleanField(default=True)
    auth = models.BooleanField(default=True)
    skins = models.BooleanField(default=True)
    
class DeathType(models.Model):
    type = models.CharField(max_length = 100)
    displayname = models.CharField(max_length = 100)
    
class KillType(models.Model):
    type = models.CharField(max_length = 100)
    displayname = models.CharField(max_length = 100)

class DeathEvent(models.Model):
    timestamp = models.DateTimeField(default = datetime.utcnow)
    server = models.ForeignKey('Server')
    death_type = models.ForeignKey('DeathType', related_name = 'death_type')
    victim = models.ForeignKey('MinecraftPlayer', related_name = 'd_victim')
    killer = models.ForeignKey('MinecraftPlayer', related_name = 'd_killer', null=True)
    
class KillEvent(models.Model):
    timestamp = models.DateTimeField(default = datetime.utcnow)
    server = models.ForeignKey('Server')
    kill_type = models.ForeignKey('KillType', related_name = 'kill_type')
    killer = models.ForeignKey('MinecraftPlayer', related_name = 'k_killer')
    victim = models.ForeignKey('MinecraftPlayer', related_name = 'k_victim', null=True)
'''
class FactionRelation(models.Model):
    faction1 = models.ForeignKey('Faction', related_name = 'faction1')
    faction2 = models.ForeignKey('Faction', related_name = 'faction2')
    relation_type = models.IntegerField(default = 0)
    
    class Meta:
        unique_together = ('faction1', 'faction2')
    
class MinecraftFaction(models.Model):
    name = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=100)
    allies = models.ManyToManyField('self', through='FactionRelation', symmetrical=False)
    enemies = models.ManyToManyField('self', through='FactionRelation', symmetrical=False)
'''