#!/usr/bin/python3
"""uWeb3 PageMaker class and its various Mixins."""

import datetime
import logging
import mimetypes
import os
import pyclbr
import sys
import threading
import time
from base64 import b64encode
from pymysql import Error as pymysqlerr

import uweb3
from uweb3.model import SecureCookie

from .. import response, templateparser
from .new_login import Users

RFC_1123_DATE = '%a, %d %b %Y %T GMT'


class ReloadModules(Exception):
  """Signals the handler that it should reload the pageclass"""


class CacheStorage(object):
  """A (semi) persistent storage for the PageMaker."""
  def __init__(self):
    super(CacheStorage, self).__init__()
    self._dict = {}
    self._lock = threading.RLock()

  def __contains__(self, key):
    return key in self._dict

  def Del(self, key):
    """Removes the given key from the persistent storage.

    N.B. if the key was not in the persistent storage, no error is raised.
    """
    with self._lock:
      try:
        del self._dict[key]
      except KeyError:
        pass  # If a key is not in the storage, consider this a success

  def Get(self, key, *default):
    """Returns the current value for `key`, or the `default` if it doesn't."""
    with self._lock:
      if len(default) > 1:
        raise ValueError('Only one default value accepted')
      try:
        return self._dict[key]
      except KeyError:
        if default:
          return default[0]
        raise

  def Set(self, key, value):
    """Sets the `key` in the dictionary storage to `value`."""
    self._dict[key] = value

  def SetDefault(self, key, default=None):
    """Returns the value for `key` or sets it to `default` if it doesn't exist.

    Arguments:
      @ key: obj
        The key to retrieve from the dictionary storage.
      @ default: obj ~~ None
        The default new value for the given key if it doesn't exist yet.
    """
    with self._lock:
      return self._dict.setdefault(key, default)


class MimeTypeDict(dict):
  """Dictionary that defines special behavior for mimetypes.

  Mimetypes (of typical form "type/subtype") are stored as (type, subtype) keys.
  This allows grouping of types to happen, and fallbacks to occur.

  The following is a typical complete MIMEType example:
    >>> mime_type_dict['text/html'] = 'HTML content'

  One could also define a default for the whole type, as follows:
    >>> mime_type_dict['text/*'] = 'Default'Exception
    >>> mime_type_dict['text/nonexistant']
    'Default'
  """
  def __init__(self, data=(), **kwds):
    super(MimeTypeDict, self).__init__()
    if data:
      self.update(data)
    if kwds:
      self.update(**kwds)

  @staticmethod
  def MimeSplit(mime):
    """Split up a MIMEtype in a type and subtype, return as tuple.

    When the subtype if undefined or '*', only the type is returned, as 1-tuple.
    """
    mime_type, _sep, mime_subtype = mime.lower().partition('/')
    if not mime_subtype or mime_subtype == '*':
      return mime_type,  # 1-tuple
    return mime_type, mime_subtype

  def __setitem__(self, mime, value):
    super(MimeTypeDict, self).__setitem__(self.MimeSplit(mime), value)

  def __getitem__(self, mime):
    parsed_mime = self.MimeSplit(mime)
    try:
      return super(MimeTypeDict, self).__getitem__(parsed_mime)
    except KeyError:
      try:
        return super(MimeTypeDict, self).__getitem__(parsed_mime[:1])
      except KeyError:
        raise KeyError('KeyError: %r' % mime)

  def get(self, mime, default=None):
    try:
      return self[mime]
    except KeyError:
      return default

  def update(self, data=None, **kwargs):
    """Update the dictionary with new values from another dictionary.

    Also takes values from an iterable object of pairwise data.
    """
    if data:
      try:
        for key, value in data.items():
          self[key] = value
      except AttributeError:
        # Argument data is not a proper dict, treat it as an iterable of tuples.
        for key, value in data:
          self[key] = value
    if kwargs:
      self.update(kwargs)

