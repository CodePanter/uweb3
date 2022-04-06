#!/usr/bin/python3
"""This file contains the connector for Mongo."""
__author__ = 'Jan Klopper (janunderdark.nl)'
__version__ = 0.1

from . import Connector

class Mongo(Connector):
  """Adds MongoDB support to connection manager object."""

  def __init__(self,  config, options, request, debug=False):
    """Returns a MongoDB database connection."""
    self.debug = debug
    import pymongo
    self.options = options.get(self.Name(), {})
    try:
      self.connection = pymongo.connection.Connection(
         host=self.options.get('host', 'localhost'),
         port=self.options.get('port', 27017))
      if 'database' in self.options:
        self.connection = self.connection[self.options['database']]
    except Exception as e:
      raise ConnectionError('Connection to "%s" of type "%s" resulted in: %r' % (self.Name(), type(self), e))

  def Disconnect(self):
    """Closes the Mongo connection."""
    if self.debug:
      print('%s closed connection to: %r' % (self.Name(), self.options.get('database', 'Unspecified')))
    self.connection.close()
    del(self.connection)
