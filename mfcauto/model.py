from .event_emitter import EventEmitter
from .constants import FCTYPE, FCOPT, STATE, FCVIDEO

knownmodels = dict()

class Model(EventEmitter):
    def __init__(self, uid):
        self.uid = uid
        self.nm = None
        self.tags = None
        self.knownsessions = dict()
        super().__init__()
    @staticmethod
    def get_model(uid, create=True):
        """Retrieves or creates a model"""
        if create:
            return knownmodels.setdefault(uid, Model(uid))
        else:
            return None if uid not in knownmodels else knownmodels[uid]
    @staticmethod
    def find_models(func):
        return [m for m in knownmodels.values() if func(m)]
    @staticmethod
    def _default_session(uid):
        return {"sid":0, "uid":uid, "vs": STATE.Offline.value, "rc": 0}
    @property
    def bestsessionid(self):
        sessionidtouse = 0
        foundmodelsoftware = False
        for (sessionid, sessionobj) in self.knownsessions.items():
            if sessionobj.setdefault("vs", STATE.Offline.value) == STATE.Offline.value:
                continue
            usethis = False
            if sessionobj.setdefault("model_sw", False):
                if foundmodelsoftware:
                    if sessionid > sessionidtouse:
                        usethis = True
                else:
                    foundmodelsoftware = True
                    usethis = True
            elif (not foundmodelsoftware) and sessionid > sessionidtouse:
                usethis = True
            if usethis:
                sessionidtouse = sessionid
        return sessionidtouse
    @property
    def bestsession(self):
        return self.knownsessions.setdefault(self.bestsessionid, Model._default_session(self.uid))
    @property
    def in_true_private(self):
        """True if the model is in a true private, False if not"""
        if self.bestsession["vs"] == STATE.Private.value and "truepvt" in self.bestsession and self.bestsession["truepvt"]:
            return True
        else:
            return False
    def mergepacket(self, packet):
        assert self.uid != -500, "We should never merge for the fake 'All' model"
        assert type(packet.smessage) == dict, (packet.fctype, type(packet.smessage), packet.smessage)

        fctype = packet.fctype
        previoussession = self.bestsession

        if packet.fctype == FCTYPE.TAGS:
            currentsessionid = previoussession["sid"]
        else:
            currentsessionid = 0 if not "sid" in packet.smessage else packet.smessage["sid"]
        currentsession = self.knownsessions.setdefault(currentsessionid, Model._default_session(self.uid))

        callbackstack = []

        if fctype == FCTYPE.TAGS:
            tagPayload = packet.smessage
            assert self.uid in tagPayload
            previousTags = self.tags.copy() if self.tags != None else None
            self.tags = (self.tags if self.tags != None else [])+tagPayload[self.uid]
            callbackstack.append(("tags",self,previousTags,self.tags))
        else:
            payload = packet.smessage
            assert type(payload)==dict and ("lv" not in payload or payload["lv"]==4) and (("uid" in payload and self.uid == payload["uid"]) or packet.aboutModel.uid == self.uid)
            for key in payload:
                if key == "u" or key == "m" or key == "s":
                    for key2 in payload[key]:
                        callbackstack.append((key2, self, None if not key2 in previoussession else previoussession[key2], payload[key][key2]))
                        currentsession[key2] = payload[key][key2]
                        if key == "m" and key2 == "flags":
                            #@BUGBUG - I'm just realizing that the Node version doesn't fire callbacks for individual flag changes... @TODO need to do it here too...
                            flags = payload[key][key2]
                            currentsession["truepvt"] = bool(flags & FCOPT.TRUEPVT.value)
                            currentsession["guests_muted"] = bool(flags & FCOPT.GUESTMUTE.value)
                            currentsession["basics_muted"] = bool(flags & FCOPT.BASICMUTE.value)
                            currentsession["model_sw"] = bool(flags & FCOPT.MODELSW.value)
                            #@TODO - Build a running set of leaf keys and assert that we've never seen this leaf key before, in other words, validate that this whole dict flattening approach is not losing information
                else:
                    callbackstack.append((key, self, None if not key in previoussession else previoussession[key], payload[key]))
                    currentsession[key] = payload[key]

        if currentsession["sid"] != previoussession["sid"]:
            previouskeys = set(previoussession.keys())
            currentkeys = set(currentsession.keys())
            for key in (previouskeys - currentkeys):
                callbackstack.append((key, self, previoussession[key], None))

        if self.bestsessionid == currentsession["sid"] or (self.bestsessionid == 0 and currentsession["sid"] != 0):
            if "nm" in self.bestsession and self.bestsession["nm"] != self.nm:
                self.nm = self.bestsession["nm"]
            for (prop, model, before, after) in callbackstack:
                if before != after:
                    self.emit(prop, model, before, after)
                    Model.All.emit(prop, model, before, after)
            self.emit("ANY", self, packet)
            Model.All.emit("ANY", self, packet)
            #self.processWhens(packet) #@TODO - @BUGBUG
        self._purgeoldsessions()
    def _purgeoldsessions(self):
        for key in set(self.knownsessions.keys()):
            if "vs" not in self.knownsessions[key] or FCVIDEO(self.knownsessions[key]["vs"])==FCVIDEO.OFFLINE:
                del self.knownsessions[key]
    def when(self, condition, ontre, onfalseaftertrue):
        pass #@TODO

#@TODO - Not sure if this is the best design, but for now we're faking a model to represent all models
#this buys us some nice things because model is already an EventEmitter...I guess.  Note that we can't have
#exactly the same design as NodeJS because Python does not allow both instance and static class members
#with the same name, so I can't have both Model.on("something") and Model.get_model(3).on("Something").
#I toyed with putting a .on at the module level, but that feels weird.  So for now the alternative for
#the static "All" variant is Model.All.on("something")
Model.All = Model.get_model(-500)
__all__ = ["Model"]
