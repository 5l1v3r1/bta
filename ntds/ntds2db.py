#! /usr/bin/env python

import sys,os
import itertools

import ntds.backend.mongo
import diskcache

def win2epoch(x):
    return x-11644473600

def dbsanecolname(x):
    return x.replace("-","_")


class ESEColumn(object):
    def __init__(self, name, attname, type_, index=False):
        self.name = name
        self.attname = attname
        self.type = type_
        self.index = index

class ESETable(object):
    _columns_ = []  # db col name # dt name # db type # index?
    _tablename_ = None

    def __init__(self, options):
        self.options = options
        self.backend = options.backend
        filename = getattr(options, self._tablename_)
        self.fname = os.path.join(options.dirname, filename)
    
    def resolve_unknown_columns(self, columns, fmt, unk_col):
        return columns, fmt, unk_col


    def identify_columns(self):
        print "Parsing header line"
        columns = self._columns_[:]
        f = open(self.fname)
        head = f.readline()
        nrec = len(columns)
        fmt = [None]*nrec
        h2pos = dict([(c.attname,(i,c.type)) for i,c in enumerate(columns)])
        
        split_head = head.strip().split("\t")
        unk_col = []
        for i,h in enumerate(split_head):
            if h in h2pos:
                pos,typ = h2pos[h]
                fmt[pos] = i,typ
            else:
                unk_col.append((i,h))
        
        if None in fmt:
            raise Exception("Did not find some headers: fmt=%r" % fmt)

        columns, fmt, unk_col = self.resolve_unknown_columns(columns, fmt, unk_col)

        if unk_col:
            print "%i unresolved cols" % len(unk_col)
            for pos,att in unk_col:
                typ = "Text"
                columns.append(ESEColumn(dbsanecolname(att), att, typ))
                fmt.append((pos, typ))
        else:
            print "All cols resolved"


        return columns, fmt
    
    def extract(self, fmt, line):
        sl = line.split("\t")
    #    return [typ.to_db(sl[i]) for i,typ in fmt]
        return [sl[i] for i,typ in fmt]
    
    def parse_file(self, table, fmt):
        f = open(self.fname)
        head = f.readline()

        print "Parsing table lines"
        i = 0
        try:
            while True:
                l = f.readline()
                if not l:
                    break
                i+=1
                if i%100 == 0:
                    sys.stderr.write("         \r%i %i" % (i, table.count()))
                values = self.extract(fmt, l)
                table.insert_fields(values)
        except KeyboardInterrupt:
            print "\nInterrupted by user"
        else:
            print "\ndone"

    def create(self):
        columns, fmt = self.identify_columns()

        metatable = self.backend.open_table(self._tablename_+"_meta")

        table = self.backend.open_table(self._tablename_)
        table.create(columns)
        self.parse_file(table, fmt)

        for col in columns:
            c = table.find({col.name:{"$exists":True}}).count()
            metatable.insert(dict(name=col.name, attname=col.attname, type=col.type, count=c))




class SDTable(ESETable):
    _tablename_ = "sdtable"
    _columns_ = [
        ESEColumn("id", "sd_id", "Int", True),
        ESEColumn("hash", "sd_hash", "Text", True),
        ESEColumn("refcount", "sd_refcount", "Int", True),
        ESEColumn("value", "sd_value", "SecurityDescriptor", False)
        ]

class Datatable(ESETable):
    _tablename_ = "datatable"
    _columns_ = [
        ESEColumn("RecId", "DNT_col", "Int", True),
        ESEColumn("ParentRecId", "PDNT_col", "Int", True),
        ESEColumn("RecordTime", "time_col", "Timestamp", True),
        ESEColumn("lDAPDisplayName", "ATTm131532", "Text", False),
        ESEColumn("attributeID", "ATTc131102", "Int", False),
        ESEColumn("attributeSyntax", "ATTc131104", "Text", False),
        ESEColumn("nTSecurityDescriptor", "ATTp131353", "NTSecDesc", True),
        ESEColumn("msExchMailboxSecurityDescriptor", "ATTp415105104", "NTSecDesc", True),
        ESEColumn("objectSid", "ATTr589970", "SID", True),
        ESEColumn("objectGUID", "ATTk589826", "GUID", True),
        ESEColumn("schemaIDGUID", "ATTk589972", "GUID", True),
#       ESEColumn("attributeTypes", "ATTc1572869", "Text", False),
        ]


    ATTRIBUTE_ID="ATTc131102"
    ATTRIBUTE_SYNTAX="ATTc131104"
    LDAP_DISPLAY_NAME="ATTm131532"


    attsyntax2type = {
    #    524290: BigInt, #ID
        524293: "Text", #printable name
        524298: "Text", # GUID
    #    524297: "Int",
        524299: "Timestamp", #timestamp
        524300: "Text", #names
        524304: "Timestamp", # time
    }

    def syntax_to_type(self, s):
        return self.attsyntax2type.get(s, "Text")

    def resolve_unknown_columns(self, columns, fmt, unk_col):
        print "Resolving %i unknown columns" % len(unk_col)
        f = open(self.fname)
        head = f.readline()
        split_head = head.strip().split("\t")
        unkcd = dict([(h[4:],(i,h)) for i,h in unk_col if h.startswith("ATT")])
        aid = split_head.index(self.ATTRIBUTE_ID)
        asy = split_head.index(self.ATTRIBUTE_SYNTAX)
        ldn = split_head.index(self.LDAP_DISPLAY_NAME)
        if aid < 0 or asy < 0 or ldn < 0:
            raise Exception("Did not find %s or %s or %s" % (self.ATTRIBUTE_ID, self.ATTRIBUTE_SYNTAX, self.LDAP_DISPLAY_NAME))
        while unkcd:
            l = f.readline()
            if not l:
                break
            sl = l.strip().split("\t")
            pos,att = unkcd.pop(sl[aid], (None,None))
            if att is not None:
                typ = self.syntax_to_type(int(sl[asy]))
                nam = dbsanecolname(sl[ldn])
                columns.append(ESEColumn(nam, att, typ, index=False))
                fmt.append((pos,typ))

        return columns, fmt, unkcd.values()



def main():
    import optparse
    parser = optparse.OptionParser()
    
    parser.add_option("-C", dest="connection",
                      help="Backend connection string. Ex: 'dbname=test user=john' for PostgreSQL or '[ip]:[port]:dbname' for mongo)", metavar="CNX")
    parser.add_option("-B", dest="backend_class", default="mongo",
                      help="database backend (amongst: %s)" % (", ".join(ntds.backend.Backend.backends.keys())))

    
    parser.add_option("--only", dest="only", default=None,
                      help="Restrict import to TABLENAME", metavar="TABLENAME")
    
    parser.add_option("--dirname", dest="dirname", default="",
                      help="Look for extracted table files in DIR", metavar="DIR")
    parser.add_option("--datatable", dest="datatable", default="datatable.3",
                      help="Read datatable from FILENAME", metavar="FILENAME")
    parser.add_option("--sdtable", dest="sdtable", default="sd_table.8",
                      help="Read sd_table from FILENAME", metavar="FILENAME")

    options, args = parser.parse_args()

    
    if options.connection is None:
        parser.error("Missing connection string (-C)")
    

    backend_class = ntds.backend.Backend.get_backend(options.backend_class)
    options.backend = backend_class(options)
    
    if options.only.lower() in [None,"sdtable","sd_table", "sd"]:
        sd = SDTable(options)
        sd.create()
    if options.only.lower() in [None,"datatable","data"]:
        dt = Datatable(options)
        dt.create()

    options.backend.commit()
    

if __name__ == "__main__":
    main()
