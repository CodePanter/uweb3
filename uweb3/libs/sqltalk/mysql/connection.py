#!/usr/bin/python3
"""This module implements the Connection class, which sets up a connection to
a MySQL database. From this connection, cursor objects can be created, which
use the escaping and character encoding facilities offered by the connection.
"""
__author__ = ('Elmer de Looff <elmer@underdark.nl>',
              'Jan Klopper <jan@underdark.nl>')
__version__ = '0.17'

# Standard modules
import pymysql
import logging
import threading
import weakref

# Application specific modules
from pymysql import constants
from pymysql import converters
from . import cursor
from .. import sqlresult


class Connection(pymysql.connections.Connection):
  """MySQL Database Connection Object"""

  def __init__(self, user, passwd, *args, **kwargs):
    """Create a connection to the database. It is strongly recommended
    that you only use keyword parameters. Consult the MySQL C API
    documentation for more information.

    Arguments:
      user:               string, user to connect as.
      passwd:             string, password to use.
      db:                 string, database to use. Default same as user.
      host:               string, host to connect to. Default 'localhost'.
      port:               integer, TCP/IP port to connect to.
      unix_socket:        string, location of unix_socket to use.
      conv:               conversion dictionary, see converters module.
      connect_timeout:    number of seconds to wait before the connection
                          attempt fails.
      compress:           bool, enable compression. Not supported by PyMySQL.
      named_pipe:         if set, a named pipe is used to connect Not supported
                          by PyMySQL.
      init_command:       command which is run once the connection is created
      read_default_file:  file from which default client values are read
      read_default_group: configuration group to use from the default file
      use_unicode:        If True, text-like columns are returned as unicode
                          objects using the connection's character set.
                          Otherwise, text-like columns are returned as strings.
                          Columns are returned as normal strings. Unicode
                          objects will always be encoded to the connection's
                          character set regardless of this setting.
      charset:            If supplied, the connection character set will be
                          changed to this character set (MySQL-4.1 and newer).
                          This enforces use_unicode=True.
      sql_mode:           If supplied, the session SQL mode will be changed to
                          this setting (MySQL-4.1 and newer). For more details
                          and legal values, see the MySQL documentation.
      client_flag:        integer, flags to use or 0.
                          (see MySQL docs or constants/CLIENTS.py)
      ssl:                dictionary or mapping, contains SSL connection
                          parameters; see the MySQL documentation for more
                          details (mysql_ssl_set()).  If this is set, and the
                          client does not support SSL, NotSupportedError will
                          be raised.
      local_infile:       bool, True enables LOAD LOCAL INFILE, False disables.
                          Default False

    There are a number of undocumented, non-standard arguments. See the
    documentation for the MySQL C API for some hints on what they do.
    """
    # Counters, transaction lock & timer
    self.counter_transactions = 0
    self.counter_queries = 0
    self.queries = []
    self.transaction_timer = None
    self.lock = threading.Lock()
    self._charset = None

    # PyMySQL connect args mapping
    kwargs['user'] = user
    kwargs['passwd'] = passwd
    kwargs['host'] = kwargs.get('host', 'localhost')
    kwargs['db'] = kwargs.get('db', user)
    if 'compress' in kwargs:
      raise self.NotSupportedError("PyMySQL doesn't support compression.")
    if 'named_pipe' in kwargs:
      raise self.NotSupportedError("PyMySQL doesn't support named pipes.")
    self.logger = logging.getLogger('mysql_%s' % kwargs['db'])
    if kwargs.pop('debug', False):
      self.debug = True
      self.logger.setLevel(logging.DEBUG)
    else:
      self.debug = False
      self.logger.setLevel(logging.WARNING)
    if kwargs.pop('disable_log', False):
      self.logger.disable_logger = True

    autocommit = kwargs.pop('autocommit', None)
    charset = kwargs.pop('charset', 'utf8')
    sql_mode = kwargs.pop('sql_mode', None)
    # use_unicode = kwargs.pop('use_unicode', False) or bool(charset)

    # The following voodoo is necessary to avoid double references that would
    # prevent a connection object from being finalized and collected properly.
    db = weakref.proxy(self)

    # def _GetUnicodeLiteral():
    #   def UnicodeLiteral(u_string, _dummy=None):
    #     """Returns the SQL (safe) literal for the given unicode object."""
    #     return db.EscapeValues(u_string.encode(db.charset))
    #   return UnicodeLiteral

    def _GetStringDecoder():
      def StringDecoder(string):
        """Returns the unicode codepoints for an encoded bytestream."""
        return string.decode(db.charset)
      return StringDecoder

    encoders = {}
    converts = {}
    conversions = converters.conversions
    self.string_decoder = _GetStringDecoder()

    # if use_unicode:
    #   decoder = self.string_decoder
    #   conversions[constants.FIELD_TYPE.STRING] = decoder
    #   conversions[constants.FIELD_TYPE.VAR_STRING] = decoder
    #   conversions[constants.FIELD_TYPE.VARCHAR] = decoder
    #   conversions[constants.FIELD_TYPE.BLOB] = decoder

    for key, value in conversions.items():
      if not isinstance(key, int):
        encoders[key] = value
      else:
        if isinstance(value, list):
          converts[key] = value[:]
        else:
          converts[key] = value
    kwargs.setdefault('conv', {}).update(converts)

    client_version = tuple(map(int, pymysql.get_client_info().split('.')[:2]))
    kwargs.setdefault('client_flag', 0)
    if client_version >= (4, 1):
      kwargs['client_flag'] |= constants.CLIENT.MULTI_STATEMENTS
    if client_version >= (5, 0):
      kwargs['client_flag'] |= constants.CLIENT.MULTI_RESULTS

    # Done redefining variables for initialization. Engage PyMySQL!
    super(Connection, self).__init__(*args, **kwargs)
    self.encoders = encoders
    # self.encoders[unicode] = self.unicode_literal = _GetUnicodeLiteral()
    self.converter = conversions

    if sql_mode:
      self.SetSqlMode(sql_mode)

    self.charset = charset or self.character_set_name()

    self.transactional = bool(self.server_capabilities &
                              constants.CLIENT.TRANSACTIONS)
    self.autocommit_mode = None
    if autocommit is not None:
      self.autocommit_mode = autocommit
    else:
      self.autocommit_mode = not self.transactional

  def __enter__(self):
    """Refreshes the connection and returns a cursor, starting a transaction."""
    if self.lock.acquire():  # This will block when the lock is in use. In normal situations this should never happen.
      self.counter_transactions += 1
      del self.queries[:]
      self._SetAutocommitState(self.autocommit)
      self.StartTransactionTimer()
      return cursor.Cursor(self)
    raise self.OperationalError(
        'A transaction is already open for this connection.')

  def __exit__(self, exc_type, exc_value, _exc_traceback):
    """End of transaction: commits on success, or rolls back on failure."""
    self.ResetTransactionTimer()
    if exc_type:
      self.rollback()
      if self.debug:
        self.logger.exception(
            'The transaction was rolled back after an exception.\n'
            'Server: %s\nQueries in transaction (last one triggered):\n\n%s',
            self.get_host_info(),
            '\n\n'.join(self.queries))
    else:
      self.commit()
      if self.debug:
        self.logger.debug(
            'Transaction committed (server: %r).', self.get_host_info())
    self.lock.release()

  def CurrentDatabase(self):
    """Return the name of the currently used database"""
    return self.Query('SELECT DATABASE()')[0]

  def EscapeField(self, field, multiple=False):
    """Returns a SQL escaped field or table name.

    Set multiple = True if field is a tuple of names to be escaped.
    If multiple = False, and a tuple is encountered `field` as `name` will be
      returned where the second part of the tuple is the `name` part.
    """
    if not field:
      return ''
    if isinstance(field, str):
      fields = '.'.join('`%s`' % f.replace('`', '``') for f in field.split('.'))
      return fields.replace('`*`', '*')
    elif not multiple and isinstance(field, tuple):
      return '%s as %s' % (self.EscapeField(field[0]), self.EscapeField(field[1]))
    return map(self.EscapeField, field)

  def EscapeValues(self, obj):
    """Escapes any object passed in following the encoders dictionary.

    Sequences and mappings will only have their contents escaped. All strings
    will be encoded to the connection's character set.
    """
    if isinstance(obj, tuple) or isinstance(obj, list):
      return list(map(lambda x: self.escape(x, self.encoders), obj))
    return self.escape(obj, self.encoders)

  def Info(self):
    """Returns a dictionary of MySQL server info and current active database.

    Returns
      dictionary: keys: 'db', 'charset', 'server', 'debug', 'autocommit',
                        'querycount', 'transactioncount'
    """
    return {'db': self.CurrentDatabase(),
            'charset': self._GetCharacterSet(),
            'server': self.ServerInfo(),
            'debug': self.debug,
            'autocommit': self.autocommit_mode,
            'querycount': self.counter_queries,
            'transactioncount': self.counter_transactions}

  def Query(self, query_string, cur=None):
    self.counter_queries += 1
    if isinstance(query_string, str):
      query_string = query_string.encode(self.charset)
    if not cur:
      cur = cursor.Cursor(self)
    cur.execute(query_string)
    stored_result = cur.fetchall()
    if stored_result:
      fields = list(stored_result[0])
    else:
      fields = []
    return sqlresult.ResultSet(
        affected=self.affected_rows(),
        charset=self.charset,
        fields=fields,
        insertid=self.insert_id(),
        query=query_string.decode(self.charset, 'ignore'),
        result=stored_result)

  def ServerInfo(self):
    """Returns a mysql specific set of server information"""
    return self.get_server_info()

  def SetSqlMode(self, sql_mode):
    """Set the connection sql_mode. See MySQL documentation for legal values."""
    self.Query('SET SESSION sql_mode=%s' % self.EscapeValues(sql_mode))

  def ShowWarnings(self):
    """Return detailed information about warnings as a sequence of tuples of
    (Level, Code, Message)."""
    return self.Query('SHOW WARNINGS')

  def StartTransactionTimer(self, delay=60):
    """Writes a warning to the log if the transaction is open too long.

    N.B. The timer is only set when the connection is in debug mode. Calling
    this method on a non-debug connection will do nothing.
    """
    def Warn(caller, delay=delay):
      self.logger.warning('Transaction open for more than %s seconds.', delay)

    if self.debug:
      self.transaction_timer = threading.Timer(delay, Warn)
      self.transaction_timer.daemon = True
      self.transaction_timer.start()

  def ResetTransactionTimer(self):
    """Resets any existing transaction timer."""
    if self.transaction_timer:
      self.transaction_timer.cancel()

  def _GetAutocommitState(self):
    """This returns the current setting for autocommiting transactions."""
    return self.autocommit_mode

  def _GetCharacterSet(self):
    """This configures the character set used by this connection.

    Character sets should be specified as known and supported by MySQL.
    """
    return self._charset

  def _SetAutocommitState(self, state):
    """This sets the autocommit mode on the connection.

    This is False by default if the database supports transactions."""
    try:
      self.ping(reconnect=True)
    except:
      self.connect(sock=None)
    super(Connection, self).autocommit(state)
    self.autocommit_mode = state

  def _SetCharacterSet(self, charset):
    """This sets the character set, refer to _GetCharacterSet for doc."""
    if charset != self._charset:
      super(Connection, self).set_charset(charset)
      self._charset = charset


  # Error classes taken from PyMySQL
  Error = pymysql.Error
  InterfaceError = pymysql.InterfaceError
  DatabaseError = pymysql.DatabaseError
  DataError = pymysql.DataError
  OperationalError = pymysql.OperationalError
  IntegrityError = pymysql.err.IntegrityError
  InternalError = pymysql.InternalError
  ProgrammingError = pymysql.ProgrammingError
  NotSupportedError = pymysql.NotSupportedError
  Warning = pymysql.Warning
