import asyncio
import os
import re
from datetime import datetime
from email.utils import parsedate_tz, mktime_tz
from pytz import utc


def coro_later(loop, delay, coroutine):
    loop.call_later(delay, lambda: asyncio.ensure_future(coroutine))


def load_module(basedir, package, module_name):
    '''Load a python module by its name.

    See: http://stackoverflow.com/a/67692
    '''
    base_dir = os.environ['PROJECT_DIR']
    module_path = os.path.join(base_dir, package, module_name + '.py')
    module_name = package + '.' + module_name
    try:
        # python 3.5
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location(module_name, module_path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    except ImportError:
        # python 3.4
        try:
            from importlib.machinery import SourceFileLoader
            module = SourceFileLoader(module_name, module_path).load_module()
        except ImportError:
            # python 2
            from imp import load_source
            module = load_source(module_name, module_path)

    return module


def create_word_regex(word):
    return re.compile(r'(^|[\s?!.,;])' + word + r'($|[\s?!.,;])')


def parse_date(text):
    timestamp = mktime_tz(parsedate_tz(text))
    return datetime.fromtimestamp(timestamp, utc)


def format_date(date):
    return date.strftime('%a, %d %b %Y %H:%M:%S GMT')
