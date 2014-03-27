#! /usr/bin/env python

# This file is part of the BTA toolset
# (c) EADS CERT and EADS Innovation Works

import bta.backend.mongo
import bta.dblog
import tools.registry
import logging
log = logging.getLogger("bta.postprocessing")


class PostProcRegistry(tools.registry.Registry):
    pass

class PostProcessing(object):
    def __init__(self, options):
        self.options = options
        self.backend = options.backend
        self.dt = self.backend.open_table("datatable")

    @classmethod
    def list_post_processors(cls):
        return list(PostProcRegistry.iterkeys())

    def post_process_all(self):
        alln = self.list_post_processors()
        done=set()
        while alln:
            k = alln.pop(0)
            dep = PostProcRegistry.get(k).get("depends",set())
            if dep.issubset(done):
                done.add(k)
                self.post_process_one(k)
            else:
                alln.append(k)

    def post_process_one(self, name):
        log.info("Post-processing: %s" % name)
        self.options.dblog.update_entry("Start Post-processor: %s" % name)
        proc = getattr(self, name)
        proc()
        self.options.dblog.update_entry("End Post-processor: %s" % name)

    @PostProcRegistry.register()
    def category(self):
        category = self.options.backend.open_table("category")
        category.create()
        category.create_index("id")
        category.create_index("name")

        idSchemaRec = self.dt.find_one({"cn": "Class-Schema"})
        if idSchemaRec is None:
            log.warning("No schema id found in datatable for category post processing")
            return
        idSchema = idSchemaRec['DNT_col']
        for r in self.dt.find({"objectCategory": idSchema}):
            category.insert({"id":r["DNT_col"], "name":r["cn"]})

    @PostProcRegistry.register()
    def rightsGuids(self):
        guid = self.options.backend.open_table("guid")
        guid.create()
        guid.create_index("id")
        guid.create_index("name")
        # guid for shema
        for id in self.dt.find({"schemaIDGUID": {"$exists": 1}}):
            guid.insert({"id":id["schemaIDGUID"].lower(), "name":id["name"]})
        # guid for object
        for id in self.dt.find({"objectGUID": {"$exists": 1}}):
            guid.insert({"id":id["objectGUID"].lower(), "name":id["name"]})
        #guid for rights
        for id in self.dt.find({"rightsGuid": {"$exists": 1}}):
            guid.insert({"id":id["rightsGuid"].lower(), "name":id["name"]})
        #ObjectId
        for id in self.dt.find({"objectSid": {"$exists": 1}}):
            guid.insert({"id":id["objectSid"].lower(), "name":id["name"]})
        #
        for id in self.dt.find({"attributeID": {"$exists": 1}}):
            guid.insert({"id":id["attributeID"].lower(), "name":id["name"]})

    @PostProcRegistry.register(depends={"category"})
    def domains(self):
        domains = self.options.backend.open_table("domains")
        domains.create()
        domains.create_index("domain")
        domains.create_index("sid")

        ct = self.options.backend.open_table("category")
        domRec = ct.find_one({"name": "Domain-DNS"})
        if domRec is None:
            log.warning("No domain dns found in datatable for domains post processing")
            return
        dom = domRec["id"]
        def find_dn(r):
            if not r:
                return ""
            cn = r.get("cn") or r.get("name")
            if cn is None or cn=="$ROOT_OBJECT$":
                return ""
            r2 = self.dt.find_one({"DNT_col":r.get("PDNT_col")})
            if not r2:
                return ""
            return find_dn(r2)+"."+cn


        for r in self.dt.find({"objectCategory":dom, "objectSid":{"$exists":True}}):
            domains.insert({"domain":find_dn(r), "sid":r["objectSid"]})

    @PostProcRegistry.register()
    def dnames(self):
        dnames = self.options.backend.open_table("dnames")
        dnames.create()
        dnames.create_index("name")
        dnames.create_index("DNT_col")
        dnames.create_index("DName")

        error = 0
        for r in self.dt.find({"Ancestors_col":{"$exists":True}}):
            dn=list()
            for p in r["Ancestors_col"]:
                try:
                    p=self.dt.find({"DNT_col":p}).limit(1)[0]
                except:
                    error += 1
                    continue
                    if p.get('name')=="$ROOT_OBJECT$\x00":
                        continue
                    if p.get('dc'):
                        dn.append("DC=%s"%p['name'])
                    elif p.get('cn'):
                        dn.append("CN=%s"%p['name'])
                    elif p.get('name'):
                        dn.append("DC=%s"%p['name'])
            dn.reverse()
            dnames.insert({"name":r["name"], "DNT_col":r["DNT_col"], "DName":",".join(dn)})
        print "NB ERRORS : %r" % error


    @PostProcRegistry.register()
    def usersid(self):
        usersid = self.options.backend.open_table("usersid")
        usersid.create()
        usersid.create_index("name")
        usersid.create_index("sid")
        usersid.create_index("account")

        ct = self.options.backend.open_table("category")
        persRec = ct.find_one({"name": "Person"})
        if persRec is None:
            log.warning("No name=Person entry found in datatable for usersid post processing")
            return
        pers = persRec['id']
        for r in self.dt.find({"objectCategory":pers, "objectSid":{"$exists":True}}):
            usersid.insert({"name":r["name"], "account":r["sAMAccountName"], "sid": r["objectSid"]})


def main():
    import optparse
    parser = optparse.OptionParser()

    parser.add_option("-C", dest="connection",
                      help="Backend connection string. Ex: 'dbname=test user=john' for PostgreSQL or '[ip]:[port]:dbname' for mongo)", metavar="CNX")
    parser.add_option("-B", dest="backend_class", default="mongo",
                      help="database backend (amongst: %s)" % (", ".join(bta.backend.Backend.backends.keys())))

    parser.add_option("--only", dest="only", metavar="POSTPROC",
                      help="Only run POSTPROC (amongst %s)" % (", ".join(PostProcessing.list_post_processors())))

    parser.add_option("--overwrite", dest="overwrite", action="store_true",
                      help="Delete tables that already exist in db")

    options, args = parser.parse_args()

    if options.connection is None:
        parser.error("Missing connection string (-C)")

    backend_class = bta.backend.Backend.get_backend(options.backend_class)
    options.backend = backend_class(options)

    with bta.dblog.DBLogEntry.dblog_context(options.backend) as options.dblog:

        pp = PostProcessing(options)
        if options.only:
            pp.post_process_one(options.only)
        else:
            pp.post_process_all()
        options.backend.commit()


if __name__ == "__main__":
    main()
