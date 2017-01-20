import asyncio

from re import search
from uuid import uuid4
from html import escape, unescape
from logging import getLogger
from circularbuffer import CircularBuffer # pylint:disable=no-name-in-module
from bleach import clean

from .settings import conf
from ..utils import coro_later

class BaseChannel(asyncio.Protocol):
    """Manages chatroom."""

    connected = False
    mgr = None
    name = None

    event_name_ping = 'onPing'

    _buf = None
    _cid = None # Connection Id
    _conn = None
    _log = None
    _loop = None
    _future = None

    _firstCommand = True


    def clean_message(self, html):
        n = search(r'<n(.*?)/>', html)
        if n:
            n = n.group(1)

        f = search(r'<f(.*?)>', html)
        if f:
            f = f.group(1)

        return (unescape(clean(html, strip=True)), n, f)


    def html_escape(self, text, quote=False):
        return escape(text, quote)


    def strip_tags(self, text):
        return clean(text, strip=True)


    def get_server(self):
        raise NotImplementedError()


    @asyncio.coroutine
    def authenticate(self):
        raise NotImplementedError()


    def _disconnect(self):
        pass


    @asyncio.coroutine
    def connect(self):
        """Connect or reconnect to server.
        see: http://stackoverflow.com/a/26004654
        """
        host, port = self.get_server()
        retries = conf['connection']['max_retries']
        retry_delay = conf['connection']['retry_delay']
        self.connected = True
        while retries > 0 and self.connected:
            retries -= 1
            try:
                self._cid = uuid4().int
                self._buf.clear()

                yield from self._loop.create_connection(self, host, port)
                if self._future is None:
                    try:
                        self._future = self._loop.create_future()
                    except AttributeError:
                        self._future = asyncio.Future()
                return

            except OSError:
                self._log.info('Failed to connect, retrying in %i seconds...',
                        retry_delay)

                yield from asyncio.sleep(retry_delay)
            except: # pylint: disable=bare-except
                break

        self.connected = False


    def disconnect(self):
        """Disconnect from server.

        Keep this function idempotent, can be called multiple times without
        having to check if certain flags were set.
        """
        future = self._future

        # This will cancel reconnects
        self.connected = False

        # This will cancel self._ping infinite-loop
        self._cid = None

        if self._conn is not None:
            self._conn.close()

        # Connection was never made, create false Future
        if future is None:
            future = asyncio.Future()
            future.set_result(None)

        return future


    def connection_made(self, transport):
        self._conn = transport
        self._firstCommand = True

        asyncio.ensure_future(self.authenticate())
        asyncio.ensure_future(self._ping(self._cid))


    def connection_lost(self, exc):
        self._conn = None
        if exc is not None:
            self._log.warning(repr(exc))

        if not self.connected:
            self._disconnect()
            self._future.set_result(None)
            self._future = None
            return

        coro_later(self._loop, conf['connection']['retry_delay'],
                self.connect())


    def data_received(self, data):
        total = len(data)
        wrote = 0
        while wrote < total:
            count = self._buf.write(data[wrote:])
            wrote += count

            while True:
                try:
                    pos = self._buf.index(b'\0')
                except ValueError:
                    break

                recv = self._buf.read(pos)
                # drop the \0
                self._buf.read(1)

                recv = recv.decode('utf-8', errors='replace').rstrip('\r\n')
                asyncio.ensure_future(self._process(recv))


    @asyncio.coroutine
    def _process(self, recv):
        """Process a command string.

        @type data: str
        @param data: the command string
        """
        self._call_event('onRaw', recv)

        data = recv.split(':')
        cmd, args = data[0], data[1:]

        func = '_rcmd_' + cmd
        if hasattr(self, func):
            yield from getattr(self, func)(args)
        elif len(recv):
            self._log.warning('Unknown data received: ' + repr(recv))


    def _call_event(self, name, *args, **kwargs):
        asyncio.ensure_future(getattr(self.mgr, name)(self, *args, **kwargs))
        asyncio.ensure_future(self.mgr.onEventCalled(self, name, *args,
                **kwargs))


    def _send_command(self, *args):
        """
        Send a command.

        @type args: [str, str, ...]
        @param args: command and list of arguments
        """
        if self._conn is None:
            return

        if self._firstCommand:
            terminator = b'\x00'
            self._firstCommand = False
        else:
            terminator = b'\r\n\x00'

        self._conn.write(':'.join(args).encode('utf-8') + terminator)


    @asyncio.coroutine
    def _ping(self, unique_id):
        """Send a ping."""
        interval = conf['connection']['ping_interval']
        count = interval / 10
        if interval % 10:
            count += 1

        while count > 0:
            count -= 1
            yield from asyncio.sleep(10)
            if self._cid != unique_id:
                return

        self._send_command('')
        self._call_event(self.event_name_ping)

        asyncio.ensure_future(self._ping(unique_id))


    def __call__(self):
        """Dummy function to be use as ProtocolFactory for asyncio."""
        return self


    def __init__(self, loop, mgr):
        self.mgr = mgr
        self._loop = loop
        self._buf = CircularBuffer(conf['connection']['buffer_size'])

        log_name = type(self).__name__
        if self.name is not None:
            log_name += '(%s)' % self.name

        self._log = getLogger(log_name)
