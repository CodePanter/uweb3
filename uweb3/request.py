#!/usr/bin/python2.6
"""uWeb3 request module."""

# Standard modules
import cgi
import sys
import urllib
from cgi import parse_qs
try:
  # python 2
  import cStringIO as stringIO
  import Cookie as cookie
except ImportError:
  # python 3
  import io as stringIO
  import http.cookies as cookie
import re
import json
# uWeb modules
from . import response
from werkzeug.formparser import parse_form_data
from werkzeug.datastructures import MultiDict


class CookieToBigError(Exception):
  """Error class for cookie when size is bigger than 4096 bytes"""

class Cookie(cookie.SimpleCookie):
  """Cookie class that uses the most specific value for a cookie name.

  According to RFC2965 (http://tools.ietf.org/html/rfc2965):
      If multiple cookies satisfy the criteria above, they are ordered in
      the Cookie header such that those with more specific Path attributes
      precede those with less specific.  Ordering with respect to other
      attributes (e.g., Domain) is unspecified.

  This class adds this behaviour to cookie parsing. That is, a key:value pair
  WILL NOT overwrite an already existing (and thus more specific) pair.

  N.B.: this class assumes the given cookie to follow the standards outlined in
  the RFC. At the moment (2011Q1) this assumption proves to be correct for both
  Chromium (and likely Webkit in general) and Firefox. Other browsers have not
  been tested, and might possibly deviate from the suggested standard.
  As such, it's recommended not to re-use the cookie name with different values
  for different paths.
  """
  # Unfortunately this works by redefining a private method.
  def _BaseCookie__set(self, key, real_value, coded_value):
    """Inserts a morsel into the Cookie, strictly on the first occurrance."""
    if key not in self:
      morsel = cookie.Morsel()
      morsel.set(key, real_value, coded_value)
      dict.__setitem__(self, key, morsel)


class PostDictionary(MultiDict):
  """ """
  #TODO: Add basic uweb functions

  def getfirst(self, key, default=None):
    """Returns the first item out of the list from the given key

    Arguments:
      @ key: str
      % default: any
    """
    items = dict(self.lists())
    try:
      return items[key][0]
    except KeyError:
      return default

  def getlist(self, key):
    """Returns a list with all values that were given for the requested key.

    N.B. If the given key does not exist, an empty list is returned.
    """
    items = dict(self.lists())
    try:
      return items[key]
    except KeyError:
      return []

class Request(object):
  def __init__(self, env, registry):
    self.env = env
    self.headers = dict(self.headers_from_env(env))
    self.registry = registry
    self._out_headers = []
    self._out_status = 200
    self._response = None
    self.method = self.env['REQUEST_METHOD']
    # `self.vars` setup, will contain keys 'cookie', 'get' and 'post'
    self.vars = {'cookie': dict((name, value.value) for name, value in
                                Cookie(self.env.get('HTTP_COOKIE')).items()),
                 'get': PostDictionary(cgi.parse_qs(self.env.get('QUERY_STRING'))),
                 'post': PostDictionary()}
    self.env['host'] = self.headers.get('Host', '')

    if self.method == 'POST':
      stream, form, files = parse_form_data(self.env)
      if self.env['CONTENT_TYPE'] == 'application/json':
        try:
          request_body_size = int(self.env.get('CONTENT_LENGTH', 0))
        except (ValueError):
          request_body_size = 0
        request_body = self.env['wsgi.input'].read(request_body_size)
        data = json.loads(request_body)
        self.vars['post'] = PostDictionary(MultiDict(data))
      else:
        self.vars['post'] = PostDictionary(form)
        for f in files:
          self.vars['post'][f] = files.get(f)

  @property
  def path(self):
    return self.env['PATH_INFO']

  @property
  def response(self):
    if self._response is None:
      self._response = response.Response()
    return self._response

  def Redirect(self, location, http_code=307):
    REDIRECT_PAGE = ('<!DOCTYPE html><html><head><title>Page moved</title></head>'
                   '<body>Page moved, please follow <a href="{}">this link</a>'
                   '</body></html>').format(location)

    headers = {'Location': location}
    if self.response.headers.get('Set-Cookie'):
      headers['Set-Cookie'] = self.response.headers.get('Set-Cookie')
    return response.Response(
      content=REDIRECT_PAGE,
      content_type=self.response.headers.get('Content-Type', 'text/html'),
      httpcode=http_code,
      headers=headers
      )

  def headers_from_env(self, env):
    for key, value in env.items():
      if key.startswith('HTTP_'):
        yield key[5:].lower().replace('_', '-'), value

  def AddCookie(self, key, value, **attrs):
    """Adds a new cookie header to the response.

    Arguments:
      @ key: str
        The name of the cookie.
      @ value: str
        The actual value to store in the cookie.
      % expires: str ~~ None
        The date + time when the cookie should expire. The format should be:
        "Wdy, DD-Mon-YYYY HH:MM:SS GMT" and the time specified in UTC.
        The default means the cookie never expires.
        N.B. Specifying both this and `max_age` leads to undefined behavior.
      % path: str ~~ '/'
        The path for which this cookie is valid. This default ('/') is different
        from the rule stated on Wikipedia: "If not specified, they default to
        the domain and path of the object that was requested".
      % domain: str ~~ None
        The domain for which the cookie is valid. The default is that of the
        requested domain.
      % max_age: int
        The number of seconds this cookie should be used for. After this period,
        the cookie should be deleted by the client.
        N.B. Specifying both this and `expires` leads to undefined behavior.
      % secure: boolean
        When True, the cookie is only used on https connections.
      % httponly: boolean
        When True, the cookie is only used for http(s) requests, and is not
        accessible through Javascript (DOM).
    """
    if isinstance(value, (str)):
      if len(value.encode('utf-8')) >= 4096:
        raise CookieToBigError("Cookie is larger than 4096 bytes and wont be set")

    new_cookie = Cookie({key: value})
    if 'max_age' in attrs:
      attrs['max-age'] = attrs.pop('max_age')
    new_cookie[key].update(attrs)
    self.AddHeader('Set-Cookie', new_cookie[key].OutputString())

  def AddHeader(self, name, value):
    if name == 'Set-Cookie':
      if not self.response.headers.get('Set-Cookie'):
        self.response.headers['Set-Cookie'] = [value]
        return
      self.response.headers['Set-Cookie'].append(value)

  def DeleteCookie(self, name):
    """Deletes cookie by name

    Arguments
    @ name: str
    """
    self.AddHeader('Set-Cookie', '{}=deleted; expires=Thu, 01 Jan 1970 00:00:00 GMT;'.format(name))


