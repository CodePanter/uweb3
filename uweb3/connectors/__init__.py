#!/usr/bin/python3
"""This file contains the Base connector for model connections and imports all
available connectors."""

__author__ = 'Jan Klopper (jan@underdark.nl)'
__version__ = 0.1

class Connector(object):
  """Base Connector class, subclass from this to create your own connectors.
  Usually the name of your class is used to lookup its config in the
  configuration file, or the database or local filename.

  Connectors based on this class are Usually Singletons. One global connection
  is kept alive, and multiple model classes use it to connect to their
  respective tables, cookies, or files.
  """
  _NAME = None

  @classmethod
  def Name(cls):
    """Returns the 'connector' name, which is usally used to lookup its config
     in the config file.

    If this is not explicitly defined by the class constant `_TABLE`, the return
    value will be the class name with the first letter lowercased.
    """
    if cls._NAME:
      return cls._NAME
    name = cls.__name__
    return name[0].lower() + name[1:]

  def Disconnect(self):
    """Standard interface to disconnect from data source"""
    raise NotImplementedError

  def Rollback(self):
    """Standard interface to rollback any pending commits"""
    raise NotImplementedError

from .SignedCookie import SignedCookie
from .Mysql import Mysql
from .Mongo import Mongo
from .Sqlite import Sqlite
from .SqlAlchemy import SqlAlchemy
