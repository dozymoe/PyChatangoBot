import asyncio
from logging import getLogger

from .channel import BaseChannel
from .user import User

class AnonPM(BaseChannel):
    """Manages connection with Chatango anon PM."""

    user_class = User

    def __init__(self, name, *args, **kwargs):
        self.name = name
        super(AnonPM, self).__init__(*args, **kwargs)


    def get_server(self):
        return self.mgr.get_anonpm_host()


    def _disconnect(self):
        self._call_event('onAnonPMDisconnect',
                self.user_class.create(self.name))


    @asyncio.coroutine
    def authenticate(self):
        self._send_command('mhs', 'mini', 'unknown', self.name)


    @asyncio.coroutine
    def message(self, user, msg):
        """send a pm to a user"""
        if msg is not None:
            self._send_command('msg', user.name, msg)


    ## Received Commands


    @asyncio.coroutine
    def _rcmd_mhs(self, args):
        """
        note to future maintainers

        args[1] is ether "online" or "offline"
        """
        self.disconnect()


    @asyncio.coroutine
    def _rcmd_msg(self, args):
        user = self.user_class.create(args[0])
        body = self.strip_tags(':'.join(args[5:]))
        self._call_event('onPMMessage', user, body)


class AnonPMManager(object):
    """Comparable wrapper for anon Chatango PM"""

    channel_class = AnonPM

    mgr = None

    _channels = None

    _log = None
    _loop = None

    def __init__(self, loop, mgr):
        self.mgr = mgr
        self._log = getLogger('AnonPMManager')
        self._loop = loop

        self._channels = {}


    @asyncio.coroutine
    def connect(self, username):
        channel = self.channel_class(loop=self._loop, mgr=self.mgr,
                name=username)

        self._channels[username.lower()] = channel

        yield from channel.connect()


    def disconnect(self):
        tasks = []

        for channel in self._channels.values():
            future = channel.disconnect()
            if future is not None:
                tasks.append(future)

        future = asyncio.gather(*tasks, loop=self._loop, return_exceptions=True)
        return future


    @asyncio.coroutine
    def message(self, user, msg):
        """send a pm to a user"""
        username = user.name.lower()

        if not username in self._channels:
            yield from self.connect(user.name)
            yield from asyncio.sleep(5)

        yield from self._channels[username].message(user, msg)
