import asyncio
import random

from time import time

from .channel import BaseChannel
from .message import Message
from .settings import conf
from .user import User

ROOM_OWNER = 2
ROOM_MODERATOR = 1

class Struct(object):
    def __init__(self, **entries):
        self.__dict__.update(entries)


class Room(BaseChannel):
    """Manages a connection with a Chatango room."""

    user_class = User
    message_class = Message

    owner = None
    usercount = 0
    silent = False
    mods = None

    _botname = None
    _history = None
    _userlist = None
    _banlist = None
    _unbanlist = None
    _mqueue = None
    _connectAmmount = 0
    _premium = False
    _msgs = None
    _i_log = None

    _uid = None
    _aid = None


    def __init__(self, name, *args, **kwargs):
        self.name = name
        super(Room, self).__init__(*args, **kwargs)

        self.mods = set()

        self._mqueue = {}
        self._history = []
        self._userlist = []
        self._msgs = {}
        self._banlist = {}
        self._unbanlist = {}
        self._i_log = []


    def get_server(self):
        return self.mgr.get_room_host(self.name)


    def _disconnect(self):
        self._call_event('onDisconnect')


    @asyncio.coroutine
    def authenticate(self):
        """Chatango authentication."""
        try:
            username, password = self.mgr.get_user_credentials()
            unique_id = str(random.randrange(10 ** 15, 10 ** 16))
            self._send_command('bauth', self.name, unique_id, username,
                    password)

        except ValueError:
            # Login as anon
            self._send_command('bauth', self.name)


    @property
    def botname(self):
        try:
            username, password = self.mgr.get_user_credentials()

            if password is None:
                return '#' + username
            else:
                return username
        except ValueError:
            return self._botname


    @property
    def userlist(self):
        return self._get_userlist()


    @property
    def usernames(self):
        return [user.name for user in self._userlist]


    @property
    def user(self):
        return self.mgr.user


    @property
    def username(self):
        return self.user.name


    @property
    def ownername(self):
        return self.owner.name


    @property
    def modnames(self):
        return [user.name for user in self.mods]


    @property
    def banlist(self):
        return self._banlist.keys()


    @property
    def unbanlist(self):
        return [(record["target"], record["src"]) for record in\
                self._unbanlist.values()]


    def _get_userlist(self, mode=None, unique=None, memory=None):
        ul = None
        if mode is None:
            mode = conf['user_list']['active_filter']

        if unique is None:
            unique = conf['user_list']['unique']

        if memory is None:
            memory = conf['user_list']['filters']['recent']['size']

        if mode == 'recent':
            ul = [hist.user for hist in self._history[-memory:]]
        else:
            ul = self._userlist

        if unique:
            return list(set(ul))
        else:
            return ul


    def disconnect(self):
        future = super(Room, self).disconnect()

        for user in self._userlist:
            user.clearSessionIds(self)

        self._userlist = []
        return future



    def login(self, username, password=None):
        """login as a user or set a name in room"""
        if password is not None:
            self._send_command('blogin', username, password)
        else:
            self._send_command('blogin', username)


    def logout(self):
        """logout of user in a room"""
        self._send_command('blogout')


    def rawMessage(self, msg):
        """
        Send a message without n and f tags.

        @type msg: str
        @param msg: message
        """
        if not self.silent:
            self._send_command('bmsg:tl2r', msg)


    @asyncio.coroutine
    def message(self, msg, html=False):
        """
        Send a message. (Use "\n" for new line)

        @type msg: str
        @param msg: message
        """
        if msg is None:
            return
        msg = msg.rstrip()
        if not html:
            msg = self.html_escape(msg)

        max_length = conf['message_formatter']['max_length']
        overflow = conf['message_formatter']['overflow']

        if len(msg) > max_length:
            if overflow == 'crop':
                yield from self.message(msg[:max_length], html=html)
            elif overflow == 'chunked':
                while len(msg) > 0:
                    sect = msg[:max_length]
                    msg = msg[max_length:]
                    yield from self.message(sect, html=html)
            else:
                raise RuntimeError('Unknown message_formatter: ' + overflow)
            return

        msg = '<n' + self.user.nameColor + '/>' + msg
        if self.botname is not None and not self.botname.startswith('!anon'):
            font_properties = '<f x%0.2i%s="%s">' % (self.user.fontSize,
                    self.user.fontColor, self.user.fontFace)

            if '\n' in msg:
                msg = msg.replace('\n', '</f></p><p' + font_properties)
            msg = font_properties + msg

        msg = msg.replace('~', '&#126;')
        self.rawMessage(msg)


    def setBgMode(self, mode):
        """turn on/off bg"""
        self._send_command('msgbg', str(mode))


    def setRecordingMode(self, mode):
        """turn on/off rcecording"""
        self._send_command('msgmedia', str(mode))


    def addMod(self, user):
        """
        Add a moderator.

        @type user: User
        @param user: User to mod.
        """
        if self.getLevel(self.user) == ROOM_OWNER:
            self._send_command('addmod', user.name)


    def removeMod(self, user):
        """
        Remove a moderator.

        @type user: User
        @param user: User to demod.
        """
        if self.getLevel(self.user) == ROOM_OWNER:
            self._send_command('removemod', user.name)


    def flag(self, message):
        """
        Flag a message.

        @type message: Message
        @param message: message to flag
        """
        self._send_command('g_flag', message.msgid)


    def flagUser(self, user):
        """
        Flag a user.

        @type user: User
        @param user: user to flag

        @rtype: bool
        @return: whether a message to flag was found
        """
        msg = self.getLastMessage(user)
        if msg:
            self.flag(msg)
            return True
        return False


    def deleteMessage(self, message):
        """
        Delete a message. (Moderator only)

        @type message: Message
        @param message: message to delete
        """
        if self.getLevel(self.user) >= ROOM_MODERATOR:
            self._send_command('delmsg', message.msgid)


    def deleteUser(self, user):
        """
        Delete a message. (Moderator only)

        @type message: User
        @param message: delete user's last message
        """
        if self.getLevel(self.user) >= ROOM_MODERATOR:
            msg = self.getLastMessage(user)
            if msg:
                self._send_command('delmsg', msg.msgid)
            return True
        return False


    def delete(self, user):
        """
        compatibility wrapper for deleteUser
        """
        self._log.warning('[obsolete] the delete function is obsolete, ' +\
                'please use deleteUser')

        return self.deleteUser(user)


    def rawClearUser(self, unid, ip, user):
        self._send_command('delallmsg', unid, ip, user)


    def clearUser(self, user):
        """
        Clear all of a user's messages. (Moderator only)

        @type user: User
        @param user: user to delete messages of

        @rtype: bool
        @return: whether a message to delete was found
        """
        if self.getLevel(self.user) >= ROOM_MODERATOR:
            msg = self.getLastMessage(user)
            if msg:
                if msg.user.name[0] in ('!', '#'):
                    self.rawClearUser(msg.unid, msg.ip, '')
                else:
                    self.rawClearUser(msg.unid, msg.ip, msg.user.name)

                return True
        return False


    def clearall(self):
        """Clear all messages. (Owner only)"""
        if self.getLevel(self.user) == ROOM_OWNER:
            self._send_command('clearall')


    def rawBan(self, name, ip, unid):
        """
        Execute the block command using specified arguments.
        (For advanced usage)

        @type name: str
        @param name: name
        @type ip: str
        @param ip: ip address
        @type unid: str
        @param unid: unid
        """
        self._send_command('block', unid, ip, name)


    def ban(self, msg):
        """
        Ban a message's sender. (Moderator only)

        @type message: Message
        @param message: message to ban sender of
        """
        if self.getLevel(self.user) >= ROOM_MODERATOR:
            self.rawBan(msg.user.name, msg.ip, msg.unid)


    def banUser(self, user):
        """
        Ban a user. (Moderator only)

        @type user: User
        @param user: user to ban

        @rtype: bool
        @return: whether a message to ban the user was found
        """
        msg = self.getLastMessage(user)
        if msg:
            self.ban(msg)
            return True
        return False


    def requestBanlist(self):
        """Request an updated banlist."""
        self._send_command('blocklist', 'block', '', 'next', '500')


    def requestUnBanlist(self):
        """Request an updated banlist."""
        self._send_command('blocklist', 'unblock', '', 'next', '500')


    def rawUnban(self, name, ip, unid):
        """
        Execute the unblock command using specified arguments.
        (For advanced usage)

        @type name: str
        @param name: name
        @type ip: str
        @param ip: ip address
        @type unid: str
        @param unid: unid
        """
        self._send_command('removeblock', unid, ip, name)


    def unban(self, user):
        """
        Unban a user. (Moderator only)

        @type user: User
        @param user: user to unban

        @rtype: bool
        @return: whether it succeeded
        """
        rec = self._getBanRecord(user)
        if rec:
            self.rawUnban(rec['target'].name, rec['ip'], rec['unid'])
            return True
        else:
            return False


    def _getBanRecord(self, user):
        return self._banlist.get(user)


    def getLevel(self, user):
        """get the level of user in a room"""
        if user == self.owner:
            return ROOM_OWNER
        if user.name in self.modnames:
            return ROOM_MODERATOR
        return 0


    def getLastMessage(self, user=None):
        """get last message said by user in a room"""
        if user:
            try:
                i = 1
                while True:
                    msg = self._history[-i]
                    if msg.user == user:
                        return msg
                    i += 1
            except IndexError:
                return None
        else:
            try:
                return self._history[-1]
            except IndexError:
                return None
        return None


    def findUser(self, name):
        """check if user is in the room

        return User(name) if name in room else None"""
        name = name.lower()
        udi = {user.name.lower(): user for user in self._userlist}
        cname = None
        for n in udi.keys():
            if name in n:
                if cname:
                    return None #ambiguous!!
                cname = n
        if cname:
            return udi[cname]
        else:
            return None


    def _addHistory(self, msg):
        """
        Add a message to history.

        @type msg: Message
        @param msg: message
        """
        self._history.append(msg)
        if len(self._history) > conf['history']['size']:
            rest, self._history = (self._history[:-conf['history']['size']],
                    self._history[-conf['history']['size']:])

            for msg in rest:
                msg.detach()


    @staticmethod
    def _getAnonId(n, ssid):
        """Gets the anon's id."""
        if n is None:
            n = '5504'
        try:
            return ''.join(str(x[0] + x[1])[-1] for x in zip(
                        [int(x) for x in n],
                        [int(x) for x in ssid[4:]])
                    )

        except ValueError:
            return 'NNNN'


    @staticmethod
    def _parseNameColor(n):
        """This just returns its argument, should return the name color."""
        #probably is already the name
        return n


    @staticmethod
    def _parseFont(f):
        """Parses the contents of a f tag and returns color, face and size."""
        #' xSZCOL="FONT"'
        try: #TODO: remove quick hack
            # sizeColor, fontFace
            sizecolor, _ = f.split('=', 1)
            sizecolor = sizecolor.strip()
            size = int(sizecolor[1:3])
            col = sizecolor[3:6]
            if col == '':
                col = None
            face = f.split('"', 2)[1]
            return col, face, size
        except: # pylint: disable=bare-except
            return None, None, None


    ## Received commands


    @asyncio.coroutine
    def _rcmd_ok(self, args):
        try:
            username, password = self.mgr.get_user_credentials()

            if password is None:
                # if got name, join room as name and no password
                if args[2] == "N":
                    self.login(username)

            elif args[2] != 'M':
                # unsuccessful login
                self._call_event('onLoginFail')
                self.disconnect()

        except ValueError:
            # if no name, join room as anon and no password
            if args[2] == 'N':
                n = args[4].rsplit('.', 1)[0]
                n = n[-4:]
                aid = args[1][0:8]
                pid = '!anon' + self._getAnonId(n, aid)
                self._botname = pid
                self.user.nameColor = n

        self.owner = self.user_class.create(args[0])
        self._uid = args[1]
        self._aid = args[1][4:8]
        self.mods.clear()
        for name in args[6].split(';'):
            self.mods.add(self.user_class.create(name.split(',')[0]))

        self._i_log.clear()


    @asyncio.coroutine
    def _rcmd_denied(self, args):
        self.disconnect()
        self._call_event('onConnectFail')


    @asyncio.coroutine
    def _rcmd_inited(self, args):
        self._send_command('g_participants', 'start')
        self._send_command('getpremium', '1')
        self.requestBanlist()
        self.requestUnBanlist()
        if self._connectAmmount == 0:
            self._call_event('onConnect')
            for msg in reversed(self._i_log):
                user = msg.user
                self._call_event('onHistoryMessage', user, msg)
                self._addHistory(msg)
            self._i_log.clear()
        else:
            self._call_event('onReconnect')
        self._connectAmmount += 1


    @asyncio.coroutine
    def _rcmd_premium(self, args):
        if float(args[1]) > time():
            self._premium = True
            if self.user._mbg:
                self.setBgMode(1)
            if self.user._mrec:
                self.setRecordingMode(1)
        else:
            self._premium = False


    @asyncio.coroutine
    def _rcmd_mods(self, args):
        modnames = args
        mods = set()
        for name in modnames:
            mods.add(self.user_class.create(name.split(',')[0]))

        premods = self.mods
        for user in mods - premods: #modded
            self.mods.add(user)
            self._call_event('onModAdd', user)

        for user in premods - mods: #demodded
            self.mods.remove(user)
            self._call_event('onModRemove', user)

        self._call_event('onModChange')


    @asyncio.coroutine
    def _rcmd_b(self, args):
        mtime = float(args[0])
        puid = args[3]
        ip = args[6]
        name = args[1]
        rawmsg = ':'.join(args[9:])
        msg, n, f = self.clean_message(rawmsg)
        if name == '':
            nameColor = None
            name = '#' + args[2]
            if name == '#':
                name = '!anon' + self._getAnonId(n, puid)
        else:
            if n:
                nameColor = self._parseNameColor(n)
            else:
                nameColor = None

        i = args[5]
        unid = args[4]
        user = self.user_class.create(name)
        if puid:
            user.puid = puid

        #Create an anonymous message and queue it because msgid is unknown.
        if f:
            fontColor, fontFace, fontSize = self._parseFont(f)
        else:
            fontColor, fontFace, fontSize = None, None, None

        msg = self.message_class(time=mtime, user=user, body=msg, raw=rawmsg,
                ip=ip, nameColor=nameColor, fontColor=fontColor,
                fontFace=fontFace, fontSize=fontSize, unid=unid, room=self)

        self._mqueue[i] = msg


    @asyncio.coroutine
    def _rcmd_u(self, args):
        temp = Struct(**self._mqueue)
        if hasattr(temp, args[0]):
            msg = getattr(temp, args[0])
            if msg.user != self.user:
                msg.user.fontColor = msg.fontColor
                msg.user.fontFace = msg.fontFace
                msg.user.fontSize = msg.fontSize
                msg.user.nameColor = msg.nameColor

            del self._mqueue[args[0]]
            msg.attach(self, args[1])
            self._addHistory(msg)
            self._call_event('onMessage', msg.user, msg)


    @asyncio.coroutine
    def _rcmd_i(self, args):
        mtime = float(args[0])
        puid = args[3]
        ip = args[6]
        name = args[1]
        rawmsg = ':'.join(args[9:])
        msg, n, f = self.clean_message(rawmsg)
        if name == '':
            nameColor = None
            name = '#' + args[2]
            if name == '#':
                name = '!anon' + self._getAnonId(n, puid)
        else:
            if n:
                nameColor = self._parseNameColor(n)
            else:
                nameColor = None

        #i = args[5]
        unid = args[4]
        user = self.user_class.create(name)
        if puid:
            user.puid = puid

        #Create an anonymous message and queue it because msgid is unknown.
        if f:
            fontColor, fontFace, fontSize = self._parseFont(f)
        else:
            fontColor, fontFace, fontSize = None, None, None

        msg = self.message_class(time=mtime, user=user, body=msg, raw=rawmsg,
                ip=ip, nameColor=nameColor, fontColor=fontColor,
                fontFace=fontFace, fontSize=fontSize, unid=unid, room=self)

        self._i_log.append(msg)


    @asyncio.coroutine
    def _rcmd_g_participants(self, args):
        args = ':'.join(args)
        args = args.split(';')
        for data in args:
            data = data.split(':')
            name = data[3].lower()
            if name == 'none':
                continue
            user = self.user_class.create(name=name, room=self)
            user.addSessionId(self, data[0])
            self._userlist.append(user)
        self._call_event('onUserCountChange')


    @asyncio.coroutine
    def _rcmd_participant(self, args):
        name = args[3].lower()
        if name == "none":
            return
        user = self.user_class.create(name)
        puid = args[2]
        if puid:
            user.puid = puid

        if args[0] == '0': #leave
            user.removeSessionId(self, args[1])
            try:
                # last_on, is_on, idle
                _, _, _ = self._status[user]
            except: # pylint: disable=bare-except
                pass

            #if user not in self._userlist or not self.mgr._userlistEventUnique:
            self._call_event('onLeave', user)

        else: #join
            user.addSessionId(self, args[1])
            #doEvent = user not in self._userlist
            self._userlist.append(user)
            #if doEvent or not self.mgr._userlistEventUnique:
            self._call_event('onJoin', user)


    @asyncio.coroutine
    def _rcmd_show_fw(self, args):
        self._call_event('onFloodWarning')


    @asyncio.coroutine
    def _rcmd_show_tb(self, args):
        self._call_event('onFloodBan')


    @asyncio.coroutine
    def _rcmd_tb(self, args):
        self._call_event('onFloodBanRepeat')


    @asyncio.coroutine
    def _rcmd_delete(self, args):
        msg = self._msgs.get(args[0])
        if msg:
            if msg in self._history:
                self._history.remove(msg)
                self._call_event('onMessageDelete', msg.user, msg)
                msg.detach()


    @asyncio.coroutine
    def _rcmd_deleteall(self, args):
        for msgid in args:
            yield from self._rcmd_delete([msgid])


    @asyncio.coroutine
    def _rcmd_n(self, args):
        self.usercount = int(args[0], 16)
        self._call_event('onUserCountChange')


    @asyncio.coroutine
    def _rcmd_blocklist(self, args):
        self._banlist = dict()
        sections = ':'.join(args).split(';')
        for section in sections:
            params = section.split(":")
            if len(params) != 5:
                continue
            if params[2] == '':
                continue

            user = self.user_class.create(params[2])
            self._banlist[user] = {
                'unid': params[0],
                'ip': params[1],
                'target': user,
                'time': float(params[3]),
                'src': self.user_class.create(params[4]),
            }
        self._call_event('onBanlistUpdate')


    @asyncio.coroutine
    def _rcmd_unblocklist(self, args):
        self._unbanlist = dict()
        sections = ':'.join(args).split(';')
        for section in sections:
            params = section.split(':')
            if len(params) != 5:
                continue
            if params[2] == '':
                continue

            user = self.user_class.create(params[2])
            self._unbanlist[user] = {
                'unid': params[0],
                'ip': params[1],
                'target': user,
                'time': float(params[3]),
                'src': self.user_class.create(params[4]),
            }
        self._call_event('onUnBanlistUpdate')


    @asyncio.coroutine
    def _rcmd_blocked(self, args):
        if args[2] == '':
            return
        target = self.user_class.create(args[2])
        user = self.user_class.create(args[3])
        self._banlist[target] = {
            'unid': args[0],
            'ip': args[1],
            'target': target,
            'time': float(args[4]),
            'src': user,
        }
        self._call_event('onBan', user, target)


    @asyncio.coroutine
    def _rcmd_unblocked(self, args):
        if args[2] == r'':
            return
        target = self.user_class.create(args[2])
        user = self.user_class.create(args[3])
        del self._banlist[target]
        self._unbanlist[user] = {
            'unid': args[0],
            'ip': args[1],
            'target': target,
            'time': float(args[4]),
            'src': user,
        }
        self._call_event('onUnban', user, target)
