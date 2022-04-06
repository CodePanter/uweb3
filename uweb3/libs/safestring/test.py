#!/usr/bin/python3
"""Tests for the safestring code"""
__author__ = 'Jan Klopper (jan@underdark.nl)'
__version__ = 0.1

# default modules
import unittest

#custom modules
from uweb3.libs.safestring import URLsafestring, SQLSAFE, HTMLsafestring, URLqueryargumentsafestring, JSONsafestring, EmailAddresssafestring, Basesafestring

class BasesafestringMethods(unittest.TestCase):
  def test_creation_str(self):
    with self.assertRaises(NotImplementedError) as context:
      str(Basesafestring('foo'))
    self.assertEqual(NotImplementedError, type(context.exception))

  def test_creation_repr(self):
    with self.assertRaises(NotImplementedError) as context:
      repr(Basesafestring('foo'))
    self.assertEqual(NotImplementedError, type(context.exception))


class TestHTMLStringMethods(unittest.TestCase):
  def test_init(self):
    testdata = HTMLsafestring('foo<test>')
    self.assertEqual(testdata, 'foo<test>')

  def test_init_unsafe(self):
    testdata = HTMLsafestring('foo<test>', unsafe=True)
    self.assertEqual(testdata, 'foo&lt;test&gt;')

  def test_addition(self):
    testdata = HTMLsafestring('foo') + '<b>test'
    self.assertEqual(testdata, 'foo&lt;b&gt;test')

  def test_addition_quotes(self):
    testdata = HTMLsafestring('foo') + '"test"'
    self.assertEqual(testdata, 'foo&quot;test&quot;')

  def test_addition_same(self):
    testdata = HTMLsafestring('foo<test>') + HTMLsafestring('foo<test>')
    self.assertEqual(testdata, 'foo<test>foo<test>')

  def test_addition_same_escaped(self):
    testdata = HTMLsafestring('foo') + '<test>'
    testdata = testdata + HTMLsafestring('foo<test>')
    self.assertEqual(testdata, 'foo&lt;test&gt;foo<test>')

  def test_addition_other(self):
    testdata = HTMLsafestring('foo<test>')
    urlquery = URLqueryargumentsafestring('foo') + ' test test/test'
    self.assertEqual(testdata + urlquery, 'foo<test>foo test test/test')

  def test_format(self):
    testdata = HTMLsafestring('foo<test> {} test').format('<b>')
    self.assertEqual(testdata, 'foo<test> &lt;b&gt; test')

  def test_format_nested_safesametype(self):
    testdata = HTMLsafestring('test {} {}').format(
      '<b>', HTMLsafestring('<b>'))
    self.assertEqual(testdata, 'test &lt;b&gt; <b>')

  def test_format_nested_safeothertype(self):
    testdata = HTMLsafestring('test {} {}').format(
      '<b>', EmailAddresssafestring('<b>'))
    self.assertEqual(testdata, 'test &lt;b&gt; &lt;b&gt;')

  def test_format_keyword(self):
    testdata = HTMLsafestring('foo<test> {kw} test').format(kw='<b>')
    self.assertEqual(testdata, 'foo<test> &lt;b&gt; test')

  def test_join(self):
    """Tests to join two already safe list items"""
    testdata = HTMLsafestring('').join((HTMLsafestring('<b>'),
                                        HTMLsafestring('<b>')))
    self.assertEqual(testdata, '<b><b>')
    self.assertIsInstance(testdata, HTMLsafestring)

  def test_join_unsafe(self):
    """Test a join over possibly insafe and safe strings combined"""
    testdata = HTMLsafestring('').join(('<b>',
                                        HTMLsafestring('<b>')))
    self.assertEqual(testdata, '&lt;b&gt;<b>')
    self.assertIsInstance(testdata, HTMLsafestring)


class TestJSonStringMethods(unittest.TestCase):
  def test_addition(self):
    testdata = JSONsafestring('foo') + '"test"'
    self.assertEqual(testdata, 'foo"\\"test\\""')

class TestURLqueryargumentsafestringMethods(unittest.TestCase):
  def test_addition(self):
    testdata = URLqueryargumentsafestring('foo') + 'test test/test'
    self.assertEqual(testdata, 'footest+test%2Ftest')


class TestURLsafestringMethods(unittest.TestCase):
  def test_headerinjection(self):
    """See if we correctly clean up header injection attemps"""
    testdata = URLsafestring('https://underdark.nl/somefile\n\nlocation: http://attacker.nl', unsafe=True)
    self.assertEqual(str(testdata), 'https://underdark.nl/somefile')

  def test_validurlunwisechars(self):
    url = 'http://mw1.google.com/mw-earth-vectordb/kml-samples/gp/seattle/gigapxl/$[level]/r$[y]_c$[x].jpg#fragment'
    testdata = URLsafestring(url, unsafe=True)
    self.assertEqual(str(testdata), url)

