#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""µWeb3 request module."""

# Standard modules
import cgi
import sys
import urllib
import io
from urllib.parse import parse_qs, parse_qsl
import io as stringIO
import http.cookies as cookie
import re
import json

# uWeb modules
from . import response

MAX_COOKIE_LENGTH = 4096
MAX_REQUEST_BODY_SIZE = 20000000 #20MB

class CookieTooBigError(Exception):
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


class Request:
  def __init__(self, env, logger, errorlogger):
    self.env = env
    self.headers = dict(self.headers_from_env(env))
    self._out_headers = []
    self._out_status = 200
    self._response = None
    self.charset = "utf-8"
    self.method = self.env['REQUEST_METHOD']
    self.vars = {
        'cookie': {
            name: value.value
            for name, value in Cookie(self.env.get('HTTP_COOKIE')).items()
        },
        'get': QueryArgsDict(parse_qs(self.env['QUERY_STRING'])),
    }
    self.env['host'] = self.headers.get('Host', '').strip().lower()
    self.logger = logger
    self.errorlogger = errorlogger
    self.noparse = self.headers.get('accept', '').lower() == 'application/json'

    if self.method in ('POST', 'PUT', 'DELETE'):
      request_body_size = 0
      try:
        request_body_size = int(self.env.get('CONTENT_LENGTH', 0))
      except Exception:
        pass
      request_payload = self.env['wsgi.input'].read(min(request_body_size, MAX_REQUEST_BODY_SIZE))
      self.input = request_payload
      self.env['mimetype'] = self.env.get('CONTENT_TYPE', '').split(';')[0]

      if self.env['mimetype'] == 'application/json':
        try:
          self.vars[self.method.lower()] = json.loads(request_payload)
        except (json.JSONDecodeError, ValueError):
          pass
      elif self.env['mimetype'] == 'multipart/form-data':
        boundary = self.env.get('CONTENT_TYPE', '').split(';')[1].strip().split('=')[1]
        request_payload = request_payload.split(b'--%s' % boundary.encode(self.charset))
        self.vars['files'] = {}
        fields = []
        for item in request_payload:
          item = item.lstrip()
          if item.startswith(b'Content-Disposition: form-data'):
            nl = 0
            prevnl = 0
            itemlength = len(item)
            name = filename = ContentType = charset = None
            while nl < itemlength:
              nl = item.index(b"\n", prevnl+len(b"\n"))
              header = item[prevnl:nl]
              prevnl = nl
              if not header.strip():
                content = item[nl:].strip()
                break
              directives = header.strip().split(b';')
              for directive in directives:
                directive = directive.lstrip()
                if directive.startswith(b'name='):
                  name = directive.split(b'=', 1)[1][1:-1].decode(self.charset)
                  if name == '_charset_': # default charset default case
                    self.charset = item[nl:].strip()
                    break
                if directive.startswith(b'filename='):
                  filename = directive.split(b'=', 1)[1][1:-1].decode(self.charset)
                if directive.startswith(b'Content-Type='):
                  ContentType = directive.split(b'=', 1)[1].decode(self.charset).split(";")
                  if len(ContentType) > 1:
                    if ContentType[1].startswith('charset'):
                      charset = ContentType[1].split('=')[1]
                    if ContentType[0].startswith('content-type'):
                      contenttype = ContentType[0].split(':')[1].strip()
            if charset:
              content = content.decode(charset)
            elif not ContentType:
              try:
                content = content.decode(charset or self.charset)
              except:
                pass
            if filename:
              self.vars['files'][name] = {'filename': filename,
                                          'ContentType': ContentType,
                                          'content': content}
            else:
              fields.append('%s=%s' % (name, content))
        self.vars[self.method.lower()] = IndexedFieldStorage(stringIO.StringIO('&'.join(fields)),
             environ={'REQUEST_METHOD': 'POST'})
      else:
        self.vars[self.method.lower()] = IndexedFieldStorage(stringIO.StringIO(request_payload.decode(self.charset)),
             environ={'REQUEST_METHOD': 'POST'})

  @property
  def path(self):
    return self.env['PATH_INFO']

  @property
  def response(self):
    if self._response is None:
      self._response = response.Response(headers=self._out_headers)
    return self._response

  def Redirect(self, location, httpcode=307):
    REDIRECT_PAGE = ('<!DOCTYPE html><html><head><title>Page moved</title></head>'
                     '<body>Page moved, please follow <a href="{}">this link</a>'
                     '</body></html>').format(location)

    headers = {'Location': location}
    if self.response.headers.get('Set-Cookie'):
      headers['Set-Cookie'] = self.response.headers.get('Set-Cookie')
    return response.Response(
      content=REDIRECT_PAGE,
      content_type=self.response.headers.get('Content-Type', 'text/html'),
      httpcode=httpcode,
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
    if isinstance(value, (str)) and len(value.encode('utf-8')) >= MAX_COOKIE_LENGTH:
      raise CookieTooBigError("Cookie is larger than %d bytes and wont be set" % MAX_COOKIE_LENGTH)

    new_cookie = Cookie({key: value})
    if 'max_age' in attrs:
      attrs['max-age'] = attrs.pop('max_age')
    new_cookie[key].update(attrs)
    if 'samesite' not in attrs and 'secure' not in attrs:
      try: # only supported from python 3.8 and up
        attrs['samesite'] = 'Lax' # set default to LAX for no secure (eg, local) sessions.
      except http.cookies.CookieError:
        pass
    self.AddHeader('Set-Cookie', new_cookie[key].OutputString())

  def AddHeader(self, name, value):
    if name == 'Set-Cookie':
      if not self.response.headers.get('Set-Cookie'):
        self.response.headers['Set-Cookie'] = [value]
        return
      self.response.headers['Set-Cookie'].append(value)
      return
    self.response.AddHeader(name, value)

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
    for field, value in parse_qsl(self.fp.read(self.length),
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

  def __repr__(self):
    return "{%s}" % ','.join("'%s': '%s'" % (k, v if len(v) > 1 else v[0]) for k, v in self.iteritems())

  @property
  def __dict__(self):
    return {
        key: value if len(value) > 1 else value[0]
        for key, value in self.iteritems()
    }


class QueryArgsDict(dict):
  def getfirst(self, key, default=None):
    """Returns the first value for the requested key, or a fallback value."""
    try:
      return self[key][0]
    except KeyError:
      return default

  def getlist(self, key):
    """Returns a list with all values that were given for the requested key.

    N.B. If the given key does not exist, an empty list is returned.
    """
    try:
      return self[key]
    except KeyError:
      return []


def return_real_remote_addr(env):
  """Returns the remote ip-address,
  if there is a proxy involved it will take the last IP addres from the HTTP_X_FORWARDED_FOR list
  """
  try:
    return env['HTTP_X_FORWARDED_FOR'].split(',')[-1].strip()
  except KeyError:
    return env['REMOTE_ADDR']
