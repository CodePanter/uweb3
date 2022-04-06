#!/usr/bin/python3
"""Testsuite for the SQL Result abstraction module."""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.6'

# Too many public methods
# pylint: disable-msg=R0904

# Statement seems to have no effect
# pylint: disable-msg=W0104

# Unused variable %
# pylint: disable-msg=W0612

# Access to a protected member % of a client class
# pylint: disable-msg=W0212

# Method name too long
# pylint: disable-msg=C0103

# Standard modules
import unittest

# Unittest target
from . import sqlresult


class ResultRowBasicOperation(unittest.TestCase):
  """Ensure basic functionality and usability."""
  def setUp(self):
    """Set up a persistent test environment."""
    names = ['name', 'nationality', 'age']
    values = ('Elmer', 'Dutch', 24)
    self.row = sqlresult.ResultRow(names, values)

  def testFieldErrorIsLookupError(self):
    """SqlResult's FieldError is a subclass of LookupError"""
    self.assertTrue(issubclass(sqlresult.FieldError, LookupError))

  def testRepresentation(self):
    """ResultRow has representation methods that work."""
    repr(self.row)
    str(self.row)

  def testFalseWhenEmpty(self):
    """ResultRow is boolean False when empty."""
    row = sqlresult.ResultRow([], [])
    self.assertFalse(row)

  def testTrueWhenFilled(self):
    """ResultRow is boolean True when it has contents."""
    self.assertTrue(self.row)

  def testLength(self):
    """ResultRow is aware of its own length."""
    self.assertEquals(len(self.row), 3)

  def testGetByIndex(self):
    """ResultRow can retrieve data based on an index."""
    self.assertEquals(self.row[0], 'Elmer')
    self.assertEquals(self.row[2], 24)

  def testGetByKey(self):
    """ResultRow can retrieve data based on a key."""
    self.assertEquals(self.row['nationality'], 'Dutch')
    self.assertEquals(self.row['age'], 24)

  def testGetIndexError(self):
    """ResultRow throws FieldError when a bad index or bad key is requested."""
    self.assertRaises(sqlresult.FieldError, self.row.__getitem__, 4)
    self.assertRaises(sqlresult.FieldError, self.row.__getitem__, 'badkey')

  def testGetMethodIndex(self):
    """ResultRow's Get method works properly for indices."""
    self.assertEquals(self.row.get(1), 'Dutch')
    self.assertEquals(self.row.get(4), None)

  def testGetMethodKey(self):
    """ResultRow's Get method works properly for keys."""
    self.assertEquals(self.row.get('age'), 24)
    self.assertEquals(self.row.get('badkey', 'raargh'), 'raargh')

  def testUpdateKey(self):
    """ResultRow can have its values updated using dictionary assignment"""
    self.row['age'] = 28
    self.assertEquals(self.row['age'], 28)

  def testAddKey(self):
    """ResultRow can have field + value combinations added, like a dict"""
    self.row['role'] = 'developer'
    self.assertEquals(self.row['role'], 'developer')
    self.assertEquals(self.row[3], 'developer')
    self.assertEquals(self.row.popitem(), ('role', 'developer'))

  def testDeleteIndex(self):
    """ResultRow entries can be deleted using the index"""
    del self.row[1]
    self.assertEquals(self.row.items(), [('name', 'Elmer'), ('age', 24)])
    self.assertRaises(sqlresult.FieldError, self.row.__getitem__, 'nationality')

  def testDeleteIndexError(self):
    """ResultRow throws a FieldError when attempting to delete a bad index"""
    self.assertRaises(sqlresult.FieldError, self.row.__delitem__, 100)

  def testDeleteKey(self):
    """ResultRow entries can be deleted using the fieldname"""
    del self.row['nationality']
    self.assertEquals(self.row.items(), [('name', 'Elmer'), ('age', 24)])
    self.assertRaises(sqlresult.FieldError, self.row.__getitem__, 'nationality')

  def testDeleteKeyError(self):
    """ResultRow throws a FieldError when attempting to delete a bad key"""
    self.assertRaises(sqlresult.FieldError, self.row.__delitem__, 'badkey')


