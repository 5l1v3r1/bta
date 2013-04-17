
from bta.miners import Miner
from bta.miners.tools import User, Group, Sid
import datetime

@Miner.register
class ListGroup(Miner):
    _name_ = "ListGroup"
    _desc_ = "List group membership"
    groups_already_saw={}

    @classmethod
    def create_arg_subparser(cls, parser):
        parser.add_argument("--match", help="Look only for groups matching REGEX", metavar="REGEX")
        parser.add_argument("--noresolve", help="Do not resolve SID", action="store_true")
        parser.add_argument("--verbose", help="Show also deleted users time and RID", action="store_true")

    def get_members_of(self, grpsid, recursive=False):
        group = self.datatable.find_one({'objectSid': grpsid})
        if not group:
            return set()
        members=set()
        for link in self.link_table.find({'link_DNT': group['RecId']}):
            deleted=False
            if 'link_deltime' in link and link['link_deltime'].year > 1970:
                deleted = link['link_deltime']
            row = self.datatable.find_one({'RecId': link['backlink_DNT']})
            if not row:
                members.add('[no entry %d found]' % link['backlink_DNT'])
                continue
            sid = row['objectSid']
            category = int(row['objectCategory'] )
            if category == self.categories.group:
                if sid not in self.groups_already_saw:
                    self.groups_already_saw[sid] = True
                    members.update(self.get_members_of(sid, recursive=True))
            elif category == self.categories.person:
                fromgrp = grpsid if recursive else ''
                membership = (row['objectSid'], deleted, fromgrp)
                members.add(membership)
            else:
                print '***** Unknown category (%d) for %s' % (category, sid)
        return members
        
    def getInfo_fromSid(self, sid):
        return self.datatable.find_one({'objectSid': sid})
    
    def find_dn(self, r):
        if not r:
            return ""
        cn = r.get("cn") or r.get("name")
        if cn is None or cn=="$ROOT_OBJECT$":
            return ""
        r2 = self.datatable.find_one({"RecId":r["ParentRecId"]})
        return self.find_dn(r2)+"."+cn

    def run(self, options, doc):
        def deleted_last(l):
            deleteditems=[]
            for i in l:
                if not i[1]:
                    yield i
                else:
                    deleteditems.append(i)
            for i in deleteditems:
                yield i
                
        match = None
        
        doc.add("List of groups matching [%s]" % options.match)
        if options.match:
            match = {"$and": [{'objectCategory': str(self.categories.group)},
                              {"$or": [ { "name": { "$regex": options.match } },
                                       { "objectSid": { "$regex": options.match } }
                                     ]}]
            }

        groups={}
        for group in self.datatable.find(match):
            groups[group['objectSid']] = set()
            groups[group['objectSid']] = self.get_members_of(group['objectSid'])

        headers=['User', 'Deletion', 'Flags', 'Recursive']
        
        listemptyGroup=[]
        for groupSid,membership in groups.items():
            if len(membership) == 0: 
                listemptyGroup.append(groupSid)
                continue
                
            info = self.getInfo_fromSid(groupSid)
            name = info['cn']
            guid = info['objectGUID']
            
            sec = doc.create_subsection("Group %s" % name)
            sec.add("sid = %s" % groupSid)
            sec.add("guid= %s" % guid)
            sec.add("cn  = %s" % self.find_dn(info))
            table = sec.create_table("Members of %s" % name)
            table.add(headers)
            table.add()
            for sid,deleted,fromgrp in deleted_last(membership):
                sidobj = Sid(self.datatable, objectSid=sid, verbose=options.verbose)
                member = str(sidobj)
                if fromgrp:
                    fromgrp = Sid(self.datatable, objectSid=fromgrp)
                flags = sidobj.getUserAccountControl()
                table.add((member, deleted or '', flags, fromgrp))
            table.finished()
            sec.finished()
        
        if len(listemptyGroup) > 0:
            headers=['Group', 'SID', 'Guid']
            table = doc.create_table("Empty groups")
            table.add(headers)
            table.add()
            for groupSid in listemptyGroup:
                info = self.getInfo_fromSid(groupSid)
                name = info['cn']
                guid = info['objectGUID']
                table.add((name, groupSid, guid))
            table.finished()
    
    def assert_consistency(self):
        Miner.assert_consistency(self)
        self.assert_field_type(self.datatable, "objectSid", str, unicode)
        self.assert_field_type(self.datatable, "RecId", int)
        self.assert_field_type(self.datatable, "ParentRecId", int)
        self.assert_field_type(self.datatable, "objectCategory", str, unicode)
        self.assert_field_type(self.datatable, "cn", str, unicode)
        self.assert_field_type(self.datatable, "name", str, unicode)
        self.assert_field_type(self.datatable, "objectGUID", str, unicode)
        self.assert_field_type(self.sd_table, "link_DNT", int)
        self.assert_field_type(self.sd_table, "link_deltime", datetime.datetime)
        self.assert_field_type(self.sd_table, "backlink_DNT", int)