class BasePageMaker(object):
  """Provides the base pagemaker methods for all the html generators."""
  # Constant for persistent storage accross requests. This will be accessible
  # by all threads of the same application (in the same Python process).
  PERSISTENT = CacheStorage()
  # Base paths for templates and public data. These are used in the PageMaker
  # classmethods that set up paths specific for that pagemaker.
  PUBLIC_DIR = 'static'
  TEMPLATE_DIR = 'templates'
  _registery = []

  # Default Static() handler cache durations, per MIMEtype, in days
  CACHE_DURATION = MimeTypeDict({'text': 7, 'image': 30, 'application': 7})

  def __init__(self, req, config=None, secure_cookie_secret=None, executing_path=None):
    """sets up the template parser and database connections

    Arguments:
      @ req: request.Request
        The originating request, including environment, GET, POST and cookies.
      % config: dict ~~ None
        Configuration for the pagemaker, with database connection information
        and other settings. This will be available through `self.options`.
    """
    self.__SetupPaths(executing_path)
    self.req = req
    self.cookies = req.vars['cookie']
    self.get = req.vars['get']
    self.post = req.vars['post']
    self.options = config or {}
    self.persistent = self.PERSISTENT
    self.secure_cookie_connection = (self.req, self.cookies, secure_cookie_secret)
    # self.user = self._GetLoggedInUser()

  def _PostRequest(self, response):
    if response.status == '500 Internal Server Error':
      if not hasattr(self, 'connection_error'): #this is set when we try and create a connection but it failed
        self.connection_error = False
        if hasattr(self, 'connection'):
            if self.connection.open:
              self.connection.close()
              self.persistent.Del("__mysql")
    return response

  def XSRFInvalidToken(self, command):
    """Returns an error message regarding an incorrect XSRF token."""
    page_data = self.parser.Parse('403.html', error=command,
                                  **self.CommonBlocks('Invalid XSRF token'))
    return uweb3.Response(content=page_data, httpcode=403)

  # def _GetLoggedInUser(self):
  #   """Checks if user is logged in based on cookie"""
  #   scookie = SecureCookie(self.secure_cookie_connection)
  #   if not scookie.cookiejar.get('login'):
  #     return None
  #   try:
  #     user = scookie.cookiejar.get('login')
  #   except Exception:
  #     self.req.DeleteCookie('login')
  #     return None
  #   if not user:
  #     return None
  #   return Users(None, user)

  @classmethod
  def LoadModules(cls, default_routes='routes', excluded_files=('__init__', '.pyc')):
    """Loops over all .py files apart from some exceptions in target directory
    Looks for classes that contain pagemaker
    """
    bases = []
    routes = os.path.join(os.getcwd(), default_routes)
    for path, dirnames, filenames in os.walk(routes):
      for filename in filenames:
        name, ext = os.path.splitext(filename)
        if name not in excluded_files and ext not in excluded_files:
          f = os.path.relpath(os.path.join(os.getcwd(), default_routes, filename[:-3])).replace('/', '.')
          example_data = pyclbr.readmodule_ex(f)
          for name, data in example_data.items():
            if hasattr(data, 'super'):
              if 'PageMaker' in data.super[0]:
                module = __import__(f, fromlist=[name])
                bases.append(getattr(module, name))
    return bases

  def _PostInit(self):
    """Method that gets called for derived classes of BasePageMaker."""

  @classmethod
  def __SetupPaths(cls, executing_path):
    """This sets up the correct paths for the PageMaker subclasses.

    From the passed in `cls`, it retrieves the filename. Of that path, the
    directory is used as the working directory. Then, the module constants
    PUBLIC_DIR and TEMPLATE_DIR are used to define class constants from.
    """
    # Unfortunately, mod_python does not always support retrieving the caller
    # filename using sys.modules. In those cases we need to query the stack.
    # pylint: disable=W0212
    try:
      local_file = os.path.abspath(sys.modules[cls.__module__].__file__)
    except KeyError:
      # This happens for old-style mod_python solutions: The pages file is
      # imported through the mechanics of mod_pythoif '__mysql' not in self.persistent: (not package imports) and
      # isn't known in sys modules. We use the CPython implementation details
      # to get the correct executing file.
      frame = sys._getframe()
      initial = frame.f_code.co_filename
      # pylint: enable=W0212
      while initial == frame.f_code.co_filename:
        if not frame.f_back:
          break  # This happens during exception handling of DebuggingPageMaker
        frame = frame.f_back
      local_file = frame.f_code.co_filename
    cls.LOCAL_DIR = cls_dir = executing_path
    cls.PUBLIC_DIR = os.path.join(cls_dir, cls.PUBLIC_DIR)
    cls.TEMPLATE_DIR = os.path.join(cls_dir, cls.TEMPLATE_DIR)

  @property
  def parser(self):
    """Provides a templateparser.Parser instance.

    If the config file specificied a [templates] section and a `path` is
    assigned in there, this path will be used.
    Otherwise, the `TEMPLATE_DIR` will be used to load templates from.
    """
    if '__parser' not in self.persistent:
      self.persistent.Set('__parser', templateparser.Parser(
          self.options.get('templates', {}).get('path', self.TEMPLATE_DIR)))
    return self.persistent.Get('__parser')

  def InternalServerError(self, exc_type, exc_value, traceback):
    """Returns a plain text notification about an internal server error."""
    error = 'INTERNAL SERVER ERROR (HTTP 500) DURING PROCESSING OF %r' % (
                self.req.path)
    self.req.registry.logger.error(
        error, exc_info=(exc_type, exc_value, traceback))
    return response.Response(
        content=error, content_type='text/plain', httpcode=500)

  @staticmethod
  def Reload():
    """Raises `ReloadModules`, telling the Handler() to reload its pageclass."""
    raise ReloadModules('Reloading ... ')

  def _GetXSRF(self):
    if 'xsrf' in self.cookies:
      return self.cookies['xsrf']
    return None

  def CommonBlocks(self, title, page_id=None, scripts=None):
    """Returns a dictionary with the header and footer in it."""
    if not page_id:
      page_id = title.replace(' ', '_').lower()

    return {'header': self.parser.Parse(
                'header.html', title=title, page_id=page_id, user=self.user
                ),
            'footer': self.parser.Parse(
                'footer.html', year=time.strftime('%Y'), user=self.user,
                page_id=page_id, scripts=scripts
                ),
            'page_id': page_id,
            'xsrftoken': self._GetXSRF(),
            }


