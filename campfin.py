"""This python utility imports bulk data from the Center for Responsive Politics into a MySQL database, sparing the user the repetitious work of importing, naming fields and properly configuring tables. It is based in part on code from the Sunlight Foundation's Jeremy Carbaugh.

It includes a few auxillary tables and fields not part of CRP's official bulk download, but does not harness Personal Financial Disclosures. When you run this script repeatedly, it will check the updated dates and only re-download if the data has been modified. Even so, you are encouraged to download bulk files, which can be quite large, at non-peak-traffic times. Because some table schemas have changed over cycles, the utility has been tested only for recent cycles: 2008 and 2010. 

Register for a 'MyOpenSecrets' account at opensecrets.org and supply your login info below. Create a mysql database on your computer and provide the host, user, password and database name. Also set the 'cycles' list for the two-digit representation of the election cycle you want to download. Then run python grab-crp.py. 

Windows users can connect to this database in Microsoft Access if you prefer by setting up an ODBC connection. (Start-Control Panel-Administrative Tools-Data Sources (ODBC)). After you've set up an ODBC connection using the MySQL ODBC Connector, go to the External Data tab in Access, click 'other' and 'ODBC,' and connect to the tables. 

Luke Rosiak
"""

import MySQLdb
import sys
import csv
import datetime
import logging
import os
import re
import urllib, urllib2

from credentials import *


