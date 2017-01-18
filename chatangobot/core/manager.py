import asyncio
from logging import getLogger

from .settings import conf
from .room import Room
from .user import User
from .pm import PM
from .anonpm import AnonPMManager

class Manager(object):
    """Class that manages multiple connections."""

    room_class = Room
    user_class = User
    pm_class = PM
    anonpm_class = AnonPMManager

    user = None
    rooms = None
    pm = None

    _loop = None
    _log = None
    _future = None

    _userlistEventUnique = False

    @property
    def roomnames(self):
        return [room.name for room in self.rooms.values()]


    def __init__(self, loop, pm=True):
        self._loop = loop
        self._log = getLogger(type(self).__name__)

        self.rooms = {}
        self.user = self.user_class.create(conf['authentication']['username'])

        if pm:
            _, password = self.get_user_credentials()
            if password:
                self.pm = self.pm_class(loop=loop, mgr=self)
                asyncio.ensure_future(self.pm.connect())
            else:
                self.pm = self.anonpm_class(loop=loop, mgr=self) # pylint: disable=redefined-variable-type

        asyncio.ensure_future(self.onInit())


    def get_room_host(self, room_name):
        """
        Get the server host for a certain room.

        @type group: str
        @param group: room name

        @rtype: str
        @return: the server's hostname
        """
        specials = {
            'mitvcanal': 56,
            'animeultimacom': 34,
            'cricket365live': 21,
            'pokemonepisodeorg': 22,
            'animelinkz': 20,
            'sport24lt': 56,
            'narutowire': 10,
            'watchanimeonn': 22,
            'cricvid-hitcric-': 51,
            'narutochatt': 70,
            'leeplarp': 27,
            'stream2watch3': 56,
            'ttvsports': 56,
            'ver-anime': 8,
            'vipstand': 21,
            'eafangames': 56,
            'soccerjumbo': 21,
            'myfoxdfw': 67,
            'kiiiikiii': 21,
            'de-livechat': 5,
            'rgsmotrisport': 51,
            'dbzepisodeorg': 10,
            'watch-dragonball': 8,
            'peliculas-flv': 69,
            'tvanimefreak': 54,
            'tvtvanimefreak': 54,
        }
        tsweights = (
            ('5', 75),
            ('6', 75),
            ('7', 75),
            ('8', 75),
            ('16', 75),
            ('17', 75),
            ('18', 75),
            ('9', 95),
            ('11', 95),
            ('12', 95),
            ('13', 95),
            ('14', 95),
            ('15', 95),
            ('19', 110),
            ('23', 110),
            ('24', 110),
            ('25', 110),
            ('26', 110),
            ('28', 104),
            ('29', 104),
            ('30', 104),
            ('31', 104),
            ('32', 104),
            ('33', 104),
            ('35', 101),
            ('36', 101),
            ('37', 101),
            ('38', 101),
            ('39', 101),
            ('40', 101),
            ('41', 101),
            ('42', 101),
            ('43', 101),
            ('44', 101),
            ('45', 101),
            ('46', 101),
            ('47', 101),
            ('48', 101),
            ('49', 101),
            ('50', 101),
            ('52', 110),
            ('53', 110),
            ('55', 110),
            ('57', 110),
            ('58', 110),
            ('59', 110),
            ('60', 110),
            ('61', 110),
            ('62', 110),
            ('63', 110),
            ('64', 110),
            ('65', 110),
            ('66', 110),
            ('68', 95),
            ('71', 116),
            ('72', 116),
            ('73', 116),
            ('74', 116),
            ('75', 116),
            ('76', 116),
            ('77', 116),
            ('78', 116),
            ('79', 116),
            ('80', 116),
            ('81', 116),
            ('82', 116),
            ('83', 116),
            ('84', 116),
        )
        try:
            sn = specials[room_name]
        except KeyError:
            group = room_name.replace('_', 'q').replace('-', 'q')
            fnv = float(int(group[0:min(5, len(group))], 36))
            lnv = group[6: (6 + min(3, len(group) - 5))]
            if(lnv):
                lnv = float(int(lnv, 36))
                lnv = max(lnv, 1000)
            else:
                lnv = float(1000)
            num = (fnv % lnv) / lnv
            maxnum = sum(map(lambda x: x[1], tsweights))
            cumfreq = 0
            sn = 0
            for wgt in tsweights:
                cumfreq += float(wgt[1]) / maxnum
                if(num <= cumfreq):
                    sn = int(wgt[0])
                    break

        host = 's%s.chatango.com' % sn
        port = conf['servers']['chatroom_port']
        return (host, port)


    def get_anonpm_host(self):
        host = conf['servers']['anonymous_pm_host']
        port = conf['servers']['anonymous_pm_port']
        return (host, port)


    def get_pm_host(self):
        host = conf['servers']['pm_host']
        port = conf['servers']['pm_port']
        return (host, port)


    def get_user_credentials(self):
        username = conf['authentication']['username']
        password = conf['authentication']['password']
        return (username, password)


    @asyncio.coroutine
    def joinRoom(self, room_name):
        """
        Join a room or return None if already joined.

        @type room: str
        @param room: room to join

        @rtype: Room or None
        @return: True or nothing
        """
        room_name = room_name.lower()
        room = self.rooms.get(room_name)
        if room is None:
            room = self.room_class(name=room_name, loop=self._loop, mgr=self)
            self.rooms[room_name] = room

        if not room.connected:
            yield from room.connect()

        return room


    @asyncio.coroutine
    def leaveRoom(self, room_name):
        """
        Leave a room.

        @type room: str
        @param room: room to leave
        """
        try:
            room = self.rooms.pop(room_name.lower())
            yield from room.disconnect()
        except KeyError:
            pass


    def getRoom(self, room_name):
        """
        Get room with a name, or None if not connected to this room.

        @type room: str
        @param room: room

        @rtype: Room
        @return: the room
        """
        return self.rooms.get(room_name.lower())


    def connect(self, *room_names):
        if self._future is None:
            try:
                self._future = self._loop.create_future()
            except AttributeError:
                self._future = asyncio.Future()

        for room_name in room_names:
            if hasattr(room_name, 'decode'):
                room_name = room_name.decode('utf-8')
            asyncio.ensure_future(self.joinRoom(room_name))

        return self._future


    def disconnect(self):
        tasks = []
        if self.pm:
            future = self.pm.disconnect()
            if future is not None:
                tasks.append(future)

        for room in self.rooms.values():
            future = room.disconnect()
            if future is not None:
                tasks.append(future)

        future = asyncio.gather(*tasks, loop=self._loop, return_exceptions=True)
        future.add_done_callback(self._future.set_result)

        result = self._future
        self._future = None
        return result


    ## Commands


    def enableBg(self):
        """Enable background if available."""
        self.user._mbg = True
        for room in self.rooms.values():
            room.setBgMode(1)


    def disableBg(self):
        """Disable background."""
        self.user._mbg = False
        for room in self.rooms.values():
            room.setBgMode(0)


    def enableRecording(self):
        """Enable recording if available."""
        self.user._mrec = True
        for room in self.rooms.values():
            room.setRecordingMode(1)


    def disableRecording(self):
        """Disable recording."""
        self.user._mrec = False
        for room in self.rooms.values():
            room.setRecordingMode(0)


    def setNameColor(self, rgb_hex):
        """
        Set name color.

        @type rgb_hex: str
        @param rgb_hex: a 3-char RGB hex code for the color
        """
        self.user.nameColor = rgb_hex


    def setFontColor(self, rgb_hex):
        """
        Set font color.

        @type rgb_hex: str
        @param rgb_hex: a 3-char RGB hex code for the color
        """
        self.user.fontColor = rgb_hex


    def setFontFace(self, face):
        """
        Set font face/family.

        @type face: str
        @param face: the font face
        """
        self.user.fontFace = face


    def setFontSize(self, size):
        """
        Set font size.

        @type size: int
        @param size: the font size (limited: 9 to 22)
        """
        if size < 9:
            size = 9
        if size > 22:
            size = 22
        self.user.fontSize = size


    ## Virtual methods


    @asyncio.coroutine
    def onInit(self):
        """Called on init."""
        pass


    @asyncio.coroutine
    def onConnect(self, room):
        """
        Called when connected to the room.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onReconnect(self, room):
        """
        Called when reconnected to the room.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onConnectFail(self, room):
        """
        Called when the connection failed.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onDisconnect(self, room):
        """
        Called when the client gets disconnected.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onLoginFail(self, room):
        """
        Called on login failure, disconnects after.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onFloodBan(self, room):
        """
        Called when either flood banned or flagged.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onFloodBanRepeat(self, room):
        """
        Called when trying to send something when floodbanned.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onFloodWarning(self, room):
        """
        Called when an overflow warning gets received.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onMessageDelete(self, room, user, message):
        """
        Called when a message gets deleted.

        @type room: Room
        @param room: room where the event occured
        @type user: User
        @param user: owner of deleted message
        @type message: Message
        @param message: message that got deleted
        """
        pass


    @asyncio.coroutine
    def onModChange(self, room):
        """
        Called when the moderator list changes.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onModAdd(self, room, user):
        """
        Called when a moderator gets added.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onModRemove(self, room, user):
        """
        Called when a moderator gets removed.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onMessage(self, room, user, message):
        """
        Called when a message gets received.

        @type room: Room
        @param room: room where the event occured
        @type user: User
        @param user: owner of message
        @type message: Message
        @param message: received message
        """
        pass


    @asyncio.coroutine
    def onHistoryMessage(self, room, user, message):
        """
        Called when a message gets received from history.

        @type room: Room
        @param room: room where the event occured
        @type user: User
        @param user: owner of message
        @type message: Message
        @param message: the message that got added
        """
        pass


    @asyncio.coroutine
    def onJoin(self, room, user):
        """
        Called when a user joins. Anonymous users get ignored here.

        @type room: Room
        @param room: room where the event occured
        @type user: User
        @param user: the user that has joined
        """
        pass


    @asyncio.coroutine
    def onLeave(self, room, user):
        """
        Called when a user leaves. Anonymous users get ignored here.

        @type room: Room
        @param room: room where the event occured
        @type user: User
        @param user: the user that has left
        """
        pass


    @asyncio.coroutine
    def onRaw(self, room, raw):
        """
        Called before any command parsing occurs.

        @type room: Room
        @param room: room where the event occured
        @type raw: str
        @param raw: raw command data
        """
        pass


    @asyncio.coroutine
    def onPing(self, room):
        """
        Called when a ping gets sent.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onUserCountChange(self, room):
        """
        Called when the user count changes.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onBan(self, room, user, target):
        """
        Called when a user gets banned.

        @type room: Room
        @param room: room where the event occured
        @type user: User
        @param user: user that banned someone
        @type target: User
        @param target: user that got banned
        """
        pass


    @asyncio.coroutine
    def onUnban(self, room, user, target):
        """
        Called when a user gets unbanned.

        @type room: Room
        @param room: room where the event occured
        @type user: User
        @param user: user that unbanned someone
        @type target: User
        @param target: user that got unbanned
        """
        pass


    @asyncio.coroutine
    def onBanlistUpdate(self, room):
        """
        Called when a banlist gets updated.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onUnBanlistUpdate(self, room):
        """
        Called when a unbanlist gets updated.

        @type room: Room
        @param room: room where the event occured
        """
        pass


    @asyncio.coroutine
    def onPMConnect(self, pm):
        """
        Called when connected to the pm

        @type pm: PM
        @param pm: the pm
        """
        pass


    @asyncio.coroutine
    def onAnonPMDisconnect(self, pm, user):
        """
        Called when disconnected from the pm

        @type pm: PM
        @param pm: the pm
        """
        pass


    @asyncio.coroutine
    def onPMDisconnect(self, pm):
        """
        Called when disconnected from the pm

        @type pm: PM
        @param pm: the pm
        """
        pass


    @asyncio.coroutine
    def onPMPing(self, pm):
        """
        Called when sending a ping to the pm

        @type pm: PM
        @param pm: the pm
        """
        pass


    @asyncio.coroutine
    def onPMMessage(self, pm, user, body):
        """
        Called when a message is received

        @type pm: PM
        @param pm: the pm
        @type user: User
        @param user: owner of message
        @type message: Message
        @param message: received message
        """
        pass


    @asyncio.coroutine
    def onPMOfflineMessage(self, pm, user, body):
        """
        Called when connected if a message is received while offline

        @type pm: PM
        @param pm: the pm
        @type user: User
        @param user: owner of message
        @type message: Message
        @param message: received message
        """
        pass


    @asyncio.coroutine
    def onPMContactlistReceive(self, pm):
        """
        Called when the contact list is received

        @type pm: PM
        @param pm: the pm
        """
        pass


    @asyncio.coroutine
    def onPMBlocklistReceive(self, pm):
        """
        Called when the block list is received

        @type pm: PM
        @param pm: the pm
        """
        pass


    @asyncio.coroutine
    def onPMContactAdd(self, pm, user):
        """
        Called when the contact added message is received

        @type pm: PM
        @param pm: the pm
        @type user: User
        @param user: the user that gotten added
        """
        pass


    @asyncio.coroutine
    def onPMContactRemove(self, pm, user):
        """
        Called when the contact remove message is received

        @type pm: PM
        @param pm: the pm
        @type user: User
        @param user: the user that gotten remove
        """
        pass


    @asyncio.coroutine
    def onPMBlock(self, pm, user):
        """
        Called when successfully block a user

        @type pm: PM
        @param pm: the pm
        @type user: User
        @param user: the user that gotten block
        """
        pass


    @asyncio.coroutine
    def onPMUnblock(self, pm, user):
        """
        Called when successfully unblock a user

        @type pm: PM
        @param pm: the pm
        @type user: User
        @param user: the user that gotten unblock
        """
        pass


    @asyncio.coroutine
    def onPMContactOnline(self, pm, user):
        """
        Called when a user from the contact come online

        @type pm: PM
        @param pm: the pm
        @type user: User
        @param user: the user that came online
        """
        pass


    @asyncio.coroutine
    def onPMContactOffline(self, pm, user):
        """
        Called when a user from the contact go offline

        @type pm: PM
        @param pm: the pm
        @type user: User
        @param user: the user that went offline
        """
        pass


    @asyncio.coroutine
    def onEventCalled(self, room, evt, *args, **kw):
        """
        Called on every room-based event.

        @type room: Room
        @param room: room where the event occured
        @type evt: str
        @param evt: the event
        """
        pass
