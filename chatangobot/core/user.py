"""Chat room users."""

_users = {}

class User(object):
    """Class that represents a user."""

    name = None
    puid = ''
    fontColor = '000'
    fontFace = '0'
    fontSize = 12
    nameColor = '000'

    _sids = None
    _msgs = None
    _mbg = False
    _mrec = False

    @property
    def sessionIds(self):
        return self._getSessionIds()


    @property
    def rooms(self):
        return self._sids.keys()


    @property
    def roomnames(self):
        return [room.name for room in self.rooms]


    @classmethod
    def create(cls, name, *args, **kwargs):
        if name is None:
            name = ''

        name = name.lower()
        user = _users.get(name)
        if not user:
            user = cls(name=name, *args, **kwargs)
            _users[name] = user
        return user


    def addSessionId(self, room, sid):
        if room not in self._sids:
            self._sids[room] = set()
        self._sids[room].add(sid)


    def removeSessionId(self, room, sid):
        try:
            self._sids[room].remove(sid)
            if len(self._sids[room]) == 0:
                del self._sids[room]
        except KeyError:
            pass


    def clearSessionIds(self, room):
        try:
            del self._sids[room]
        except KeyError:
            pass


    def hasSessionId(self, room, sid):
        try:
            return sid in self._sids[room]
        except KeyError:
            return False


    def _getSessionIds(self, room=None):
        if room:
            return self._sids.get(room, set())
        else:
            return set.union(*self._sids.values())


    def __repr__(self):
        return "<User: %s>" % self.name


    def __init__(self, name, **kw):
        self.name = name.lower()
        self._sids = {}
        self._msgs = []

        for attr, val in kw.items():
            if val is not None:
                setattr(self, attr, val)
