#!/usr/bin/python
"""SQLTalk MySQL interface package.

Functions:
  Connect: Connects to a MySQL server and returns a connection object.
           Refer to the documentation enclosed in the connections module for
           argument information.
"""
__author__ = 'Jan Klopper <jan@underdark.nl>'
__version__ = '0.10'

# Application specific modules
from . import connection

def Connect(*args, **kwargs):
  """Factory function for connection.Connection."""
  return connection.Connection(*args, **kwargs)
