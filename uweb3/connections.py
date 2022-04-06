#!/usr/bin/python3
"""This file contains all the connectionManager classes that interact with
databases, restfull apis, secure cookies, config files etc."""
__author__ = 'Jan Klopper (janunderdark.nl)'
__version__ = 0.2

import sys

import uweb3

from .connectors import *

class ConnectionError(Exception):
  """Error class thrown when the underlying connectors thrown an error on
  connecting."""

class ConnectionManager(object):
  """This is the connection manager object that is handled by all Model Objects.
  It finds out which connection was requested by looking at the call stack, and
  figuring out what database type the model class calling it belongs to.

  Connected databases are stored and reused.
  On delete, the databases are closed and any lingering transactions are
  committed. to complete the database writes.
  """

  DEFAULTCONNECTIONMANAGER = None

  def __init__(self, config, options, debug, requestdepth=3, requestmaxdept=100):
    """Initializes the ConnectionManager

     Arguments:
      % config: reference to config parser
      config instance
      % options: reference to config parsers dict
      options for the various settings provided in the config
      % debug: bool, Optional defaults to False
      Outputs extra debugging information if set to True
      % requestdept: int, indicates how many stack layers we should start at
      lookin up the stack to find our request object. Optional defaults to 2.
      % requestdept: int, requestmaxdepth indicates how many stack layers at
      maximum we should start at lookin up the stack to find our request object.
      Optional defaults to 100.

    """
    self.__connectors = {} # classes
    self.__connections = {} # instances
    self.config = config
    self.options = options
    self.debug = debug
    self.LoadDefaultConnectors()
    self.requestdepth = requestdepth
    self.requestmaxdepth = requestmaxdept

  def LoadDefaultConnectors(self):
    """Populates the list of Connectors with the default available connectors"""
    self.RegisterConnector(SignedCookie)
    self.RegisterConnector(Mysql, True)
    self.RegisterConnector(Sqlite)
    self.RegisterConnector(Mongo)
    self.RegisterConnector(SqlAlchemy)

  def RegisterConnector(self, handler, default=False):
    """Make the ConnectonManager aware of a new type of connector.

    Arguments:
      % handler: class
      Reference to the class that will handle the connections
      % default: bool, Optional defaults to False
      Should this Connector be considers the default connector?
    """
    if default:
      self.DEFAULTCONNECTIONMANAGER = handler.Name()
    self.__connectors[handler.Name()] = handler

  def RelevantConnection(self, level=2):
    """Returns the relevant database connection dependant on the caller model
    class.

    If the caller model cannot be determined, the 'relational' database
    connection is returned as a fallback method.

    Level indicates how many stack layers we should go up to find the current
    caller_class which indicates our connector type. Defaults to 2.

    When no connection can be found or made due to a missing request from this
    context a TypeError will be raised.

    When no connection can be found or made Due to a missing connector class a
    TypeError will be raised.
    """
    # Figure out caller type or instance
    # pylint: disable=W0212
    #TODO use inspect module instead, and iterate over frames
    caller_locals = sys._getframe(level).f_locals
    # pylint: enable=W0212
    # Caller might be a Class or Class instance
    if 'self' in caller_locals:
      caller_cls = type(caller_locals['self'])
    else:
      caller_cls = caller_locals.get('cls', type)
    # Decide the type of connection to return for this caller
    con_type = (caller_cls._CONNECTOR if hasattr(caller_cls, '_CONNECTOR') else
                self.DEFAULTCONNECTIONMANAGER)
    if (con_type in self.__connections and
        hasattr(self.__connections[con_type], 'connection')):
      return self.__connections[con_type].connection

    try:
      # instantiate a connection
      self.__connections[con_type] = self.__connectors[con_type](
          self.config, self.options, self.request, self.debug)
      return self.__connections[con_type].connection
    except KeyError as error:
      raise TypeError('No connector for: %r, available: %r, %r' % (
          con_type, self.__connectors, error))

  @property
  def request(self):
    """Returns the request object as looked up in the stack.

    When no connection can be found or made due to a missing request from this
    context a TypeError will be raised.

    When no connection can be found or made Due to a missing connector class a
    TypeError will be raised.
    """
    requestdepth = self.requestdepth
    while requestdepth < self.requestmaxdepth:
      try:
        parent = sys._getframe(requestdepth).f_locals['self']
        if isinstance(parent, uweb3.PageMaker) and hasattr(parent, 'req'):
          return parent.req
      except (KeyError, AttributeError, ValueError):
        pass
      requestdepth = requestdepth + 1
    raise TypeError('No request could be found in call Stack or no "model" connections are present.')

  def __enter__(self):
    """Proxies the transaction to the underlying relevant connection."""
    return self.RelevantConnection().__enter__()

  def __exit__(self, *args):
    """Proxies the transaction to the underlying relevant connection."""
    return self.RelevantConnection().__exit__(*args)

  def __getattr__(self, attribute):
    return getattr(self.RelevantConnection(), attribute)

  def RollbackAll(self):
    """Performs a rollback on all connectors with pending commits."""
    if self.debug:
      print('Rolling back uncommited transaction on all connectors.')
    for classname in self.__connections:
      try:
        self.__connections[classname].Rollback()
      except NotImplementedError:
        pass

  def PostRequest(self):
    """This cleans up any non persistent connections.
    Eg, connections that rely on request information, or connections that should
    not be kept alive beyond the scope of a request.
    """
    cleanups = [
        classname for classname in self.__connections
        if (hasattr(self.__connections[classname], 'PERSISTENT')
            and not self.__connections[classname].PERSISTENT)
    ]
    for classname in cleanups:
      try:
        self.__connections[classname].Disconnect()
      except (NotImplementedError, TypeError, ConnectionError):
        pass
      del(self.__connections[classname])

  def __iter__(self):
    """Pass tru to the Relevant connection as an Iterable, so variable unpacking
    can be used by the consuming class. This is used in the SecureCookie Model
    class."""
    return iter(self.RelevantConnection())

  def __del__(self):
    """Cleans up all references, and closes all connectors"""
    if self.debug:
      print('Deleting model connections.')
    for classname in self.__connectors:
      if not hasattr(self.__connectors[classname], 'connection'):
        continue
      try:
        self.__connections[classname].Disconnect()
      except (NotImplementedError, TypeError, ConnectionError):
        pass
