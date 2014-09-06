from __future__ import print_function
import os, sys, re, base64
dirNm, execName = os.path.split(os.path.realpath(sys.argv[0]))
sys.path.append(os.path.realpath(os.path.join(dirNm, "../libexec")))
sys.path.append(os.path.realpath(os.path.join(dirNm, "../site")))

import MySQLdb, ConfigParser, getpass, time
import warnings
from   xalt_util import *
from   xalt_site_pkg import translate
warnings.filterwarnings("ignore", "Unknown table.*")

patSQ = re.compile("'")
class XALTdb(object):
  def __init__(self, confFn):
    self.__host   = None
    self.__user   = None
    self.__passwd = None
    self.__db     = None
    self.__conn   = None
    self.__confFn = confFn

  def __readFromUser(self):
    self.__host   = raw_input("Database host:")
    self.__user   = raw_input("Database user:")
    self.__passwd = getpass.getpass("Database pass:")
    self.__db     = raw_input("Database name:")

  def __readConfig(self,confFn):
    try:
      config=ConfigParser.ConfigParser()
      config.read(confFn)
      self.__host    = config.get("MYSQL","HOST")
      self.__user    = config.get("MYSQL","USER")
      self.__passwd  = base64.b64decode(config.get("MYSQL","PASSWD"))
      self.__db      = config.get("MYSQL","DB")
    except ConfigParser.NoOptionError, err:
      sys.stderr.write("\nCannot parse the config file\n")
      sys.stderr.write("Switch to user input mode...\n\n")
      self.__readFromUser()

  def connect(self, db = None):
    if(os.path.exists(self.__confFn)):
      self.__readConfig(self.__confFn)
    else:
      self.__readFromUser()

    try:
      self.__conn = MySQLdb.connect (self.__host,self.__user,self.__passwd)
      if (db):
        cursor = self.__conn.cursor()
        
        # If MySQL version < 4.1, comment out the line below
        cursor.execute("SET SQL_MODE=\"NO_AUTO_VALUE_ON_ZERO\"")
        cursor.execute("USE "+xalt.db())


    except MySQLdb.Error, e:
      print ("XALTdb: Error %d: %s" % (e.args[0], e.args[1]), file=sys.stderr)
      raise

    return self.__conn


  def db(self):
    return self.__db

  def link_to_db(self, reverseMapT, linkT):
    query = ""

    try:
      conn   = self.connect()
      query  = "USE "+self.db()
      conn.query(query)
      query  = "SELECT uuid FROM xalt_link WHERE uuid='%s'" % linkT['uuid']
      conn.query(query)
      result = conn.store_result()
      if (result.num_rows() > 0):
        return

      build_epoch = float(linkT['build_epoch'])
      dateTimeStr = time.strftime("%Y-%m-%d %H:%M:%S",
                                  time.localtime(float(linkT['build_epoch'])))
      # It is unique: lets store this link record
      query = "INSERT into xalt_link VALUES (NULL,'%s','%s','%s','%s','%s','%s','%.2f','%d','%s') " % (
        linkT['uuid'],         linkT['hash_id'],         dateTimeStr,
        linkT['link_program'], linkT['build_user'],      linkT['build_syshost'],
        build_epoch,           int(linkT['exit_code']),  linkT['exec_path'])
      conn.query(query)
      link_id = conn.insert_id()

      XALT_Stack.push("load_xalt_objects():"+linkT['exec_path'])
      self.load_objects(conn, linkT['linkA'], reverseMapT, linkT['build_syshost'],
                        "join_link_object", link_id)
      v = XALT_Stack.pop()  # unload function()
      carp("load_xalt_objects()",v)


    except Exception as e:
      print(XALT_Stack.contents())
      print(query)
      print ("link_to_db(): Error %d: %s" % (e.args[0], e.args[1]))
      sys.exit (1)

  def load_objects(self, conn, objA, reverseMapT, syshost, tableName, index):

    try:
      for entryA in objA:
        object_path  = entryA[0]
        hash_id      = entryA[1]
        if (hash_id == "unknown"):
          continue

        query = "SELECT obj_id FROM xalt_object WHERE hash_id='%s' AND object_path='%s' AND syshost='%s'" % (
          hash_id, object_path, syshost)
        
        conn.query(query)
        result = conn.store_result()
        if (result.num_rows() > 0):
          row    = result.fetch_row()
          obj_id = int(row[0][0])
        else:
          moduleName = obj2module(object_path, reverseMapT)
          obj_kind   = obj_type(object_path)

          query      = "INSERT into xalt_object VALUES (NULL,'%s','%s','%s',%s,NOW(),'%s') " % (
                      object_path, syshost, hash_id, moduleName, obj_kind)
          conn.query(query)
          obj_id   = conn.insert_id()
          #print("obj_id: ",obj_id, ", obj_kind: ", obj_kind,", path: ", object_path, "moduleName: ", moduleName)

        # Now link libraries to xalt_link record:
        query = "INSERT into %s VALUES (NULL,'%d','%d') " % (tableName, obj_id, index)
        conn.query(query)

    except Exception as e:
      print(XALT_Stack.contents())
      print(query)
      print ("load_xalt_objects(): Error %d: %s" % (e.args[0], e.args[1]))
      sys.exit (1)

  def run_to_db(self, reverseMapT, runT):
    
    nameA = [ 'num_cores', 'num_nodes', 'account', 'job_id', 'queue' , 'submit_host']
    try:
      conn   = self.connect()
      query  = "USE "+self.db()
      conn.query(query)

      translate(nameA, runT['envT'], runT['userT']);
      XALT_Stack.push("SUBMIT_HOST: "+ runT['userT']['submit_host'])

      dateTimeStr = time.strftime("%Y-%m-%d %H:%M:%S",
                                  time.localtime(float(runT['userT']['start_time'])))
      uuid        = runT['xaltLinkT'].get('Build.UUID')
      if (uuid):
        uuid = "'" + uuid + "'"
      else:
        uuid = "NULL"

      #print( "Looking for run_uuid: ",runT['userT']['run_uuid'])

      query = "SELECT run_id FROM xalt_run WHERE run_uuid='%s'" % runT['userT']['run_uuid']
      conn.query(query)

      result = conn.store_result()
      if (result.num_rows() > 0):
        #print("found")
        row    = result.fetch_row()
        run_id = int(row[0][0])
        query  = "UPDATE xalt_run SET run_time='%.2f', end_time='%.2f' WHERE run_id='%d'" % (
          runT['userT']['run_time'], runT['userT']['end_time'], run_id)
        conn.query(query)
        v = XALT_Stack.pop()
        carp("SUBMIT_HOST",v)
        return
      else:
        #print("not found")
        moduleName = obj2module(runT['userT']['exec_path'], reverseMapT)
        query  = "INSERT INTO xalt_run VALUES (NULL,'%s','%s','%s', '%s',%s,'%s', '%s','%s','%.2f', '%.2f','%.2f','%d', '%d','%d','%s', '%s','%s',%s,'%s') " % (
          runT['userT']['job_id'],      runT['userT']['run_uuid'],    dateTimeStr,
          runT['userT']['syshost'],     uuid,                         runT['hash_id'],
          runT['userT']['account'],     runT['userT']['exec_type'],   runT['userT']['start_time'],
          runT['userT']['end_time'],    runT['userT']['run_time'],    runT['userT']['num_cores'],
          runT['userT']['num_nodes'],   runT['userT']['num_threads'], runT['userT']['queue'],
          runT['userT']['user'],        runT['userT']['exec_path'],   moduleName,
          runT['userT']['cwd'])
        conn.query(query)
        run_id   = conn.insert_id()

      self.load_objects(conn, runT['libA'], reverseMapT, runT['userT']['syshost'],
                        "join_run_object", run_id) 

      # loop over env. vars.
      for key in runT['envT']:
        # use the single quote pattern to protect all the single quotes in env vars.
        value = patSQ.sub(r"\\'", runT['envT'][key])
        query = "SELECT env_id FROM xalt_env_name WHERE env_name='%s'" % key
        conn.query(query)
        result = conn.store_result()
        if (result.num_rows() > 0):
          row    = result.fetch_row()
          env_id = int(row[0][0])
          found  = True
        else:
          query  = "INSERT INTO xalt_env_name VALUES(NULL, '%s')" % key
          conn.query(query)
          env_id = conn.insert_id()
          found  = False
        #print("env_id: ", env_id, ", found: ",found)

        
        query = "INSERT INTO join_run_env VALUES (NULL, '%d', '%d', '%s')" % (
          env_id, run_id, value.encode("ascii","ignore"))
        conn.query(query)
      v = XALT_Stack.pop()
      carp("SUBMIT_HOST",v)
    except Exception as e:
      print(XALT_Stack.contents())
      print(query.encode("ascii","ignore"))
      print ("run_to_db(): ",e)
      sys.exit (1)
