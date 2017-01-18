class Message(object):
    """Class that represents a message."""

    msgid = None
    time = None
    user = None
    body = None
    room = None
    raw = ''
    ip = None
    unid = ''
    nameColor = '000'
    fontSize = 12
    fontFace = '0'
    fontColor = '000'

    @property
    def id(self):
        return self.msgid


    def attach(self, room, msgid):
        """
        Attach the Message to a message id.

        @type msgid: str
        @param msgid: message id
        """
        if self.msgid is None:
            self.room = room
            self.msgid = msgid
            self.room._msgs[msgid] = self


    def detach(self):
        """Detach the Message."""

        if self.msgid is not None and self.msgid in self.room._msgs:
            del self.room._msgs[self.msgid]
            self.msgid = None


    def delete(self):
        self.room.deleteMessage(self)


    def __init__(self, **kw):
        for attr, val in kw.items():
            if val is not None:
                setattr(self, attr, val)