class ResultRowDataExtraction(unittest.TestCase):
  """Ensure that all name/value/item collecting methods work as intended."""
  def setUp(self):
    """Set up a persistent test environment."""
    self.names = ['name', 'project', 'age', 'language',
                  'character', 'distro-of-choice']
    self.values = ('Elmer', 'Underdark', 24, 'python', 'geek', u'Ubuntu')
    self.row = sqlresult.ResultRow(self.names, self.values)

  def testGetIterator(self):
    """ResultRow's iterator yields all the values stored."""
    self.assertEquals(tuple(self.row), self.values)

  def testGetFieldnames(self):
    """ResultRow's names property returns a list of all fieldnames stored."""
    self.assertEquals(self.row.names, self.names)

  def testGetItems(self):
    """ResultRow's item property return a list of all item pairs as tuples."""
    self.assertEquals(
        self.row.items(), zip(self.names, self.values))
    self.assertEquals(
        dict(self.row.items()), dict(zip(self.names, self.values)))


class ResultRowEquality(unittest.TestCase):
  """Ensure ResultRow compares properly to other instances and objects."""
  def setUp(self):
    """Set up a persistent test environment."""
    self.names = ['name', 'nationality', 'age']
    self.values = ('Elmer', 'Dutch', 24)
    self.row = sqlresult.ResultRow(self.names, self.values)

  def testEqualityWithResultRow(self):
    """ResultRow is equal to another ResultRow with the same contents."""
    other = sqlresult.ResultRow(self.names, self.values)
    self.assertNotEqual(id(self.row), id(other))
    self.assertEquals(self.row, other)

  def testNonEqualityWithNonResultRow(self):
    """ResultRow is not equal to a tuple or list with the same contents."""
    self.assertNotEqual(self.row, self.values)
    self.assertNotEqual(self.row, list(self.values))

  def testNonEqualityWithDifferentNames(self):
    """ResultRow is not equal to a ResultRow with different fieldnames."""
    names_copy = self.names[:]
    names_copy[1] = 'not the same'
    other_names = sqlresult.ResultRow(names_copy, self.values)
    self.assertNotEqual(self.row, other_names)

  def testNonEqualityWithDifferentValues(self):
    """ResultRow is not equal to a ResultRow with different values."""
    values_copy = list(self.values)
    values_copy[1] = 'Bob'
    other_values = sqlresult.ResultRow(self.names, values_copy)
    self.assertNotEqual(self.row, other_values)

  def testNonEqualityWithDifferentSize(self):
    """ResultRow is not equal to a ResultSet with a different length."""
    self.names.append('animal')
    values_copy = list(self.values)
    values_copy.append('pink ponies')
    bigger = sqlresult.ResultRow(self.names, values_copy)
    self.assertNotEqual(self.row, bigger)
    self.assertNotEqual(bigger, self.row)


class ResultSetBasicOperation(unittest.TestCase):
  """Ensure basic functionality and usability."""
  def setUp(self):
    """Set up a persistent test environment."""
    self.fields = ('first', 'second', 'third', 'fourth')
    self.result = tuple(tuple(2 ** i for i in range(j, j + 4))
                        for j in range(0, 13, 4))

  def testFalseWhenEmpty(self):
    """ResultSet is boolean False when there's all but a result."""
    result = sqlresult.ResultSet(query='Lorem Ipsum dolor sit amet.',
                                 charset='latin1',
                                 result=(),
                                 fields=self.fields,
                                 affected=1,
                                 insertid=1)
    self.assertFalse(result)

  def testTrueWhenFilled(self):
    """ResultSet is boolean True when it has a result stored."""
    result = sqlresult.ResultSet(query='',
                                 charset='',
                                 result=self.result,
                                 fields=self.fields,
                                 affected=0,
                                 insertid=0)
    self.assertTrue(result)

if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
