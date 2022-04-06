#!/usr/bin/python3
"""SQLTalk SQLite interface package."""

# Standard modules
import sqlite3

# Application specific modules
from . import connection

VERSION_INFO = tuple(map(int, sqlite3.version.split('.')))
SQLITE_VERSION_INFO = tuple(map(int, sqlite3.sqlite_version.split('.')))


def Connect(*args, **kwds):
  """Factory function for connection.Connection."""
  kwds['detect_types'] = sqlite3.PARSE_DECLTYPES
  return connection.Connection(*args, **kwds)


def ThreadConnect(*args, **kwds):
  """Factory function for connection.ThreadedConnection."""
  kwds['detect_types'] = sqlite3.PARSE_DECLTYPES
  return connection.ThreadedConnection(*args, **kwds)


DataError = sqlite3.DataError
DatabaseError = sqlite3.DatabaseError
Error = sqlite3.Error
IntegrityError = sqlite3.IntegrityError
InterfaceError = sqlite3.InterfaceError
InternalError = sqlite3.InternalError
NotSupportedError = sqlite3.NotSupportedError
OperationalError = sqlite3.OperationalError
