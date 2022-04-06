#!/usr/bin/python3
"""This file contains the connector for Sqlite."""
__author__ = 'Jan Klopper (janunderdark.nl)'
__version__ = 0.1

from . import Connector

class Sqlite(Connector):
  """Adds SQLite support to connection manager object."""

  def __init__(self,  config, options, request, debug=False):
    """Returns a SQLite database connection.
    The name of the class is used as the local filename.
    """
    from ..libs.sqltalk import sqlite
    self.debug = debug
    self.options = options[self.Name()]
    try:
      self.connection = sqlite.Connect(self.options.get('database'))
    except Exception as e:
      raise ConnectionError('Connection to "%s" of type "%s" resulted in: %r' % (self.Name(), type(self), e))

  def Rollback(self):
    """Rolls back any uncommited transactions."""
    return self.connection.rollback()

  def Disconnect(self):
    """Closes the SQLite connection."""
    if self.debug:
      print('%s closed connection to: %r' % (self.Name(), self.options.get('database')))
    self.connection.close()
    del(self.connection)
