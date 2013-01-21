#! /usr/bin/env python

import time
import ntds.backend.mongo

def win2time(x):
    return time.ctime(int(x)-11644473600)

def do_timeline(options):
    col = options.db.open_table()

    
    def find_dn(r):
        cn = r.get("cn") or r.get("name")
        if cn is None or cn=="$ROOT_OBJECT$":
            return ""
        r2 = col.find_one({"RecId":r["ParentRecId"]})
        return find_dn(r2)+"."+cn

    c = col.find({"cn":options.cn})
    for r in c:
        print "=>",r["cn"],find_dn(r)


def main():
    import optparse
    parser = optparse.OptionParser()
    
    parser.add_option("-C", dest="connection",
                      help="PostGreSQL connection string. Ex: 'dbname=test user=john' for PostgreSQL or '[ip]:[port]:dbname' for mongo)", metavar="CNX")
    parser.add_option("-t", dest="tablename",
                      help="table name to create in database", metavar="TABLENAME")
    parser.add_option("--cn", dest="cn",
                      help="look for objects whose common name is CN", metavar="CN")
    parser.add_option("-B", dest="backend", default="mongo",
                      help="database backend (amongst: %s)" % (", ".join(ntds.backend.Backend.backends.keys())))

    options, args = parser.parse_args()

    
    if options.tablename is None:
        parser.error("Missing table name (-t)")
    if options.connection is None:
        parser.error("Missing connection string (-C)")

    db_backend = ntds.backend.Backend.get_backend(options.backend)
    options.columns = []
    options.db = db_backend(options)

    do_timeline(options)

if __name__ == "__main__":
    main()
