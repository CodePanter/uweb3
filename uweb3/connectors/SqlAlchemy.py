#!/usr/bin/python3
"""This file contains the connector for SqlAlchemy."""
__author__ = 'Jan Klopper (janunderdark.nl)'
__version__ = 0.1

from . import Connector

class SqlAlchemy(Connector):
  """Adds MysqlAlchemy connection to ConnectionManager."""

  def __init__(self,  config, options, request, debug=False):
    """Returns a Mysql database connection wrapped in a SQLAlchemy session."""
    from sqlalchemy.orm import sessionmaker
    self.debug = debug
    self.options = {'host': 'localhost',
                    'user': None,
                    'password': None,
                    'database': ''}
    try:
      self.options = options[self.Name()]
    except KeyError:
      pass
    Session = sessionmaker()
    Session.configure(bind=self.engine, expire_on_commit=False)
    try:
      self.connection = Session()
    except Exception as e:
      raise ConnectionError('Connection to "%s" of type "%s" resulted in: %r' % (self.Name(), type(self), e))

  def engine(self):
    from sqlalchemy import create_engine
    return create_engine('mysql://{username}:{password}@{host}/{database}'.format(
      username=self.options.get('user'),
      password=self.options.get('password'),
      host=self.options.get('host', 'localhost'),
      database=self.options.get('database')),
      pool_size=5,
      max_overflow=0,
      encoding=self.options.get('charset', 'utf8'),)
