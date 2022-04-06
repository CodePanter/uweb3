#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Tests for the request module."""

# Method could be a function
# pylint: disable-msg=R0201

# Too many public methods
# pylint: disable-msg=R0904

# Standard modules
try:
  import cStringIO as stringIO
except ImportError:
  import io as stringIO

import unittest
import urllib

# Unittest target
from uweb3 import request


class IndexedFieldStorageTest(unittest.TestCase):
  """Comprehensive testing of the IndexedFieldStorage object."""

  def CreateFieldStorage(self, data):
    """Returns an IndexedFieldStorage object constructed from the given data."""
    return request.IndexedFieldStorage(stringIO.StringIO(data),
                                       environ={'REQUEST_METHOD': 'POST'})

  def testEmptyStorage(self):
    """An empty IndexedFieldStorage is empty and is boolean False"""
    ifs = self.CreateFieldStorage('')
    self.assertFalse(ifs)

  def testBasicStorage(self):
    """A basic IndexedFieldStorage has the proper key + value pair"""
    ifs = self.CreateFieldStorage('key=value')
    self.assertEqual(ifs.getfirst('key'), 'value')
    self.assertEqual(ifs.getlist('key'), ['value'])

  def testMissingKey(self):
    """getfirst / getlist for missing keys return proper defaults"""
    ifs = self.CreateFieldStorage('')
    self.assertEqual(ifs.getfirst('missing'), None)
    self.assertEqual(ifs.getfirst('missing', 'signal'), 'signal')
    self.assertEqual(ifs.getlist('missing'), [])
    # getlist has no default argument

  def testMultipleKeyOrder(self):
    """getlist returns keys in the order they were given to the FieldStorage"""
    args = ['1', '3', '2']
    ifs = self.CreateFieldStorage('arg=1&arg=3&arg=2')
    self.assertEqual(ifs.getlist('arg'), args)

  def testUrlEncoding(self):
    """IndexedFieldStorage can handle utf-8 encoded forms"""
    string = u'We ♥ Unicode'
    try:
      data = urllib.urlencode({'q': string})
    except AttributeError:
      data = urllib.parse.urlencode({'q': string})
    ifs = self.CreateFieldStorage(data)
    self.assertEqual(ifs.getfirst('q'), string)

  def testDictionaryFunctionality(self):
    """The indexing of IndexedFieldStorage allows dict-like assignment"""
    data = 'd[name]=Arthur&d[type]=King'
    ifs = self.CreateFieldStorage(data)
    self.assertEqual(ifs.getfirst('d'), {'name': 'Arthur', 'type': 'King'})

  def testDictionaryAndMultipleValues(self):
    """Dictionaries and regular values can be combined; dict is item no. #1"""
    data = 'd=third&d[first]=1&d[second]=2&d=fourth'
    ifs = self.CreateFieldStorage(data)
    form_data = ifs.getlist('d')
    self.assertEqual(form_data[0], {'first': '1', 'second': '2'})
    self.assertEqual(form_data[1], 'third')
    self.assertEqual(form_data[2], 'fourth')


if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