class CampFinDownloader(object):
    
    def __init__(self,cycles=CYCLES):
        
        self.CYCLES = cycles
        self.db = MySQLdb.connect(host=MYSQL_HOST, user=MYSQL_USER, passwd=MYSQL_PASSWORD,db=MYSQL_DB)
        self.cursor = self.db.cursor()
        self.dest_path = 'raw'


    def createtables(self):
        queries = [
                """CREATE TABLE IF NOT EXISTS crp_cmtes (
	            Cycle char(4) NOT NULL,
	            CmteID char(9) NOT NULL,
	            PACShort varchar(40) NULL,
	            Affiliate varchar(40) NULL,
	            UltOrg varchar(40) NULL,
	            RecipID char(9) NULL,
	            RecipCode char(2) NULL,
	            FECCandID char(9) NULL,
	            Party char(1) NULL,
	            PrimCode char(5) NULL,
	            Src char(10) NULL,
                Sens char(1) NULL,
	            Frgn int NOT NULL,
	            Actve int NULL,
                PRIMARY KEY (Cycle, CmteID)
                );""",
                """CREATE TABLE IF NOT EXISTS crp_cands(
	            Cycle char(4) NOT NULL,
	            FECCandID char(9) NOT NULL,
	            CID char(9) NOT NULL,
	            FirstLastP varchar(40) NULL,
	            Party char(1) NULL,
	            DistIDRunFor char(4) NULL,
	            DistIDCurr char(4) NULL,
	            CurrCand char(1) NULL,
	            CycleCand char(1) NULL,
	            CRPICO char(1) NULL,
	            RecipCode char(2) NULL,
	            NoPacs char(1) NULL,
                PRIMARY KEY (Cycle, FECCandID),
                INDEX (CID)
                );""",  
                """CREATE TABLE IF NOT EXISTS crp_indivs(
	            Cycle char(4) NOT NULL,
	            FECTransID char(7) NOT NULL,
	            ContribID char(12) NULL,
	            Contrib varchar(34) NULL,
                RecipID char(9) NULL,
	            Orgname varchar(40) NULL,
	            UltOrg varchar(40) NULL,
	            RealCode char(5) NULL,
	            Date date NOT NULL,
	            Amount int NULL,
                street varchar(20) NULL,
	            City varchar (18) NULL,
	            State char (2) NULL,
                Zip char (5) NULL,
	            Recipcode char (2) NULL,
	            Type char(3) NULL,
	            CmteID char(9) NULL,
	            OtherID char(9) NULL,
	            Gender char(1) NULL,
	            FECOccEmp varchar(35) NULL,
                Microfilm varchar(11) NULL,
	            Occ_EF varchar(38) NULL,
	            Emp_EF varchar(38) NULL,
                Src char(5) NULL,
                lastname varchar(20),
                first varchar(10),
                first3 varchar(3),
                INDEX (Orgname),
                PRIMARY KEY (Cycle, FECTransID)
                );""",
                """CREATE TABLE IF NOT EXISTS crp_pacs (
	            Cycle char(4) NOT NULL,
	            FECRecNo char(7)  NOT NULL,
                PACID char(9)  NOT NULL,
	            CID char(9)  NULL,
	            Amount int,
	            Date datetime NULL,
	            RealCode char(5)  NULL,
	            Type char(3)  NULL,
	            DI char(1)  NOT NULL,
	            FECCandID char(9)  NULL,
                INDEX (Cycle, PACID)
                );""",
                """CREATE TABLE IF NOT EXISTS crp_pac_other (
	            Cycle char(4) NOT NULL,
	            FECRecNo char(7)  NOT NULL,
	            FilerID char(9)  NOT NULL,
	            DonorCmte varchar(40)  NULL,
	            ContribLendTrans varchar(40)  NULL,
	            City varchar(18)  NULL,
	            State char(2)  NULL,
	            Zip char(5)  NULL,
	            FECOccEmp varchar(35)  NULL,
	            PrimCode char(5)  NULL,
	            Date datetime NULL,
	            Amount float NULL,
	            RecipID char(9)  NULL,
	            Party char(1)  NULL,
	            OtherID char(9)  NULL,
	            RecipCode char(2)  NULL,
	            RecipPrimcode char(5)  NULL,
	            Amend char(1)  NULL,
	            Report char(3)  NULL,
	            PG char(1)  NULL,
	            Microfilm char(11)  NULL,
	            Type char(3)  NULL,
	            Realcode char(5)  NULL,
	            Source char(5)  NULL
                );"""
        ]
          
        
        for query in queries:
            self.cursor.execute(query)



    def populatetables(self):

        def writerowsfromcsv(file, table):
            def linereader(path):
                infile = open(path, 'rU')
                for line in infile:
                    line = unicode(line, 'ascii', 'ignore').replace('\n', '')
                    yield line
                infile.close()
            
            detailReader =  csv.reader(linereader(file), quotechar='|')
            writerows(detailReader, table)

        def writerows(rows, table):

            def reformatdate(date):
                return date[6:] + '-' + date[:2] + '-' + date[3:5]
            logging.info("Writing " + table)
            for row in rows:
                if len(row)>0:
                    cols = ''
                    if table=='indivs':
                        #split contrib and fam?
                        cols = '(Cycle,FECTransID,ContribID,Contrib,RecipID,Orgname,UltOrg,RealCode,Date,Amount,street,City,State,Zip,Recipcode,Type,CmteID,OtherID,Gender,FECOccEmp,Microfilm ,Occ_EF,Emp_EF,Src,lastname,first,first3)'
                        lastname = row[3].split(', ')[0]
                        first = row[3][len(lastname)+2:]
                        row.append(lastname)
                        row.append(first)
                        row.append(first[:3])
                        row[8] = reformatdate(row[8])
                    if table=='pacs':
                        row[5] = reformatdate(row[5])
                    if table=='pac_other':
                        row[10] = reformatdate(row[10])
                    if table=='expends':
                        row[9] = reformatdate(row[9])



                    sql = "INSERT INTO crp_%s %s VALUES (" % (table, cols)
                    for f in row:
                        f = f.decode('iso8859-1').encode('utf-8','ignore').strip()
                        sql = sql+' %s,'
                    sql = sql[:-1]+");"

                    try:
                        self.cursor.execute(sql,tuple(row)) 
                    except:
                        print( "This FAILED:" + sql + str(row) )
                        pass


        ext = ".txt"
        for year in self.CYCLES:
            self.cursor.execute("DELETE FROM crp_cmtes WHERE cycle='20%s'" % year)
            writerowsfromcsv( os.path.join(self.dest_path, "cmtes" + year + ext), "cmtes")
            self.cursor.execute("DELETE FROM crp_cands WHERE cycle='20%s'" % year)
            writerowsfromcsv( os.path.join(self.dest_path, "cands" + year + ext), "cands")
            self.cursor.execute("DELETE FROM crp_indivs WHERE cycle='20%s'" % year)
            writerowsfromcsv( os.path.join(self.dest_path, "indivs" + year + ext), "indivs")
            self.cursor.execute("DELETE FROM crp_pacs WHERE cycle='20%s'" % year)
            writerowsfromcsv( os.path.join(self.dest_path, "pacs" + year + ext), "pacs")
            self.cursor.execute("DELETE FROM crp_pac_other WHERE cycle='20%s'" % year)
            writerowsfromcsv( os.path.join(self.dest_path, "pac_other" + year + ext), "pac_other")

 
 
 
 	            

 


if __name__ == '__main__':
    cycles = sys.argv[1:]
    dl = CampFinDownloader(cycles)

    dl.createtables()
    dl.populatetables()

  