class TestEmailAddresssafestringMethods(unittest.TestCase):
  def test_unsafe_init(self):
    """See if we correctly clean up header injection attemps"""
    testdata = EmailAddresssafestring('jan@underdark.nl\nbcc: victim@otherhost.com', unsafe=True)
    self.assertEqual(testdata, 'jan@underdark.nl')

class TestSQLSAFEMethods(unittest.TestCase):
  def test_user_supplied_safe_value(self):
    user_supplied_safe_object = SQLSAFE("SELECT * FROM users WHERE username = 'username\t'")
    self.assertEqual(user_supplied_safe_object, "SELECT * FROM users WHERE username = 'username\t'")
    self.assertIsInstance(user_supplied_safe_object, SQLSAFE)

  def test_escaping_wrong_values_type(self):
    with self.assertRaises(ValueError):
      self.assertRaises(SQLSAFE("""SELECT * FROM users WHERE username = ?""", values=["username'"], unsafe=True))

  def test_escaping_uneven_replacements_and_values(self):
    with self.assertRaises(ValueError):
      self.assertRaises(SQLSAFE("""SELECT * FROM users WHERE username = ?""", values=["username'", "test"], unsafe=True))
      self.assertRaises(SQLSAFE("""SELECT * FROM users WHERE username = ? AND name=?""", values=["username'"], unsafe=True))

  def test_escaping(self):
    testdata = SQLSAFE("""SELECT * FROM users WHERE username = ?""", values=("username'",), unsafe=True)
    self.assertEqual(testdata, "SELECT * FROM users WHERE username = 'username\\''")
    testdata = SQLSAFE("""SELECT * FROM users WHERE username = ?""", values=('username"',), unsafe=True)
    self.assertEqual(testdata, "SELECT * FROM users WHERE username = 'username\\\"'")
    testdata = SQLSAFE("""SELECT * FROM users WHERE username = ? AND ? """, values=('username"', "password"), unsafe=True)

  def test_concatenation(self):
    testdata = SQLSAFE("""SELECT * FROM users WHERE username = ?""", values=("username'",), unsafe=True)
    other = "AND firstname='test'"
    self.assertEqual(testdata + other, "SELECT * FROM users WHERE username = 'username\\'' AND firstname=\\'test\\'")
    testdata = SQLSAFE("""SELECT * FROM users WHERE username = ?""", values=('username"',), unsafe=True)
    other = "AND firstname='test'"
    self.assertEqual(testdata + other, "SELECT * FROM users WHERE username = 'username\\\"' AND firstname=\\'test\\'")

  def test_unescape_wrong_type(self):
    """Validate if the string we are trying to unescape is part of an SQLSAFE instance"""
    testdata = SQLSAFE("""SELECT * FROM users WHERE username = ?""", values=("username'",), unsafe=True)
    with self.assertRaises(ValueError):
      self.assertRaises(testdata.unescape('whatever'))

  def test_correct_escape_character(self):
    """Validate that all characters are escaped as expected"""
    self.assertEqual(SQLSAFE.sanitize('\0', with_quotes=False), '\\0')
    self.assertEqual(SQLSAFE.sanitize('\b', with_quotes=False), '\\b')
    self.assertEqual(SQLSAFE.sanitize('\t', with_quotes=False), '\\t')
    self.assertEqual(SQLSAFE.sanitize('\n', with_quotes=False), '\\n')
    self.assertEqual(SQLSAFE.sanitize('\r', with_quotes=False), '\\r')
    self.assertEqual(SQLSAFE.sanitize('\x1a', with_quotes=False), '\\Z')
    self.assertEqual(SQLSAFE.sanitize('"', with_quotes=False), '\\"')
    self.assertEqual(SQLSAFE.sanitize('\'', with_quotes=False), '\\\'')
    self.assertEqual(SQLSAFE.sanitize('\\', with_quotes=False), '\\\\')

  def test_unescape(self):
    """Validate that the string is converted back to the original after escaping and unescaping"""
    testdata = SQLSAFE("""SELECT * FROM users WHERE username = ?""", values=("username\t \t",), unsafe=True)
    self.assertEqual(testdata, "SELECT * FROM users WHERE username = 'username\\t \\t'")
    self.assertEqual(testdata.unescape(testdata), "SELECT * FROM users WHERE username = 'username\t \t'")


if __name__ == '__main__':
    unittest.main()
