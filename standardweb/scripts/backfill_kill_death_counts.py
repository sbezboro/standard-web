import copy
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'standardweb.settings'

import rollbar

from django.conf import settings
from django.db import transaction

from standardweb.models import *


# from http://stackoverflow.com/questions/4856882/limiting-memory-use-in-a-large-django-queryset/4856965#4856965
class MemorySavingQuerysetIterator(object):
    def __init__(self,queryset, max_obj_num=100000):
        self._base_queryset = queryset
        self._generator = self._setup()
        self.max_obj_num = max_obj_num

    def _setup(self):
        for i in xrange(0, self._base_queryset.count(), self.max_obj_num):
            # By making a copy of of the queryset and using that to actually access
            # the objects we ensure that there are only `max_obj_num` objects in
            # memory at any given time
            smaller_queryset = copy.deepcopy(self._base_queryset)[i:i + self.max_obj_num]
            print 'Grabbing next %s objects from DB, offset %s' % (self.max_obj_num, i)
            for obj in smaller_queryset.iterator():
                yield obj

    def __iter__(self):
        return self

    def next(self):
        return self._generator.next()


def _death_event_key(death_event):
    return '%d.%d.%d.%d' % (death_event.server_id, death_event.death_type_id,
                            death_event.victim_id, death_event.killer_id or 0)


def _kill_event_key(kill_event):
    return '%d.%d.%d' % (kill_event.server_id, kill_event.kill_type_id,
                         kill_event.killer_id)


def main():
    death_map = {}
    kill_map = {}

    with transaction.commit_manually():
        try:
            for death_event in MemorySavingQuerysetIterator(DeathEvent.objects.filter()):
                death_map.setdefault(_death_event_key(death_event), 0)
                death_map[_death_event_key(death_event)] += 1

            for kill_event in MemorySavingQuerysetIterator(KillEvent.objects.all()):
                kill_map.setdefault(_kill_event_key(kill_event), 0)
                kill_map[_kill_event_key(kill_event)] += 1

            for key, count in death_map.iteritems():
                server_id, death_type_id, victim_id, killer_id = key.split('.')
                params = {
                    'server_id': server_id,
                    'death_type_id': death_type_id,
                    'victim_id': victim_id
                }

                if int(killer_id):
                    params['killer_id'] = killer_id

                obj, created = DeathCount.objects.get_or_create(**params)
                obj.count = count
                obj.save()

            for key, count in kill_map.iteritems():
                server_id, kill_type_id, killer_id = key.split('.')
                params = {
                    'server_id': server_id,
                    'kill_type_id': kill_type_id,
                    'killer_id': killer_id
                }

                obj, created = KillCount.objects.get_or_create(**params)
                obj.count = count
                obj.save()
        except Exception, e:
            transaction.rollback()
            print e
        else:
            transaction.commit()


if __name__ == '__main__':
    rollbar.init(settings.ROLLBAR['access_token'], settings.ROLLBAR['environment'])
    main()
