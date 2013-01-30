
import pymongo
import struct
from datetime import datetime
from ntds.normalization import TypeFactory,Normalizer
from ntds.backend import Backend
import ntds.sd
import ntds.tools

class MongoNormalizer(Normalizer):
    def empty(self, val):
        return not bool(val)

class MongoTextNormalizer(MongoNormalizer):
    pass
    
class MongoIntNormalizer(MongoNormalizer):
    def normal(self, val):
        return int(val)

class MongoTimestampNormalizer(MongoNormalizer):
    def normal(self, val):
        try:
            ts = int(val)-11644473600 # adjust windows timestamp (from 01/01/1601) to unix epoch
            return datetime.fromtimestamp(ts)
        except ValueError:
            return datetime.fromtimestamp(0)

class MongoNTSecDesc(MongoNormalizer):
    def normal(self, val):
        return struct.unpack("Q", val.decode("hex"))[0]

class MongoSID(MongoNormalizer):
    def normal(self, val):
        try:
            val = val.strip().decode("hex")
        except:
            return val
        if val:
            return ntds.tools.decode_sid(val)
        return None
    
class MongoGUID(MongoNormalizer):
    def normal(self, val):
        val = val.strip().decode("hex")
        if val:
            return ntds.tools.decode_guid(val)
        return None
    
class MongoSecurityDescriptor(MongoNormalizer):
    def normal(self, val):
        val = val.strip().decode("hex")
        if val:
            return ntds.sd.sd_to_json(val)
        return None
    

class MongoTypeFactory(TypeFactory):
    def Text(self):
        return MongoTextNormalizer()
    def Int(self):
        return MongoIntNormalizer()
    def Timestamp(self):
        return MongoTimestampNormalizer()
    def NTSecDesc(self):
        return MongoNTSecDesc()
    def SID(self):
        return MongoSID()
    def GUID(self):
        return MongoGUID()
    def SecurityDescriptor(self):
        return MongoSecurityDescriptor()




@Backend.register("mongo")
class Mongo(Backend):
    def __init__(self, options):
        Backend.__init__(self, options)
        self.colname = options.tablename
        ip,port,self.dbname,_ = (options.connection+":::").split(":",3)
        ip = ip if ip else "127.0.0.1"
        port = int(port) if port else 27017
        self.cnxstr = (ip,port)
        self.cnx = pymongo.Connection(*self.cnxstr)
        self.db = self.cnx[self.dbname]
        self.typefactory = MongoTypeFactory()
    def create_table(self):
        self.fields = [(x[0], getattr(self.typefactory,x[2])())  for x in self.columns]
        self.col = self.db.create_collection(self.colname)
        for x in self.columns:
            if x[3]:
                self.col.create_index(x[0])
    def open_table(self):
        self.col = self.db[self.colname]
        return self.col

    def insert(self, values):
        d = dict([(name,norm.normal(v)) for (name,norm),v in zip(self.fields, values) if not norm.empty(v)])
        id = self.col.insert(d)
    def count(self):
        return self.col.count()
    