class IndexedFieldStorage(cgi.FieldStorage):
  """Adaption of cgi.FieldStorage with a few specific changes.

  Notable differences with cgi.FieldStorage:
    1) `environ.QUERY_STRING` does not add to the returned FieldStorage
       This way we maintain a strict separation between POST and GET variables.
    2) Field names in the form 'foo[bar]=baz' will generate a dictionary:
         foo = {'bar': 'baz'}
       Multiple statements of the form 'foo[%s]' will expand this dictionary.
       Multiple occurrances of 'foo[bar]' will result in unspecified behavior.
    3) Automatically attempts to parse all input as UTF8. This is the proposed
       standard as of 2005: http://tools.ietf.org/html/rfc3986.
  """
  FIELD_AS_ARRAY = re.compile(r'(.*)\[(.*)\]')
  def iteritems(self):
    return ((key, self.getlist(key)) for key in self)

  def items(self):
    return list(self.iteritems())

  def read_urlencoded(self):
    indexed = {}
    self.list = []
    for field, value in cgi.parse_qsl(self.fp.read(self.length),
                                      self.keep_blank_values,
                                      self.strict_parsing):
      if self.FIELD_AS_ARRAY.match(str(field)):
        field_group, field_key = self.FIELD_AS_ARRAY.match(field).groups()
        indexed.setdefault(field_group, cgi.MiniFieldStorage(field_group, {}))
        indexed[field_group].value[field_key] = value
      else:
        self.list.append(cgi.MiniFieldStorage(field, value))
    self.list = list(indexed.values()) + self.list
    self.skip_lines()


class CustomByteLikeObject(object):
  def __init__(self, data):
    self.data = data

  def read(self, length=None):
    if length:
      return self.data[0:length]
    else:
      return self.data

  def readline(self, *args):
    return self.data

def ParseForm(file_handle, environ, json=False):
  """Returns an IndexedFieldStorage object from the POST data and environment.

  This small wrapper is necessary because cgi.FieldStorage assumes that the
  provided file handles supports .readline() iteration. File handles as provided
  by BaseHTTPServer do not support this, so we need to convert them to proper
  stringIO objects first.
  """
  #TODO see if we need to encode in utf8 or is ascii is fine based on the headers
  # print(file_handle.read(int(environ['CONTENT_LENGTH'])).decode('ascii'))
  # data = sys.stdin.read()
  if json:
    #We already decoded the JSON and turned into a urlquerystring
    environ['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
    files = CustomByteLikeObject(file_handle.encode())
  else:
    files = CustomByteLikeObject(file_handle.read(int(environ['CONTENT_LENGTH'])))

  return IndexedFieldStorage(fp=files, environ=environ, keep_blank_values=1)


