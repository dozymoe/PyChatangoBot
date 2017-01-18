import asyncio
from time import time
import aiohttp
import async_timeout

from .channel import BaseChannel
from .settings import conf
from .user import User

class PM(BaseChannel):
    """Manages a connection with Chatango PM."""

    user_class = User

    contacts = None
    blocklist = None

    _status = None

    def __init__(self, *args, **kwargs):
        super(PM, self).__init__(*args, **kwargs)

        self.blocklist = set()
        self.contacts = set()
        self._status = {}


    def get_server(self):
        return self.mgr.get_pm_host()


    def _disconnect(self):
        self._call_event('onPMDisconnect')


    @asyncio.coroutine
    def authenticate(self):
        try:
            username, password = self.mgr.get_user_credentials()
        except ValueError:
            return

        auth_token = yield from self._get_auth_token(username, password)
        if auth_token:
            self._send_command('tlogin', auth_token, '2')
        else:
            self._call_event('onLoginFail')
            self.disconnect()


    @asyncio.coroutine
    def _get_auth_token(self, name, password):
        """
        Request an auid using name and password.

        @type name: str
        @param name: name
        @type password: str
        @param password: password

        @rtype: str
        @return: auid
        """
        payload = {
            'user_id': name,
            'password': password,
            'storecookie': 'on',
            'checkerrors': 'yes',
        }
        token = None
        session = aiohttp.ClientSession(loop=self._loop)
        try:
            with async_timeout.timeout(conf['connection']['timeout']):
                resp = yield from session.post('https://chatango.com/login',
                        data=payload)

                token = resp.cookies['auth.chatango.com'].value
                yield from resp.release()
        except asyncio.TimeoutError:
            pass
        except: # pylint:disable=bare-except
            self._log.exception('PM::_get_auth_token')
        finally:
            session.close()

        return token


    @asyncio.coroutine
    def message(self, user, msg):
        """send a pm to a user"""
        if msg is not None:
            self._send_command('msg', user.name, msg)


    def addContact(self, user):
        """add contact"""
        if user not in self.contacts:
            self._send_command('wladd', user.name)
            self.contacts.add(user)
            self._call_event('onPMContactAdd', user)


    def removeContact(self, user):
        """remove contact"""
        if user in self.contacts:
            self._send_command('wldelete', user.name)
            self.contacts.remove(user)
            self._call_event('onPMContactRemove', user)


    def block(self, user):
        """block a person"""
        if user not in self.blocklist:
            self._send_command('block', user.name, user.name, 'S')
            self.blocklist.add(user)
            self._call_event('onPMBlock', user)


    def unblock(self, user):
        """unblock a person"""
        if user in self.blocklist:
            self._send_command('unblock', user.name)


    def track(self, user):
        """get and store status of person for future use"""
        self._send_command('track', user.name)


    def checkOnline(self, user):
        """return True if online, False if offline, None if unknown"""
        if user in self._status:
            return self._status[user][1]
        else:
            return None


    def getIdle(self, user):
        """
        return last active time, time.time() if isn't idle, 0 if offline,
        None if unknown
        """
        if not user in self._status:
            return None
        elif not self._status[user][1]:
            return 0
        elif not self._status[user][2]:
            return time()
        else:
            return self._status[user][2]


    ## Received commands


    @asyncio.coroutine
    def _rcmd_OK(self, args):
        self._send_command('wl')
        self._send_command('getblock')
        self._call_event('onPMConnect')


    @asyncio.coroutine
    def _rcmd_wl(self, args):
        self.contacts = set()
        for i in range(len(args) // 4):
            name, last_on, is_on, idle = args[i * 4: i * 4 + 4]
            user = self.user_class.create(name)
            if last_on is "None":
                #in case chatango gives a "None" as data argument
                pass
            elif not is_on == "on":
                self._status[user] = [int(last_on), False, 0]
            elif idle == '0':
                self._status[user] = [int(last_on), True, 0]
            else:
                self._status[user] = [int(last_on), True,
                        time() - int(idle) * 60]

            self.contacts.add(user)

        self._call_event('onPMContactlistReceive')


    @asyncio.coroutine
    def _rcmd_block_list(self, args):
        self.blocklist = set()
        for name in args:
            if name == "":
                continue
            self.blocklist.add(self.user_class.create(name))


    @asyncio.coroutine
    def _rcmd_idleupdate(self, args):
        user = self.user_class.create(args[0])
        try:
            # last_on, is_on, idle
            last_on, is_on, _ = self._status[user]
        except: # pylint: disable=bare-except
            pass

        if args[1] == '1':
            self._status[user] = [last_on, is_on, 0]
        else:
            try:
                self._status[user] = [last_on, is_on, time()]
            except: # pylint: disable=bare-except
                pass


    @asyncio.coroutine
    def _rcmd_track(self, args):
        user = self.user_class.create(args[0])
        if user in self._status:
            last_on = self._status[user][0]
        else:
            last_on = 0

        if args[1] == '0':
            idle = 0
        else:
            idle = time() - int(args[1]) * 60

        is_on = args[2] == "online"

        self._status[user] = [last_on, is_on, idle]


    @asyncio.coroutine
    def _rcmd_DENIED(self, args):
        self._call_event('onLoginFail')
        self.disconnect()


    @asyncio.coroutine
    def _rcmd_msg(self, args):
        user = self.user_class.create(args[0])
        body = self.strip_tags(':'.join(args[5:]))
        self._call_event('onPMMessage', user, body)


    @asyncio.coroutine
    def _rcmd_msgoff(self, args):
        user = self.user_class.create(args[0])
        body = self.strip_tags(':'.join(args[5:]))
        self._call_event('onPMOfflineMessage', user, body)


    @asyncio.coroutine
    def _rcmd_wlonline(self, args):
        user = self.user_class.create(args[0])
        last_on = float(args[1])
        self._status[user] = [last_on, True, last_on]
        self._call_event('onPMContactOnline', user)


    @asyncio.coroutine
    def _rcmd_wloffline(self, args):
        user = self.user_class.create(args[0])
        last_on = float(args[1])
        self._status[user] = [last_on, False, 0]
        self._call_event('onPMContactOffline', user)


    @asyncio.coroutine
    def _rcmd_kickingoff(self, args):
        self.disconnect()


    @asyncio.coroutine
    def _rcmd_toofast(self, args):
        self.disconnect()


    @asyncio.coroutine
    def _rcmd_unblocked(self, args):
        """call when successfully unblocked"""
        user = self.user_class.create(args[0])
        if user in self.blocklist:
            self.blocklist.remove(user)
            self._call_event('onPMUnblock', user)
