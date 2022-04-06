#!/usr/bin/python3
"""This file contains the connector for Signed cookies."""
__author__ = 'Jan Klopper (janunderdark.nl)'
__version__ = 0.1

import os
from base64 import b64encode

from . import Connector

class SignedCookie(Connector):
  """Adds a signed cookie connection to the connection manager object.

  The name of the class is used as the Cookiename"""

  PERSISTENT = False

  def __init__(self, config, options, request, debug=False):
    """Sets up the local connection to the signed cookie store, and generates a
    new secret key if no key can be found in the config"""
    self.debug = debug
    # Generating random seeds on uWeb3 startup or fetch from config
    try:
      self.options = options[self.Name()]
      self.secure_cookie_secret = self.options['secret']
    except KeyError:
      secret = self.GenerateNewKey()
      config.Create(self.Name(), 'secret', secret)
      if self.debug:
        print('SignedCookie: Wrote new secret random to config.')
      self.secure_cookie_secret = secret
    self.connection = (request, request.vars['cookie'], self.secure_cookie_secret)

  @staticmethod
  def GenerateNewKey(length=128):
    return b64encode(os.urandom(length)).decode('utf-8')
