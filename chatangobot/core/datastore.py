from redis import Redis

from .settings import conf

datastore = Redis(**conf['datastore']['connect_args'])


def datastore_key(key):
    return conf['datastore']['prefix'] + key