class DebuggerMixin(object):
  """Replaces the default handler for Internal Server Errors.

  This one prints a host of debugging and request information, though it still
  lacks interactive functions.
  """
  CACHE_DURATION = MimeTypeDict({})
  ERROR_TEMPLATE = templateparser.FileTemplate(os.path.join(
      os.path.dirname(__file__), 'http_500.html'))

  def _ParseStackFrames(self, stack):
    """Generates list items for traceback information.

    Each traceback item contains the file- and function name, the line numer
    and the source that belongs with it. For each stack frame, the local
    variables are also added to it, allowing proper analysis to happen.

    This most likely doesn't need overriding / redefining in a subclass.

    Arguments:
      @ stack: traceback.stack
        The stack frames to return analysis on.

    Yields:
      str: Template-parsed HTML with frame information.
    """
    frames = []
    while stack:
      frame = stack.tb_frame
      frames.append({'file': os.path.abspath(frame.f_code.co_filename),
                     'scope': frame.f_code.co_name,
                     'locals': frame.f_locals,
                     'source': self._SourceLines(
                         frame.f_code.co_filename, frame.f_lineno)})
      stack = stack.tb_next
    return reversed(frames)

  @staticmethod
  def _SourceLines(filename, line_num, context=3):
    """Yields the offending source line, and `context` lines of context.

    Arguments:
      @ filename: str
        The filename (path) of which we should print lines of source.
      @ line_num: int
        The line number for the offending line.
      % context: int ~~ 3
        Number of lines context, before and after the offending line.

    Yields:
      str: Templated list-item for a source code line.
    """
    import linecache
    for line_num in range(line_num - context, line_num + context + 1):
      yield line_num, linecache.getline(filename, line_num)

  def InternalServerError(self, exc_type, exc_value, traceback):
    """Returns a HTTP 500 response with detailed failure analysis."""
    self.req.registry.logger.error(
        'INTERNAL SERVER ERROR (HTTP 500) DURING PROCESSING OF %r',
        self.req.path, exc_info=(exc_type, exc_value, traceback))
    exception_data = {
        'cookies': self.cookies,
        'environ': self.req.env,
        'query_args': self.get,
        'post_data': self.post,
        'error_for_error': False,
        'exc': {'type': exc_type, 'value': exc_value,
                'traceback': self._ParseStackFrames(traceback)}}
    try:
      return response.Response(
          self.ERROR_TEMPLATE.Parse(**exception_data), httpcode=500)
    except Exception:
      exc_type, exc_value, traceback = sys.exc_info()
      self.req.registry.logger.critical(
          'INTERNAL SERVER ERROR (HTTP 500) DURING PROCESSING OF ERROR PAGE',
          exc_info=(exc_type, exc_value, traceback))
      exception_data['error_for_error'] = True
      exception_data['orig_exc'] = exception_data['exc']
      exception_data['exc'] = {'type': exc_type, 'value': exc_value,
                               'traceback': self._ParseStackFrames(traceback)}
      return response.Response(
          self.ERROR_TEMPLATE.Parse(**exception_data), httpcode=500)

