===
BTA
===

Installing BTA
==============

Dependencies:

* mongodb
* libesedb http://code.google.com/p/libesedb/

Installation:

* ``python setup.py install`` 

Active Directory Analysis
=========================

Goal:

* Clean an AD or an AD forest, looking for

  + bad practices
  + forgotten entries
  + backdoors
  + recompromissions


* BTA is an operationnal tool, ought to be

  + deterministic, reliable
  + running a well established procedure


Protocol
========

Audit steps:

#. Extract [#SSTIC]_ the``ntds.dit`` file
#. Import the``ntds.dit`` file in a database
#. Look for control points in the database

.. [#SSTIC] https://www.sstic.org/2012/presentation/audit_ace_active_directory/

Importing
=========

* ``ntds.dit`` is unusable as-is. 
* one ``ntds.dit`` is imported into one MongoDB *database*
* ability to import several ``ntds.dit`` in parallel

Examples:

.. code-block ::

 ntds2db -C ::mydb /path/to/ntds.dit
 ntds2db /path/to/*.dit  --multi             \
   --C-from-filename                         \ 
      "::%s" "basename rmext 'DB' swap plus"


Analysing
=========

* Querying the database

  + analysing control points of a database: **btaminer**
  + analysing differences between 2 bases: **btadiff**


Analysing control points
========================

* miners cristalize expertise

  + list of admin accounts
  + list of accounts with delegations
  + list of accounts with password errors
  + list of various timelines

.. code-block ::

  btaminer -t ReST -C ::AD1 Schema --timelineCS created

  Analysis by miner [Schema]
  ==========================

  +---------------+-----------------------+
  | Date          | Affected class schema |
  +===============+=======================+
  | 2009-02-11 18 | 234                   |
  | 2011-12-20 00 | 267                   |
  | 2011-12-22 14 | 3                     |
  | 2011-12-23 18 | 46                    |
  +---------------+-----------------------+



Analysing differences
=====================

* diff

  + diff (naive for the moment) between 2 imports at different moments
  + noise filtering

.. code-block ::

  $ btadiff --CA ::ADclean --CB ::ADbackdoor --ignore-defaults
  ===============
  Starting diffing sd_table
  ---------------
  AB,101: [] *sd_refcount['14'=>'15']
  AB,108: [] *sd_refcount['39'=>'41']
  A ,229: []
  A ,372: []
  AB,423: [] *sd_refcount['3'=>'2']
   B,424: []
   B,425: []
   B,428: []
  ---------------
  Table [sd_table]: 160 records checked, 2 disappeared, 3 appeared, 3 changed
  ===============
  [...]


.. code-block ::

  ===============
  Starting diffing datatable
  ---------------
  AB,3586: [DC001] *logonCount['116'=>'117'], *lastLogon['130052518207794051L'=>'130052535716737649L']
  AB,3639: [RID Set] *rIDNextRID['1153'=>'1154']
  AB,8784: [A:[gc]/B:[gc  DEL:346bf199-8567-4375-ac15-79ec4b42b270]] +isDeleted, 
           *name["u'gc'"=>"u'gc\\nDEL:346bf199-8"], *dc["u'gc'"=>"u'gc\\nDEL:346bf199-8"]
  AB,8785: [A:[DomainDnsZones]/B:[DomainDnsZones  DEL:58b2962b-708c-4c93-99ff-0b7e163131f9]]
           +isDeleted, *name["u'DomainDnsZones'"=>"u'DomainDnsZones\\nDE"], 
           *dc["u'DomainDnsZones'"=>"u'DomainDnsZones\\nDE"]
  AB,8786: [A:[ForestDnsZones]/B:[ForestDnsZones  DEL:87f7d8a2-4d05-48d0-8283-9ab084584470]]
           +isDeleted, *name["u'ForestDnsZones'"=>"u'ForestDnsZones\\nDE"], 
           *dc["u'ForestDnsZones'"=>"u'ForestDnsZones\\nDE"]
   B,8789: [snorky insomnihack]
   B,8790: [gc]
   B,8791: [DomainDnsZones]
   B,8792: [ForestDnsZones]
  ---------------
  Table [datatable]: 7636 records checked, 0 disappeared, 4 appeared, 5 changed
  ===============
  



Other features
==============

* can give reports in different formats:

  + dump live
  + documents ReST
  + zip de CSV

* audit log of writings in a database
* table consistency checks before *mining*


