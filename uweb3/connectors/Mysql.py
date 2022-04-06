#!/usr/bin/python3
"""This file contains the connector for Mysql."""
__author__ = 'Jan Klopper (janunderdark.nl)'
__version__ = 0.1

from . import Connector

class Mysql(Connector):
  """Adds MySQL support to connection manager object."""

  def __init__(self, config, options, request, debug=False):
    """Returns a MySQL database connection."""
    self.debug = debug
    self.options = {'host': 'localhost',
                   'user': None,
                   'password': None,
                   'database': ''}
    try:
      from ..libs.sqltalk import mysql
      try:
        self.options = options[self.Name()]
      except KeyError:
        pass
      self.connection = mysql.Connect(
        host=self.options.get('host', 'localhost'),
        user=self.options.get('user'),
        passwd=self.options.get('password'),
        db=self.options.get('database'),
        charset=self.options.get('charset', 'utf8'),
        debug=self.debug)
    except Exception as e:
      raise ConnectionError('Connection to "%s" of type "%s" resulted in: %r' % (self.Name(), type(self), e))

  def Rollback(self):
    with self.connection as cursor:
      return cursor.Execute("ROLLBACK")

  def Disconnect(self):
    """Closes the MySQL connection."""
    if self.debug:
      print('%s closed connection to: %r' % (self.Name(), self.options.get('database')))
    self.connection.close()
    del(self.connection)
