from collections import Mapping
from copy import deepcopy
from json import load as json_load
import logging
import os

DEFAULT_SETTINGS = {
    'authentication': {
        'username': None,
        'password': None,
    },
    'datastore': {
        'connect_args': {},
        'prefix': 'chatango_bot_', # prefix of stored data's dictionary key
    },
    'connection': {
        'buffer_size': 65536,
        'max_retries': 99,
        'ping_interval': 20, # seconds
        'retry_delay': 10, # seconds
        'timeout': 30, # seconds
    },
    'servers': {
        'anonymous_pm_host': 'b1.chatango.com',
        'anonymous_pm_port': 5222,
        'pm_host': 'c1.chatango.com',
        'pm_port': 5222,
        'chatroom_port': 443,
    },
    'logging': {
        'level': 'info',
    },
    'message_formatter': {
        'max_length': 1800,
        'overflow': 'chunked', # too large, chunked or crop?
    },
    'user_list': {
        'active_filter': 'recent',
        'unique': True,

        'filters': {
            'recent': {
                'size': 50,
            },
        },
    },
    'history': {
        'size': 150,
    },
    'chat': {
        'name_color': '000099',
        'text_color': '000099',
        'text_typeface': '1',
        'text_size': 11,
    },
    'services': [],
}

def _deep_update(obj, data):
    for key in data:
        item = data[key]

        if isinstance(item, Mapping):
            if key not in obj:
                obj[key] = {}
            _deep_update(obj[key], item)
        else:
            obj[key] = item


conf = deepcopy(DEFAULT_SETTINGS)

with open(os.environ['SETTINGS_FILE'], 'r') as f:
    _deep_update(conf, json_load(f))


logging.basicConfig(level=getattr(logging, conf['logging']['level'].upper()))
