"""This file holds all the decorators we use in this project."""

import codecs
from datetime import datetime
import hashlib
import pickle
import pytz
import json
import time

import uweb3
from uweb3 import model
from uweb3.request import IndexedFieldStorage

def loggedin(f):
  """Decorator that checks if the user requesting the page is logged in based on set cookie."""
  def wrapper(*args, **kwargs):
    if not args[0].user:
      return args[0].RequestLogin()
    return f(*args, **kwargs)
  return wrapper

def checkxsrf(f):
  """Decorator that checks the user's XSRF.
  The function will compare the XSRF in the user's cookie and in the
  (post) request.
  """
  def _clear_form_data(pagemaker):
    method = pagemaker.req.method.lower()
    # Set an attribute in the pagemaker that holds the form data on an invalid XSRF validation
    pagemaker.invalid_xsrf_data = getattr(pagemaker, method)
    # Remove the form data from the PageMaker
    setattr(pagemaker, method, IndexedFieldStorage())
    # Remove the form data from the Request class
    pagemaker.req.vars[method] = IndexedFieldStorage()
    if 'files' in pagemaker.req.vars:
      pagemaker.req.vars['files'] = {}
    return pagemaker

  def wrapper(*args, **kwargs):
    if args[0].req.method != "GET":
      if args[0].invalid_xsrf_token:
        _clear_form_data(args[0])
        return args[0].XSRFInvalidToken()
    return f(*args, **kwargs)
  return wrapper

def Cached(maxage=None, verbose=False, handler=None, *t_args, **t_kwargs):
  """Decorator that wraps checks the cache table for a cached page.
  The function will see if we have a recent cached output for this call,
  or if one is being created as we speak.
  Use by adding the decorator module and flagging a pagemaker function with
  it.
  from pages import decorators
  @decorators.Cached(60)
  def mypage()

  Arguments:
    #TODO: Make handler an argument instead of a kwd since it is required?
    @ handler: class CustomClass(model.Record, model.CachedPage)
      This is some sort of custom mixin class that we use to store our cached page in the database
    % maxage: int(60)
      Cache time in seconds.
    % verbose: bool(False)
      Insert html comment with cache information.
  Raises:
    KeyError
  """
  def cache_decorator(f):
    def wrapper(*args, **kwargs):
      if not handler:
        raise KeyError("A handler is required for storing this page into the database.")
      create = False
      name = f.__name__
      modulename = f.__module__
      handler.Clean(args[0].connection, maxage)
      requesttime = time.time()
      time.clock()
      sleep = 0.3
      maxsleepinterval = 2
      try:  # see if we have a cached version thats not too old
        data = handler.FromSignature(args[0].connection,
                                              maxage,
                                              name, modulename,
                                              json.dumps(args[1:]),
                                              json.dumps(kwargs))
        if verbose:
          data = '%s<!-- cached %ds ago -->' % (
                                             pickle.loads(codecs.decode(data['data'].encode(), "base64")),
                                             data['age'])
        else:
          data = pickle.loads(codecs.decode(data['data'].encode(), "base64"))
      except model.CurrentlyWorking:  # we dont have anything fresh enough, but someones working on it
        age = 0
        while age < maxage:  # as long as there's no output, we should try periodically until we have waited too long
          time.sleep(sleep)
          age = (time.time() - requesttime)
          try:
            data = handler.FromSignature(args[0].connection,
                                                  maxage,
                                                  name, modulename,
                                                  json.dumps(args[1:]),
                                                  json.dumps(kwargs))
            break
          except Exception:
            sleep = min(sleep*2, maxsleepinterval)
        try:
          data = pickle.loads(codecs.decode(data['data'].encode(), "base64"))
          if verbose:
            data += '<!-- waited for fresh content for %s seconds -->' % age
        except NameError:
          create = True
      except uweb3.model.NotExistError:  # we don't have anything fresh enough, lets create
        create = True
      if create:
        try:
          now = str(pytz.utc.localize(datetime.utcnow()))[0:19]
          # create the db row for this call, let other processes know we are working on it.
          cache = handler.Create(args[0].connection, {
            'name': name,
            'modulename': modulename,
            'args': json.dumps(args[1:]),
            'kwargs': json.dumps(kwargs),
            'creating': now,
            'created': now
            })
          data = f(*args, **kwargs)
          cache['data'] = codecs.encode(pickle.dumps(data), "base64").decode()
          # update the created time to now, as we are done.
          cache['created'] = str(pytz.utc.localize(datetime.utcnow()))[0:19]
          cache['creating'] = None
          cache.Save()
          if verbose:
            data += '<!-- Freshly generated -->'
        except Exception: #This is probably a pymysql Error. or db collision, whilst unfortunate, we wont break the page on this
          pass
      return data
    return wrapper
  return cache_decorator

def ContentType(content_type):
  """Decorator that wraps and returns sets the contentType."""
  def content_type_decorator(f):
    def wrapper(*args, **kwargs):
      pageresult = f(*args, **kwargs) or {}
      if not isinstance(pageresult, uweb3.Response):
        return uweb3.Response(pageresult,
                              content_type=content_type)
      if isinstance(pageresult, uweb3.Response):
        pageresult.content_type = content_type
      args[0].req.content_type = content_type
      return pageresult
    return wrapper
  return content_type_decorator

def CSP(resourcetype, urls, append=True):
  """Decorator that injects a new CSP allowed source into the current csp output."""
  def csp_decorator(f):
    def wrapper(*args, **kwargs):
      args[0]._SetCsp(resourcetype, urls, append)
      return f(*args, **kwargs) or {}
    return wrapper
  return csp_decorator

def TemplateParser(template, *t_args, **t_kwargs):
  """Decorator that wraps and returns the output.

  The output is wrapped in a templateparser call if its not already something
  that we prepared for direct output to the client.
  """
  def template_decorator(f):
    def wrapper(*args, **kwargs):
      pageresult = f(*args, **kwargs) or {}
      if not isinstance(pageresult, (str, uweb3.Response, uweb3.Redirect)):
        return args[0].parser.Parse(template, **pageresult)
      return pageresult
    return wrapper
  return template_decorator