class MongoMixin(object):
  """Adds MongoDB support to PageMaker."""
  @property
  def mongo(self):
    """Returns a MongoDB database connection."""
    if '__mongo' not in self.persistent:
      import pymongo
      mongo_config = self.options.get('mongo', {})
      connection = pymongo.connection.Connection(
          host=mongo_config.get('host'),
          port=mongo_config.get('port'))
      if 'database' in mongo_config:
        self.persistent.Set('__mongo', connection[mongo_config['database']])
      else:
        self.persistent.Set('__mongo', connection)
    return self.persistent.Get('__mongo')


class SqlAlchemyMixin(object):
  """Adds MysqlAlchemy connection to PageMaker."""

  @property
  def engine(self):
    if '__sql_alchemy' not in self.persistent:
      from sqlalchemy import create_engine
      mysql_config = self.options['mysql']
      engine = create_engine('mysql://{username}:{password}@{host}/{database}'.format(
          username=mysql_config.get('user'),
          password=mysql_config.get('password'),
          host=mysql_config.get('host', 'localhost'),
          database=mysql_config.get('database')), pool_size=5, max_overflow=0)
      self.persistent.Set('__sql_alchemy', engine)
    return self.persistent.Get('__sql_alchemy')

  @property
  def session(self):
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker()
    Session.configure(bind=self.engine, expire_on_commit=False)
    return Session()

class MysqlMixin(object):
  """Adds MySQL support to PageMaker."""
  @property
  def connection(self):
    """Returns a MySQL database connection."""
    try:
      if '__mysql' not in self.persistent:
        from underdark.libs.sqltalk import mysql
        mysql_config = self.options['mysql']
        self.persistent.Set('__mysql', mysql.Connect(
            host=mysql_config.get('host', 'localhost'),
            user=mysql_config.get('user'),
            passwd=mysql_config.get('password'),
            db=mysql_config.get('database'),
            charset=mysql_config.get('charset', 'utf8'),
            debug=DebuggerMixin in self.__class__.__mro__))
      return self.persistent.Get('__mysql')
    except Exception as e:
      self.connection_error = True
      raise e



class SqliteMixin(object):
  """Adds SQLite support to PageMaker."""
  @property
  def connection(self):
    """Returns an SQLite database connection."""
    if '__sqlite' not in self.persistent:
      from underdark.libs.sqltalk import sqlite
      self.persistent.Set('__sqlite', sqlite.Connect(
          self.options['sqlite']['database']))
    return self.persistent.Get('__sqlite')

class SmorgasbordMixin(object):
  """Provides multiple-database connectivity.

  This enables a developer to use a single 'connection' property (`bord`) which
  can be used for regular relation database and MongoDB access. The caller will
  be given the relation database connection, unless Smorgasbord is aware of
  the caller's needs for another database connection.
  """
  class Connections(dict):
    """Connection autoloading class for Smorgasbord."""
    def __init__(self, pagemaker):
      super(SmorgasbordMixin.Connections, self).__init__()
      self.pagemaker = pagemaker

    def __getitem__(self, key):
      """Returns the requested database connection type.

      If the database connection type isn't locally available, it is retrieved
      using one of the _Load* methods.
      """
      try:
        return super(SmorgasbordMixin.Connections, self).__getitem__(key)
      except KeyError:
        return self.setdefault(key, getattr(self, '_Load%s' % key.title())())

    def _LoadMongo(self):
      """Returns the PageMaker's MongoDB connection."""
      return self.pagemaker.mongo

    def _LoadRelational(self):
      """Returns the PageMaker's relational database connection."""
      return self.pagemaker.connection

  @property
  def bord(self):
    """Returns a Smorgasbord of autoloading database connections."""
    if '__bord' not in self.persistent:
      from .. import model
      self.persistent.Set('__bord', model.Smorgasbord(
          connections=SmorgasbordMixin.Connections(self)))
    return self.persistent.Get('__bord')


# ##############################################################################
# Classes for public use (wildcard import)
#
class SqAlchemyPageMaker(SqlAlchemyMixin, BasePageMaker):
  """The basic PageMaker class, providing MySQL support."""

class PageMaker(MysqlMixin, BasePageMaker):
  """The basic PageMaker class, providing MySQL support."""

class DebuggingPageMaker(DebuggerMixin, PageMaker):
  """The same basic PageMaker, with added debugging on HTTP 500."""
