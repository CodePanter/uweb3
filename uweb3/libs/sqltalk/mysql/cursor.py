#!/usr/bin/python
"""SQLTalk MySQL Cursor class."""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.13'

# Standard modules
import warnings
import weakref
import pymysql

class ReturnObject(tuple):
  """An object that functions as a tuple but has more required attributes."""

  def __new__(cls, connection, results):
    """Creates the immutable tuple."""
    return super().__new__(cls, tuple(results))

  def __init__(self, connection, results):
    """Adds the required attributes."""
    if connection._result is not None:
      self.insertid = connection._result.insert_id
    else:
      self.insertid = None


class Cursor(pymysql.cursors.DictCursor):
  """Cursor to execute database interaction with, within a transaction."""

  def __init__(self, connection):
    self.description = None
    self.rownumber = 0
    self.rowcount = -1
    self.arraysize = 1
    self._executed = None
    self._result = None
    self._rows = None
    self._warnings_handled = False
    self._connection = weakref.ref(connection)

  def _Execute(self, query):
    """Actually executes the query and returns the result of it.

    Arguments:
      @ query: basestring,
        Fully formatted sql statement to execute. In case of unicode, the
        string is encoded to the local character set before it is passed on
        to the server.

    Returns:
      sqlresult.ResultSet instance holding all query result data.
    """
    # TODO(Elmer): Fix this so that arguments can be given independent of the
    # query they belong to. This enables proper SelectTables and enables a host
    # of other escaping things to start working properly.
    #   Refer to MySQLdb.cursor code (~line 151) to see how this works.
    self._LogQuery(query)
    return self.connection.Query(query.strip(), self)

  def _LogQuery(self, query):
    connection = self.connection
    if not isinstance(query, str):
      query = str(query, connection.charset, errors='replace')
    connection.logger.debug(query)
    connection.queries.append(query)

  @staticmethod
  def _StringConditions(conditions, _unused_field_escape):
    if not conditions:
      return '1'
    elif not isinstance(conditions, str):
      return ' AND '.join(conditions)
    return conditions

  @staticmethod
  def _StringFields(fields, field_escape):
    if fields is None:
      return '*'
    elif isinstance(fields, str):
      return field_escape(fields)
    return ', '.join(field_escape(fields, True))

  @staticmethod
  def _StringGroup(group, field_escape):
    if group is None:
      return ''
    elif isinstance(group, str):
      return 'GROUP BY ' + field_escape(group)
    return 'GROUP BY ' + ', '.join(field_escape(group, True))

  @staticmethod
  def _StringLimit(limit, offset):
    if limit is None:
      return ''
    elif offset:
      return 'LIMIT %d OFFSET %d' % (limit, offset)
    return 'LIMIT %d' % limit

  @staticmethod
  def _StringOrder(order, field_escape):
    if order is None:
      return ''
    orders = []
    for rule in order:
      if isinstance(rule, str):
        orders.append(field_escape(rule))
      else:
        orders.append('%s %s' % (field_escape(rule[0]), ('', 'DESC')[rule[1]]))
    return 'ORDER BY ' + ', '.join(orders)

  @staticmethod
  def _StringTable(table, field_escape):
    if isinstance(table, str):
      return field_escape(table)
    return ', '.join(field_escape(table, True))

  def Delete(self, table, conditions, order=None,
             limit=None, offset=0, escape=True):
    """Remove row(s) from table that match conditions, up to limit.

    Arguments:
      table:      string. Name of the table to delete.
      conditions: string/list/tuple (optional).
                  Where statements. Literal as string. AND'd if list/tuple.
                  THESE WILL NOT BE ESCAPED FOR YOU, EVER.
      order:      (nested) list/tuple (optional).
                  Defines sorting of table before updating, elements can be:
                    string: a field to order by (in default database order).
                    list/tuple of two elements:
                      1) string, field name to order by
                      2) bool, revserse; set this to True to reverse the order
      limit:      integer. Defines max number of rows to delete. Default: None.
      offset:     integer (optional). Number of rows to skip, requires limit.
      escape:     boolean. Defines whether table and field names should be
                  escaped. Set this to False if you want to make use of MySQL
                  functions on this query. Default True.

    Returns:
      sqlresult.ResultSet object.
    """
    field_escape = self.connection.EscapeField if escape else lambda x: x
    return self._Execute('delete from %s where %s %s %s' % (
        self._StringTable(table, field_escape),
        self._StringConditions(conditions, field_escape),
        self._StringOrder(order, field_escape),
        self._StringLimit(limit, offset)))

  def Describe(self, table, field=''):
    """Describe table in database or field in table.

    Takes
      table: string. Name of the table to describe.
      field: string (optional). Field name to describe.

    Returns:
      sqlresult.ResultSet object.
    """
    return self._Execute('DESC %s %s' % (
        self._StringTable(table, self.connection.EscapeField),
        self._StringFields(field, self.connection.EscapeField)))

  def Execute(self, query):
    """Executes a raw query."""
    return self._Execute(query)

  def Insert(self, table, values, escape=True):
    """Insert new row into table.

    This method can also perform multi-row insert.
    By default, input strings are quoted, made safe to be inserted into MySQL
    and the Python None-object is translated to MySQL 'NULL'.

    Arguments:
      table:   string. Name of the table to insert into.
      values:  dictionary or list/tuple.
               Dictionary for single inserts:
               * keys:   field names
               * values: field values
               List of dictionaries for a multi-row insert:
               * Each record as a single dictionary.
               * Each dictionary should have the same keys (fields).
      escape:  boolean. Defines whether table names, fields and values should
               be escaped. Set this to False if you want to make use of
               MySQL functions on this query. Default True.

    Returns:
      sqlresult.ResultSet object.
    """
    if not values:
      raise ValueError('Must insert 1 or more value')
    values = self.connection.EscapeValues(values) if escape else values
    table = self.connection.EscapeField(table) if escape else table
    try:
      # Single insert
      values = ', '.join('`%s`=%s' % value for value in values.items())
      query = 'INSERT INTO %s SET %s' % (table, values)
    except AttributeError:
      # Multi-row insert
      fields = ', '.join(map(self.connection.EscapeField, values[0]))
      values = ', '.join('(%s)' % ', '.join(row.itervalues()) for row in values)
      query = 'INSERT INTO %s (%s) VALUES %s' % (table, fields, values)
    return self._Execute(query)

  def Select(self, table, fields=None, conditions=None, order=None,
             group=None, limit=None, offset=0, escape=True, totalcount=False,
             distinct=False):
    """Select fields from table that match the conditions, ordered and limited.

    Arguments:
      table:      string/list/tuple. Table(s) to select fields out of.
      fields:     string/list/tuple (optional). Fields to select. Default '*'.
                  As string, single field name. (autoquoted)
                  As list/tuple, one field name per element. (autoquoted)
                  If the fielname itself is supplied as a tuple,
                  `field` as `name' will be returned where name is the second
                  item in the tuple. (autoquoted)
      conditions: string/list/tuple (optional). SQL 'where' statement.
                  Literal as string. AND'd if list/tuple.
                  THESE WILL NOT BE ESCAPED FOR YOU, EVER.
      order:      (nested) list/tuple (optional).
                  Defines sorting of table before updating, elements can be:
                    string: a field to order by (in default database order).
                    list/tuple of two elements:
                      1) string, field name to order by
                      2) bool, revserse; set this to True to reverse the order
      group:      str (optional). Field name or function to group result by.
      limit:      integer (optional). Defines output size in rows.
      offset:     integer (optional). Number of rows to skip, requires limit.
      escape:     boolean. Defines whether table and field names should be
                  escaped. Set this to False if you want to make use of MySQL
                  functions on this query. Default True.
      totalcount: boolean. If this is set to True, queries with a LIMIT applied
                  will have the full number of matching rows on
                  the affected_rows attribute of the resultset.
      distinct:   bool (optional). Performs a DISTINCT query if set to True.

    Returns:
      sqlresult.ResultSet object.
    """
    field_escape = self.connection.EscapeField if escape else self.NoEscapeField
    result = self._Execute('SELECT %s %s %s FROM %s WHERE %s %s %s %s' % (
        'SQL_CALC_FOUND_ROWS' if totalcount and limit is not None else '',
        'DISTINCT' if distinct else '',
        self._StringFields(fields, field_escape),
        self._StringTable(table, field_escape),
        self._StringConditions(conditions, field_escape),
        self._StringGroup(group, field_escape),
        self._StringOrder(order, field_escape),
        self._StringLimit(limit, offset)))
    if totalcount and limit is not None:
      result.affected = self._Execute('SELECT FOUND_ROWS()')[0][0]
    return result

  def NoEscapeField(self, field, multiple=False):
    """Returns a SQL unescaped field or table name.

    Set multiple = True if field is a tuple of names to be returned.
    If multiple = False, and a tuple is encountered `field` as `name` will be
      returned where the second part of the tuple is the `name` part.
    """
    if not field:
      return ''
    if isinstance(field, str):
      return field
    elif not multiple and isinstance(field, tuple):
      return '%s as %s' % (field[0], field[1])
    return map(self.NoEscapeField, field)

  def SelectTables(self, contains=None, exact=False):
    """Returns table names from the current database.

    Arguments
      % contains: str ~~ ''
        A substring required to be present in all returned table names.
      % exact: bool ~~ False
        Flags whether the string given in contains should be the exact name.

    Returns:
      set: tables names that match the filter.
    """
    if contains:
      contains = self.connection.EscapeValues(contains)
      if exact:
        result = self._Execute('SHOW TABLES LIKE %s' % contains)
      else:
        # Strip quotes from escaped string to allow insertion of wildcards.
        result = self._Execute('SHOW TABLES LIKE "%%%s%%"' % (
            contains.strip("'")))
    else:
      result = self._Execute('SHOW TABLES')
    return set(result[result.fieldnames[0]])

  def Truncate(self, table):
    """Truncate table in database, reducing it to 0 rows.

    Arguments:
      table: string, name of the table to truncate.

    Returns:
      sqlresult.ResultSet object.
    """
    return self._Execute('TRUNCATE %s' % (
        self._StringTable(table, self.connection.EscapeField)))

  def Update(self, table, values, conditions, order=None,
             limit=None, offset=None, escape=True):
    """Updates table records to the new values where conditions are met.

    Arguments:
      table:      string. Name of table to update values in.
      values:     dictionary. Key for fieldname, value for content (autoquoted).
      conditions: string/list/tuple.
                  Where statements. Literal as string. AND'd if list/tuple.
                  THESE WILL NOT BE ESCAPED FOR YOU, EVER.
      order:      (nested) list/tuple (optional).
                  Defines sorting of table before updating, elements can be:
                    string: a field to order by (in default database order).
                    list/tuple of two elements:
                      1) string, field name to order by
                      2) bool, revserse; set this to True to reverse the order
      limit:      integer (optional). Defines max rows to update.
                  Default value for this is None, meaning no limit.
      offset:     integer (optional). Number of rows to skip, requires limit.
      escape:     boolean. Defines whether table names, fields and values should
                  be escaped. Set this to False if you want to make use of
                  MySQL functions on this query. Default True.

    Returns:
      sqlresult.ResultSet object.
    """
    if escape:
      field_escape = self.connection.EscapeField
      values = self.connection.EscapeValues(values)
    else:
      field_escape = lambda x: x

    return self._Execute('UPDATE %s SET %s WHERE %s %s %s' % (
        self._StringTable(table, field_escape),
        ', '.join('`%s`=%s' % value for value in values.items()),
        self._StringConditions(conditions, field_escape),
        self._StringOrder(order, field_escape),
        self._StringLimit(limit, offset)))

  def _ProcessWarnings(self, resultset):
    """Updates messages attribute with warnings given by the MySQL server."""
    db_info = self.connection.Info()
    db_warnings = self.connection.ShowWarnings()
    if db_warnings:
      # This is done in two loops in case Warnings are set to raise exceptions.
      for warning in db_warnings:
        self.connection.logger.warning(
            '%d: %s\nQuery: %s', warning[1], warning[2], resultset.query)
        resultset.warnings.append(warning)
      for warning in db_warnings:
        warnings.warn(warning[-1], self.Warning, 3)

  @property
  def connection(self):
    """Returns the connection that this cursor belongs to."""
    connection = self._connection()
    if connection is None:
      raise self.ProgrammingError('Connection for this cursor closed.')
    return connection

  DatabaseError = pymysql.DatabaseError
  DataError = pymysql.DataError
  Error = pymysql.Error
  IntegrityError = pymysql.IntegrityError
  InterfaceError = pymysql.InterfaceError
  InternalError = pymysql.InternalError
  NotSupportedError = pymysql.NotSupportedError
  OperationalError = pymysql.OperationalError
  ProgrammingError = pymysql.ProgrammingError
  Warning = pymysql.Warning
