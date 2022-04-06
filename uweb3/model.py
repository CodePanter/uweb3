#!/usr/bin/python3
"""uWeb3 model base classes."""

# Standard modules
import base64
import configparser
import datetime
import os
import sys
import hashlib
import json
import secrets



class Error(Exception):
  """Superclass used for inheritance and external exception handling."""

class DatabaseError(Error):
  """Superclass for errors returned by the database backend."""

class CurrentlyWorking(Error):
  """Caching error"""

class BadFieldError(DatabaseError):
  """A field in the record could not be written to the database."""

class AlreadyExistError(Error):
  """The resource already exists, and cannot be created twice."""

class NotExistError(Error):
  """The requested or provided resource doesn't exist or isn't accessible."""

class PermissionError(Error):
  """The entity has insufficient rights to access the resource."""


class SettingsManager(object):
  def __init__(self, filename=None, path=None):
    """Creates a ini file with the child class name

    Arguments:
      % filename: str, optional
      Name of the file, optionally without the extension will default to .ini
      If not filename is given the class.__name__ will be used to look for the config file in the path
      % path: str, Optional
      Path to the config file, will be used if filename is relative, eg does not start with '/'
    """
    self.options = None
    extension = '' if filename and filename.endswith(('.ini', '.conf')) else '.ini'

    if filename:
      self.filename = f"{filename[:1].lower() + filename[1:] + extension}"
    else:
      self.filename = self.TableName() + extension

    if path and not filename.startswith('/'):
      self.file_location = os.path.join(path, self.filename)
    else:
      self.file_location = self.filename
    self.__CheckPermissions()
    if not os.path.isfile(self.file_location):
      os.mknod(self.file_location)

    self.mtime = None
    self.config = configparser.ConfigParser()
    self.Read()

  @classmethod
  def TableName(cls):
    """Returns the 'database' table name for the SettingsManager class.

    If this is not explicitly defined by the class constant `_TABLE`, the return
    value will be the class name with the first letter lowercased.
    We stick to the same naming scheme as for more table like connectors even
    though we use files instead of tables in this class.
    """
    if cls._TABLE:
      return cls._TABLE
    name = cls.__name__
    return name[0].lower() + name[1:]

  def __CheckPermissions(self):
    """Checks if SettingsManager can read/write to file."""
    if not os.path.isfile(self.file_location):
      return True
    if not os.access(self.file_location, os.R_OK):
      raise PermissionError(f"SettingsManager missing permissions to read file: {self.file_location}")
    if not os.access(self.file_location, os.W_OK):
      raise PermissionError(f"SettingsManager missing permissions to write to file: {self.file_location}")

  def Create(self, section, key, value):
    """Creates a section or/and key = value

    Arguments:
      @ section: str
        Name of the section you want to create or append key = value to
      @ key: str
        Name of the key you want to create
      @ value: str

    Raises:
      ValueError
    """
    if not self.options.get(section):
      self.config.add_section(section)
    else:
      if self.config[section].get(key):
        raise ValueError("key already exists")

    self.config.set(section, key, value)
    self._Write(False)
    self.mtime = None

  def Read(self):
    """Reads the config file and populates the options member
    It uses the mtime to see if any re-reading is required

    Returns True if changes where detected, False if no re-read was needed."""
    if not self.mtime:
      curtime = os.path.getmtime(self.file_location)
      if self.mtime and self.mtime == curtime:
        return False
      self.config.read(self.file_location)
      self.options = self.config._sections
      self.mtime = curtime
    return True

  def Update(self, section, key, value):
    """Updates ini file
    After update reads file again and updates options attribute

    Arguments:
      @ section: str
      @ key: str
      @ value: str

    Raises
      TypeError: Option values must be string
    """
    if not self.options.get(section):
      self.config.add_section(section)
    self.config.set(section, key, value)
    self._Write()
    self.mtime = None

  def Delete(self, section, key=None):
    """Delete sections/keys from the INI file
    Be aware, deleting a section that is not empty will remove all keys from that
    given section

    Arguments:
      @ section: str
        Name of the section
      @ key: None / str
        Name of the key you want to remove
        If set to None (default) it will delete the supplied section
    Raises:
      configparser.NoSectionError
    """
    if key:
      self.config.remove_option(section, key)
    if not key:
      self.config.remove_section(section)
    self._Write()
    self.mtime = None
    return True

  def _Write(self, reread=True):
    """Internal function to store the current config to file"""
    with open(self.file_location, 'w') as configfile:
      self.config.write(configfile)
    if reread:
      return self.Read()
    return True


class SecureCookie(object):
  """The secureCookie class works just like other data abstraction classes,
  except that it stores its data in client side cookies that are signed with a
  server side secret to avoid tampering by the end-user.

  Subclass this class with your own class to create signed cookie objects. The
  name for your class will reflect the name for the cookie in the cookie.
  """

  HASHTYPE = 'ripemd160'
  _TABLE = None
  _CONNECTOR = 'signedCookie'

  def __init__(self, connection):
    """Create a new SecureCookie instance."""
    self.connection = connection
    self.request, self.cookies, self.cookie_salt = self.connection
    self.debug = self.connection.debug
    self._rawcookie = None
    if self.debug:
      print('current cookies (unvalidated) for request:', self.cookies)

  def __str__(self):
    """Returns the cookie's value if it was valid and untampered with."""
    return str(self.rawcookie)

  @classmethod
  def TableName(cls):
    """Returns the 'database' table name for the SecureCookie class.

    If this is not explicitly defined by the class constant `_TABLE`, the return
    value will be the class name with the first letter lowercased.
    We stick to the same naming scheme as for more table like connectors even
    though we use cookies instead of tables in this class.
    """
    if cls._TABLE:
      return cls._TABLE
    name = cls.__name__
    return name[0].lower() + name[1:]

  @property
  def rawcookie(self):
    """Reads the request cookie, checks if it was signed correctly and return
    the value, or returns False"""
    if not self._rawcookie is None:
      return self._rawcookie
    name = self.TableName()
    if name in self.cookies and self.cookies[name]:
      isValid, value = self.__ValidateCookieHash(self.cookies[name])
      if isValid:
        self._rawcookie = value
        return value
      if self.debug:
        print('Secure cookie "%s" was tampered with and thus invalid. content was: %s ' % (name, self.cookies[name]))
    if self.debug:
      print('Secure cookie "%s" was not present.' % name)
    self._rawcookie = ''
    return self._rawcookie

  @classmethod
  def Create(cls, connection, data, **attrs):
    """Creates a secure cookie

    Arguments:
      @ data: dict
        Needs to have a key called __name with value of how you want to name the 'table'
      % only_return_hash: boolean
        If this is set it will just return the hash of the cookie. This is used to
        validate the cookies hash
      % update: boolean
        Used to update the cookie. Updating actually means deleting and setting a new
        one. This attribute is used by the update method from this class
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

    Raises:
      ValueError: When cookie with name already exists
    """
    cls.connection = connection
    cls.request, cls.cookies, cls.cookie_salt = connection
    name = cls.TableName()
    cls._rawcookie = data

    hashed = cls.__CreateCookieHash(cls, data)
    cls.cookies[name] = hashed
    cls.request.AddCookie(name, hashed, **attrs)
    return cls

  def Update(self, data, **attrs):
    """"Updates a secure cookie
    Keep in mind that the actual cookie's value is avilable from the next
    request. After calling this method it will update the cookie attribute to
    the new value however.

    Arguments:
      @ data: dict
        Needs to have a key called __name with value of how you want to name the 'table'
      % only_return_hash: boolean
        If this is set it will just return the hash of the cookie. This is used to
        validate the cookies hash
      % update: boolean
        Used to update the cookie. Updating actually means deleting and setting a new
        one. This attribute is used by the update method from this class
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

    Raises:
      ValueError: When no cookie with given name found
    """
    name = self.TableName()
    if not self.rawcookie:
      raise ValueError("No valid cookie with name `{}` found".format(name))
    self._rawcookie = data
    hashed = self.__CreateCookieHash(data)
    self.cookies[name] = hashed
    self.request.AddCookie(name,  hashed, **attrs)

  def Delete(self):
    """Deletes cookie based on name
    The cookie is no longer in the session after calling this method
    """
    name = self.TableName()
    self.request.DeleteCookie(name)
    self._rawcookie = None

  def __CreateCookieHash(self, data):
    data = str(json.dumps(data))
    h = hashlib.new(self.HASHTYPE)
    h.update((data + self.cookie_salt).encode('utf-8'))
    return '{}+{}'.format(h.hexdigest(), self._encode(data))

  def __ValidateCookieHash(self, cookie):
    """Takes a cookie and validates it

    Arguments:
      @ str: A hashed cookie from the `__CreateCookieHash` method
    """
    if not cookie:
      return None
    try:
      data = json.loads(self._decode(cookie.rsplit('+', 1)[1]))
    except Exception:
      print('Cookie contents could not be loaded as Json')
      return (False, None)

    if cookie == self.__CreateCookieHash(data):
      return (True, data)
    print('Cookie contents could not be verified as hash is different')
    return (False, None)

  @staticmethod
  def _encode(data):
    """Encode cookie values per RFC 6265
    http://www.ietf.org/rfc/rfc6265.txt

    We elect to only encode the control chars for the cookie spec, and not the
    whole cookie content.
    """
    return data.replace('%', "%25").replace('"', "%22").replace(",", "%27").replace('{', "%7B").replace('}', "%7D").replace('=', "%3D")

  @staticmethod
  def _decode(data):
    """decode cookie values per RFC 6265
    http://www.ietf.org/rfc/rfc6265.txt

    We elect to only decode the control chars for the cookie spec, and not the
    whole cookie content.
    """
    return data.replace("%22", '"').replace("%27", ",").replace("%7B", '{').replace("%7D", '}').replace("%3D", '=').replace("%25", '%')

# Record classes have many methods, this is not an actual problem.
# pylint: disable=R0904
class BaseRecord(dict):
  """Basic database record wrapping class.

  This allows structured database manipulation for applications. Supported
  features include:
  * Loading a record from Primary Key;
  * Deleting a record by Primary Key;
  * Deleting an existing open record;
  * Listing all records of the current type;
  * Calculating the minimum changed set and storing this to the database.
  """
  _LOAD_METHOD = 'FromPrimary'
  _PRIMARY_KEY = 'ID'
  _TABLE = None

  def __init__(self, connection, record, run_init_hook=True):
    """Initializes a BaseRecord instance.

    Arguments:
      @ connection: object
        The database connection to use for further queries.
      @ record: mapping
        A field:value mapping of the database record information.
      % run_init_hook: bool ~~ True
        States whether or not the `_PostInit()` hook should be run after
        the other initialization steps have completed.
    """
    super(BaseRecord, self).__init__(record)
    if not hasattr(BaseRecord, '_SUBTYPES'):
      # Adding classes at runtime is pretty rare, but fails this code.
      BaseRecord._SUBTYPES = dict(RecordTableNames())
    self.connection = connection
    self._record = self._DataRecord()
    # _PostInit hook should run after making a live copy of the data, so that
    # mirrored data transforms between _PostInit and _PreSave will not trigger
    # the record to be updated on saves where the data hasn't actually changed.
    if run_init_hook:
      self._PostInit()

  def __eq__(self, other):
    """Simple equality comparison for database objects.

    To compare equal, two objects must:
      1) Be of the same type;
      2) Have the same primary key which is NOT None;
      3) Have the same content.

    In the case that the compared objects have foreign relations, these  will be
    compared as well (recursively). If only one of the objects has foreign
    relations loaded, only the primary key value will be compared to the value
    in the other Record.
    """
    if type(self) != type(other):
      return False  # Types must be the same.
    elif not (self.key == other.key is not None):
      return False  # Records should have the same non-None primary key value.
    elif len(self) != len(other):
      return False  # Records must contain the same number of objects.
    for key, value in self.items():
      other_value = other[key]
      if isinstance(value, BaseRecord) != isinstance(other_value, BaseRecord):
        # Only one of the two is a BaseRecord instance
        if (isinstance(value, BaseRecord) and value.key != other_value or
            isinstance(other_value, BaseRecord) and other_value.key != value):
          return False
      elif value != other_value:
        return False
    return True

  def __hash__(self):
    """Returns the hashed value of the key."""
    return hash(self.key)

  def __int__(self):
    """Returns the integer key value of the Record.

    For record objects where the primary key value is not (always) an integer,
    this function will raise an error in the situations where it is not.
    """
    key_val = self._ValueOrPrimary(self.key)
    if not isinstance(key_val, (int)):
      # We should not truncate floating point numbers.
      # Nor turn strings of numbers into an integer.
      raise ValueError('The primary key is not an integral number.')
    return key_val

  def __ne__(self, other):
    """Returns the proper inverse of __eq__."""
    # Without this, the non-equal checks used in __eq__ will not work,
    # and the  `!=` operator would not be the logical inverse of `==`.
    return not self == other

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, super(BaseRecord, self).__repr__())

  def __str__(self):
    return '%s({%s})' % (
        self.__class__.__name__,
        ', '.join('%r: %r' % item for item in self.items()))

  def copy(self):
    """Returns a shallow copy of the Record that is a new functional Record."""
    return self.__class__(
        self.connection, super(BaseRecord, self).copy(), run_init_hook=False)

  # ############################################################################
  # Rich comparators
  #
  def __gt__(self, other):
    """Index of this record is greater than the other record's.

    This requires both records to be of the same record class."""
    if type(self) == type(other):
      return self.key > other.key
    return NotImplemented

  def __ge__(self, other):
    """Index of this record is greater than, or equal to, the other record's.

    This requires both records to be of the same record class."""
    if type(self) == type(other):
      return self.key >= other.key
    return NotImplemented

  def __lt__(self, other):
    """Index of this record is smaller than the other record's.

    This requires both records to be of the same record class."""
    if type(self) == type(other):
      return self.key < other.key
    return NotImplemented

  def __le__(self, other):
    """Index of this record is smaller than, or equal to, the other record's.

    This requires both records to be of the same record class."""
    if type(self) == type(other):
      return self.key <= other.key
    return NotImplemented

  # ############################################################################
  # Hooks for things to run before and after creating and updating records
  #
  def _PreCreate(self, _cursor):
    """Hook that runs before creating (inserting) a Record in the database.

    Typically you would verify values of the Record in this step, or transform
    the data for database-safe insertion. If the data is transformed here, this
    transformation should be reversed in `_PostCreate()`.

    Returning False from this method will halt the creation of the record.
    """
    return True

  def _PreSave(self, _cursor):
    """Hook that runs before saving (updating) a Record in the database.

    Typically you would verify values of the Record in this step, or transform
    the data for database-safe insertion. If the data is transformed here, this
    transformation should be reversed in `_PostSave()`.

    Returning False from this method will halt the updating of the record.
    """
    return True

  def _PostInit(self):
    """Hook that runs after initializing a Record instance.

    This typically runs on every instance, but can be suppressed. Records that
    are newly created using the `Create()` classmethod will NOT have this hook
    run. They should use `_PreCreate()` and `_PostCreate()` methods.

    Any transforms done after creating and saving should likely be present here.
    """

  def _PostCreate(self, _cursor):
    """Hook that runs after creating (inserting) a Record in the database.

    Any transforms that were performed on the data should be reversed here.
    """

  def _PostSave(self, _cursor):
    """Hook that runs after saving (updating) a Record in the database.

    Any transforms that were performed on the data should be reversed here.
    """

  def _PreDelete(self):
    """Hook that runs before deleting a Record in the database.
    Returning False from this method will halt the deletion of the record.
    """
    return True

  def _PostDelete(self):
    """Hook that runs after deleting a Record in the database."""

  # ############################################################################
  # Base record functionality methods, to be implemented by subclasses.
  # Some methods have a generic implementation, but may need customization,
  #
  @classmethod
  def Create(cls, connection, record):
    """Creates a proper record object and stores it to the database.

    After storing it to the database, the live object is returned

    Arguments:
      @ connection: object
        Database connection to use for the created record..
      @ record: mapping
        The record data to write to the database.

    Returns:
      BaseRecord: the record that was created from the initiation mapping.
    """
    raise NotImplementedError

  @classmethod
  def DeletePrimary(cls, connection, key):
    """Deletes a database record based on the primary key value.

    Arguments:
      @ connection: object
        Database connection to use.
      @ pkey_value: obj
        The value for the primary key field
    """
    raise NotImplementedError

  def Delete(self):
    """Deletes a loaded record based on `self.TableName` and `self.key`.

    For deleting an unloaded object, use the classmethod `DeletePrimary`.
    """
    if not self._PreDelete():
      return False
    self.DeletePrimary(self.connection, self.key)
    self._record.clear()
    self.clear()
    self._PostDelete()

  @classmethod
  def FromPrimary(cls, connection, pkey_value):
    """Returns the Record object that belongs to the given primary key value.

    Arguments:
      @ connection: object
        Database connection to use.
      @ pkey_value: obj
        The value for the primary key field

    Raises:
      NotExistError:
        There is no record that matches the given primary key value.

    Returns:
      Record: Database record abstraction class.
    """
    raise NotImplementedError

  @classmethod
  def List(cls, connection, conditions=None):
    """Yields a Record object for every table entry.

    Arguments:
      @ connection: object
        Database connection to use.
      % conditions: str / iterable ~~ None
        Optional query portion that will be used to limit the list of results

    Yields:
      Record: Database record abstraction class.
    """
    raise NotImplementedError

  def Save(self):
    """Saves the changes made to the record.

    This performs an update to the record, except when `create_new` if set to
    True, in which case the record is inserted.

    Arguments:
      % create_new: bool ~~ False
        Tells the method to create a new record instead of updating a current.
        This should be used when Save is called by the Create() method.
    """
    raise NotImplementedError

  @classmethod
  def _LoadAsForeign(cls, connection, relation_value, method=None):
    """Loads a record as a foreign relation of another.

    Defaults to using the _LOAD_METHOD defined on the class, but when
    provided the optional `method` argument, this named method is used instead.
    """
    if method is None:
      method = cls._LOAD_METHOD
    return getattr(cls, method)(connection, relation_value)

  # ############################################################################
  # Functions for tracking table and primary key values
  #
  def _Changes(self):
    """Returns the differences of the current state vs the last stored state."""
    sql_record = self._DataRecord()
    return {
        key: value
        for key, value in sql_record.items() if self._record.get(key) != value
    }

  def _DataRecord(self):
    """Returns a dictionary of the record's database values
    For any Record object present, its primary key value (`Record.key`) is used.
    """
    return {key: self._ValueOrPrimary(value) for key, value in super().items()}

  @staticmethod
  def _ValueOrPrimary(value):
    """Returns the value, or its primary key value if it's a Record."""
    while isinstance(value, BaseRecord):
      if hasattr(value, '_RECORD_KEY') and value._RECORD_KEY:
        value = value[value._RECORD_KEY]
      else:
        value = value.key
    return value

  @classmethod
  def TableName(cls):
    """Returns the database table name for the Record class.

    If this is not explicitly defined by the class constant `_TABLE`, the return
    value will be the class name with the first letter lowercased.
    """
    if cls._TABLE:
      return cls._TABLE
    name = cls.__name__
    return name[0].lower() + name[1:]

  # Pylint falsely believes this property is overwritten by its setter later on.
  # pylint: disable=E0202
  @property
  def key(self):
    """Returns the primary key for the object.

    This is used for the Save/Update methods, where foreign relations should be
    stored by their primary key.
    """
    if isinstance(self._PRIMARY_KEY, tuple):
      record = self._DataRecord()
      return tuple(record[key] for key in self._PRIMARY_KEY)
    return self.get(self._PRIMARY_KEY)
  # pylint: enable=E0202

  # Pylint doesn't understand property setters at all.
  # pylint: disable=E0102, E0202, E1101
  @key.setter
  def key(self, value):
    """Sets the value of the primary key."""
    if isinstance(value, tuple):
      if len(value) != len(self._PRIMARY_KEY):
        raise ValueError('Not enough values for compound key.')
      for key, key_val in zip(self._PRIMARY_KEY, value):
        self[key] = key_val
    else:
      self[self._PRIMARY_KEY] = value
  # pylint: enable=E0102, E0202, E1101

  Error = Error
  AlreadyExistError = AlreadyExistError
  NotExistError = NotExistError
  PermissionError = PermissionError


class Record(BaseRecord):
  """Extensions to the Record abstraction for relational database use."""
  _FOREIGN_RELATIONS = {}
  _CONNECTOR = 'mysql'
  SEARCHABLE_COLUMNS = []

  # ############################################################################
  # Methods enabling auto-loading
  #
  def GetRaw(self, field):
    """Returns the value of the field, suppressing auto-loading."""
    return super(Record, self).__getitem__(field)

  def __getitem__(self, field):
    """Returns the value corresponding to a given `field`.

    If a field represents a foreign relation, this will be delegated to
    the `_LoadForeign` method.
    """
    value = super(Record, self).__getitem__(field)
    return self._LoadForeign(field, value)

  def _LoadForeign(self, field, value):
    """Loads and returns objects referenced by foreign key.

    This is done by checking the `field` against the class' `_FOREIGN_RELATIONS`
    mapping. If a match is found, `_LoadForeignFromRelationsTable` is executed
    and its return value returned.

    If the `field` is not present in the class mapping, it will be checked
    against table names for each of the subclasses of Record. This mapping is
    maintained in `_SUBTYPES`. If a match is found, an instance of the
    corresponding class will replace the existing value, and will subsequently
    be returned.

    If the `field` is not present in either mapping, its value will remain
    unchanged, and returned as such.

    N.B. If the field name the same as the record's `TableName`, it will NOT be
    automatically resolved. The assumption is that the field will not contain a
    meaningful reference. This behavior can be altered by specifying the
    relation in the _FOREIGN_RELATIONS class constant.

    Arguments:
      @ field: str
        The field name to be checked for foreign references
      @ value: obj
        The current value for the field. This is used as lookup index in case
        of foreign references.

    Returns:
      obj: The value belonging to the given `field`. In case of resolved foreign
           references, this will be the referenced object. Else it's unchanged.
    """
    if value is None:
      return None
    elif not isinstance(value, BaseRecord):
      if field in self._FOREIGN_RELATIONS:
         value = self._LoadUsingForeignRelations(
            self._FOREIGN_RELATIONS[field], field, value)
      elif field == self.TableName():
        return value
      elif field in self._SUBTYPES:
        value = self._SUBTYPES[field]._LoadAsForeign(self.connection, value)
      self[field] = value
    return value

  def _LoadUsingForeignRelations(self, foreign_cls, field, value):
    """Loads and returns foreign relation based on given class (name).

    The action taken depends on the given `cls`. If the given class is None (or
    otherwise boolean false), no action will be taken, and the value will be
    returned unchanged.

    If the class is given as string, it will be loaded from the current module.
    It should be a proper subclass of Record, after which the current `value` is
    used to create a record using `cls._LoadAsForeign`.

    Arguments:
      @ foreign_cls: Record / str / dict
        The class name or actual type to create an instance from. Could also
        be a dictionary with `class` and `loader` keys that indicate class and
        method to use for loading foreign relations.
      @ field: str
        The field name to be checked for foreign references
      @ value: obj
        The current value for the field. This is used as lookup index in case
        of foreign references.

    Raises:
      ValueError: If the class name cannot be found, or the type is not a
                  subclass of Record.

    Returns:
      obj: The value belonging to the given `field`. In case of resolved foreign
           references, this will be the referenced object. Else it's unchanged.
    """
    def GetRecordClass(cls):
      """Returns the record class or loads it from its string name"""
      if isinstance(cls, str):
        try:
          cls = getattr(sys.modules[self.__module__], cls)
        except AttributeError:
          raise ValueError(
              'Bad _FOREIGN_RELATIONS map: Target %r not a class in %r' % (
                  cls, self.__module__))
      if not issubclass(cls, Record):
        raise ValueError('Bad _FOREIGN_RELATIONS map: '
                         'Target %r not a subclass of Record' % cls.__name__)
      return cls

    if foreign_cls is None:
      return value
    if type(foreign_cls) is dict:
      cls = GetRecordClass(foreign_cls['class'])
      loader = foreign_cls.get('loader')
      return cls._LoadAsForeign(self.connection, value, method=loader)
    return GetRecordClass(foreign_cls)._LoadAsForeign(self.connection, value)

  # ############################################################################
  # Override basic dict methods so that autoload mechanisms function on them.
  #
  def get(self, key, default=None):
    """Returns the value for `key` if its present, otherwise `default`."""
    try:
      return self[key]
    except KeyError:
      return default

  def pop(self, field, *default):
    """Pops the value corresponding to the field from the Record.

    If the field does not exist, either KeyError or an optional default value
    is returned instead.
    """
    try:
      value = self[field]
    except KeyError:
      if not default:
        raise
      return default[0]
    del self[field]
    return value

  def iteritems(self):
    """Yields all field+value pairs in the Record.

    N.B. This automatically resolves foreign references.
    """
    return ((key, self[key]) for key in self)

  def itervalues(self):
    """Yields all values in the Record, loading foreign references."""
    return (self[key] for key in self)

  def items(self):
    """Returns a list of field+value pairs in the Record.

    N.B. This automatically resolves foreign references.
    """
    return list(self.iteritems())

  def values(self):
    """Returns a list of values in the Record, loading foreign references."""
    return list(self.itervalues())

  # ############################################################################
  # Private methods to be used for development
  #
  @classmethod
  def _FromParent(cls, parent, relation_field=None, conditions=None,
                 limit=None, offset=None, order=None,
                 yield_unlimited_total_first=False):
    """Returns all `cls` objects that are a child of the given parent.

    This utilized the parent's _Children method, with either this class'
    TableName or the filled out `relation_field`.

    Arguments:
      @ parent: Record
        The parent for who children should be found in this class
      % relation_field: str ~~ cls.TableName()
        The fieldname in this class' table which relates to the parent's primary
        key. If not given, parent.TableName() will be used.
      % conditions: str / iterable ~~ None
        The extra condition(s) that should be applied when querying for records.
      % limit: int ~~ None
        Specifies a maximum number of items to be yielded. The limit happens on
        the database side, limiting the query results.
      % offset: int ~~ None
        Specifies the offset at which the yielded items should start. Combined
        with limit this enables proper pagination.
      % order: iterable of str/2-tuple
        Defines the fields on which the output should be ordered. This should be
        a list of strings or 2-tuples. The string or first item indicates the
        field, the second argument defines descending order
        (desc. if True).
      % yield_unlimited_total_first: bool ~~ False
        Instead of yielding only Record objects, the first item returned is the
        number of results from the query if it had been executed without limit.
    """
    if not isinstance(parent, Record):
      raise TypeError('parent argument should be a Record type.')
    relation_field = relation_field or parent.TableName()
    relation_value = parent.connection.EscapeValues(cls._ValueOrPrimary(parent))
    qry_conditions = ['`%s` = %s' % (relation_field, relation_value)]
    if conditions:
      if isinstance(conditions, str):
        qry_conditions.append(conditions)
      else:
        qry_conditions.extend(conditions)

    firstrow = yield_unlimited_total_first # set a flag to skip the linking of
    # the first row to our parent, as that will be the full record cound instead
    # of a record
    for record in cls.List(parent.connection, conditions=qry_conditions,
        limit=limit, offset=offset, order=order,
        yield_unlimited_total_first=yield_unlimited_total_first):
      if not firstrow:
        record[relation_field] = parent.copy()
      firstrow = False
      yield record

  def _Children(self, child_class, relation_field=None, conditions=None,
    limit=None, offset=None, order=None, yield_unlimited_total_first=False):
    """Returns all `child_class` objects related to this record.

    The table for the given `child_class` will be queried for all fields where
    the `relation_field` is the same as this record's primary key (`self.key`).

    These records will then be yielded as instances of the child class.

    Arguments:
      @ child_class: type (Record subclass)
        The child class whose objects should be found.
      % relation_field: str ~~ self.TableName()
        The fieldname in the `child_class` table which relates that table to the
        table for this record.
      % conditions: str / iterable ~~
        The extra condition(s) that should be applied when querying for records.
      % limit: int ~~ None
        Specifies a maximum number of items to be yielded. The limit happens on
        the database side, limiting the query results.
      % offset: int ~~ None
        Specifies the offset at which the yielded items should start. Combined
        with limit this enables proper pagination.
      % order: iterable of str/2-tuple
        Defines the fields on which the output should be ordered. This should be
        a list of strings or 2-tuples. The string or first item indicates the
        field, the second argument defines descending order (desc. if True).
      % yield_unlimited_total_first: bool ~~ False
        Instead of yielding only Record objects, the first item returned is the
        number of results from the query if it had been executed without limit.
    """
    # Delegating to let child class handle its own querying. These are methods
    # for development, and are private only to prevent name collisions.
    # pylint: disable=W0212
    return child_class._FromParent(
        self, relation_field=relation_field, conditions=conditions,
        limit=limit, offset=offset, order=order,
        yield_unlimited_total_first=yield_unlimited_total_first)

  def _DeleteChildren(self, child_class, relation_field=None):
    """Deletes all `child_class` objects related to this record.

    The table for the given `child_class` will be queried for all fields where
    the `relation_field` is the same as this record's primary key (`self.key`).

    Arguments:
      @ child_class: type (Record subclass)
        The child class whose objects should be deleted.
      % relation_field: str ~~ self.TableName()
        The fieldname in the `child_class` table which relates that table to the
        table for this record.
    """
    relation_field = relation_field or self.TableName()
    with self.connection as cursor:
      safe_key = self.connection.EscapeValues(self.key)
      cursor.Delete(table=child_class.TableName(),
                    conditions='`%s`=%s' % (relation_field, safe_key))

  @classmethod
  def _PrimaryKeyCondition(cls, connection, value):
    """Returns the primary key condition to be used."""
    if isinstance(cls._PRIMARY_KEY, tuple):
      if not isinstance(value, tuple):
        raise TypeError(
            'Compound keys should be loaded using a tuple of key values.')
      if len(value) != len(cls._PRIMARY_KEY):
        raise ValueError('Not enough values (%d) for compound key.', len(value))
      values = tuple(map(cls._ValueOrPrimary, value))
      return ' AND '.join('`%s` = %s' % (field, value) for field, value
                   in zip(cls._PRIMARY_KEY, connection.EscapeValues(values)))
    return '`%s`.`%s` = %s' % (
        cls.TableName(),
        cls._PRIMARY_KEY,
        connection.EscapeValues(cls._ValueOrPrimary(value)))

  def _RecordCreate(self, cursor):
    """Inserts the record's current values in the database as a new record.

    Upon success, the record's primary key is set to the result's insertid
    """
    try:
      values = self._DataRecord()
      # Compound key case
      if isinstance(self._PRIMARY_KEY, tuple):
        auto_inc_field = set(self._PRIMARY_KEY) - set(values)
        if auto_inc_field:
          raise ValueError('No value for compound key field(s): %s' % (
              ', '.join(map(repr, auto_inc_field))))
        return cursor.Insert(table=self.TableName(), values=values)
      # Single-column key case
      result = cursor.Insert(table=self.TableName(), values=values)
      if result.insertid:
        self._record[self._PRIMARY_KEY] = self.key = result.insertid
    except cursor.OperationalError as err_obj:
      if err_obj[0] == 1054:
        raise BadFieldError(err_obj[1])
      raise DatabaseError(err_obj)

  def _RecordUpdate(self, cursor):
    """Updates the existing database entry with the record's current values.

    The constraint with which the record is updated is the name and value of the
    Record's primary key (`self._PRIMARY_KEY` and `self.key` resp.)
    """
    try:
      if isinstance(self._PRIMARY_KEY, tuple):
        primary = tuple(self._record[key] for key in self._PRIMARY_KEY)
      else:
        primary = self._record[self._PRIMARY_KEY]
      cursor.Update(
          table=self.TableName(),
          values=self._Changes(),
          conditions=self._PrimaryKeyCondition(self.connection, primary))
    except KeyError:
      raise Error('Cannot update record without pre-existing primary key.')
    except cursor.OperationalError as err_obj:
      if err_obj[0] == 1054:
        raise BadFieldError(err_obj[1])
      raise DatabaseError(err_obj)

  def _SaveForeign(self, cursor):
    """Recursively saves all nested Record instances."""
    for value in super(Record, self).items():
      if isinstance(value, Record):
        # Accessing protected members of a foreign class. Also, the only means
        # of recursively saving the record tree without opening multiple
        # database transactions (which would lead to exceptions really fast).
        # pylint: disable=W0212
        value._SaveForeign(cursor)
        value._SaveSelf(cursor)

  def _SaveSelf(self, cursor):
    """Updates the existing database entry with the record's current values.

    The constraint with which the record is updated is the name and value of the
    Record's primary key (`self._PRIMARY_KEY` and `self.key` resp.)
    """
    self._PreSave(cursor)
    difference = self._Changes()
    if difference:
      self._RecordUpdate(cursor)
      self._record.update(difference)
    self._PostSave(cursor)

  # ############################################################################
  # Public methods for creation, deletion and storing Record objects.
  #
  @classmethod
  def Create(cls, connection, record):
    record = cls(connection, record, run_init_hook=False)
    with connection as cursor:
      # Accessing protected members of a foreign class.
      # pylint: disable=W0212
      record._PreCreate(cursor)
      record._RecordCreate(cursor)
      record._PostCreate(cursor)
    return record

  @classmethod
  def DeletePrimary(cls, connection, pkey_value):
    with connection as cursor:
      cursor.Delete(table=cls.TableName(),
                    conditions=cls._PrimaryKeyCondition(connection, pkey_value))

  @classmethod
  def FromPrimary(cls, connection, pkey_value):
    with connection as cursor:
      record = cursor.Select(
          table=cls.TableName(),
          conditions=cls._PrimaryKeyCondition(connection, pkey_value))
    if not record:
      raise NotExistError('There is no %r for primary key %r' % (
          cls.__name__, pkey_value))
    return cls(connection, record[0])

  @classmethod
  def List(cls, connection, conditions=None, limit=None, offset=None,
           order=None, yield_unlimited_total_first=False, search=None,
           tables=None, escape=True, fields=None, distinct=False):
    """Yields a Record object for every table entry.

    Arguments:
      @ connection: object
        Database connection to use.
      % conditions: str / iterable ~~ None
        Optional query portion that will be used to limit the list of results.
        If multiple conditions are provided, they are joined on an 'AND' string.
      % limit: int ~~ None
        Specifies a maximum number of items to be yielded. The limit happens on
        the database side, limiting the query results.
      % offset: int ~~ None
        Specifies the offset at which the yielded items should start. Combined
        with limit this enables proper pagination.
      % order: iterable of str/2-tuple
        Defines the fields on which the output should be ordered. This should be
        a list of strings or 2-tuples. The string or first item indicates the
        field, the second argument defines descending order (desc. if True).
      % yield_unlimited_total_first: bool ~~ False
        Instead of yielding only Record objects, the first item returned is the
        number of results from the query if it had been executed without limit.
      % search: str
        Specifies what string should be searched for in the default searchable
        database columns.
      % tables: str / iterable ~~ None
        Specifies what tables should be searched queried
      % escape: bool ~~ True
        Are conditions escaped?
      % fields: str / iterable ~~ *
        Specifies what fields should be returned
      % distinct: bool (optional).
        Performs a DISTINCT query if set to True.

    Yields:
      Record: Database record abstraction class.
    """
    if not tables:
      tables = [cls.TableName()]
    group = None
    if fields is None:
      fields = '%s.*' % cls.TableName()
    if search:
      group = '%s.%s' % (cls.TableName(), (cls.RecordKey() if getattr(cls, "RecordKey", None) else cls._PRIMARY_KEY))
      tables, searchconditions = cls._GetSearchQuery(connection, tables, search)
      if conditions:
        if type(conditions) == list:
          conditions.extend(searchconditions)
        else:
          searchconditions.append(conditions)
          conditions = searchconditions
      else:
        conditions = searchconditions
    cacheable = False
    if not offset or offset < 0:
      offset = 0
    if hasattr(cls, '_addToCache'):
      #TODO dont cache partial / multi-table objects
      cacheable = True
      connection.modelcache['_stats']['queries'].append('%s Record.List' % cls.TableName())
    with connection as cursor:
      records = cursor.Select(fields=fields,
                              table=tables, conditions=conditions,
                              limit=limit, offset=offset, order=order,
                              totalcount=yield_unlimited_total_first,
                              escape=escape, group=group, distinct=distinct)
    if yield_unlimited_total_first:
      yield records.affected
    records = [cls(connection, record) for record in list(records)]

    yield from records

    if cacheable:
      list(cls._cacheListPreseed(records))

  # SQL Records have foreign relations, saving needs an extra argument for this.
  # pylint: disable=W0221
  def Save(self, save_foreign=False):
    """Saves the changes made to the record.

    This expands on the base Save method, providing a save_foreign that will
    recursively update all nested records when set to True.

    Arguments:
      % save_foreign: bool ~~ False
        If set, each Record (subclass) contained by this one will be saved as
        well. This recursive saving triggers *before* this record itself will be
        saved. N.B. each record is saved using a separate transaction, meaning
        that a failure to save this object will *not* roll back child saves.
    """
    with self.connection as cursor:
      if save_foreign:
        self._SaveForeign(cursor)
      self._SaveSelf(cursor)
    return self
  # pylint: enable=W0221

  @classmethod
  def _GetSearchQuery(cls, connection, tables, search):
    """Extracts table information from the searchable columns list."""
    conditions = []
    like = 'like "%%%s%%"' % connection.EscapeValues(search.strip())[1:-1]
    searchconditions = []
    thistable = cls.TableName()
    for column in cls.SEARCHABLE_COLUMNS:
      if '.' not in column:
        searchconditions.append('`%s`.`%s` %s' % (thistable, column, like))
        continue
      classname, column = column.split('.', 1)
      othertable = cls._SUBTYPES[classname].TableName()
      if (othertable != thistable and
          othertable not in tables):
        fkey = cls._FOREIGN_RELATIONS.get(classname, False)
        key = othertable._PRIMARY_KEY
        if fkey and fkey.get('LookupKey', False):
          key = fkey.get('LookupKey')
        elif getattr(table, "RecordKey", None):
          key = othertable.RecordKey()
        # add the cross table join
        #TODO use referenced field, instead of just the othertable name
        conditions.append('`%s`.`%s` = `%s`.`%s' % (thistable,
            othertable,
            othertable,
            key))
        tables.append(othertable)
      searchconditions.append('`%s`.`%s` %s' % (othertable,
          column, like))

    conditions.append('(%s)' % ' or '.join(searchconditions))
    return tables, conditions

  def __json__(self, complete=True, recursive=True):
    """Returns a dictionary representation of the Record.

    Arguments:
      % complete: bool ~~ False
        Whether the foreign references on the object should all be resolved before
        converting the Record to a dictionary. Either way, existing resolved
        references will be represented as complete dictionaries.

      Returns:
        dict: dictionary representation of the record.
      """
    record_dict = {}
    record = self if complete else dict(record)
    for key, value in record.items():
      if isinstance(value, BaseRecord):
        if complete and recursive:
          record_dict[key] = value.__json__(complete=True, recursive=True)
        else:
          record_dict[key] = dict(value)
      else:
        record_dict[key] = value
    return record_dict


class VersionedRecord(Record):
  """Basic class for database table/record abstraction."""
  _LOAD_METHOD = 'FromIdentifier'
  _RECORD_KEY = None

  # ############################################################################
  # RecordKey method, analogous to TableName
  #
  @classmethod
  def RecordKey(cls):
    """Returns the record identifier fieldname.

    If this is not explicitly defined by the class constant `_RECORD_KEY`, the
    return value will be the class' TableName() with 'ID' appended.
    """
    if cls._RECORD_KEY is not None:
      return cls._RECORD_KEY
    return cls.TableName() + 'ID'

  # ############################################################################
  # Public methods for creation, deletion and storing Record objects.
  #
  @classmethod
  def FromIdentifier(cls, connection, identifier):
    """Returns the newest Record object that matches the given identifier.

    N.B. Newest is defined as 'last in lexicographical sort'.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      @ identifier: obj
        The value of the record key field

    Raises:
      NotExistError:
        There is no Record that matches the given identifier.

    Returns:
      Record: The newest record for the given identifier.
    """
    safe_id = connection.EscapeValues(identifier)

    with connection as cursor:
      record = cursor.Select(
          table=cls.TableName(), order=[(cls._PRIMARY_KEY, True)],
          conditions='`%s`=%s' % (cls.RecordKey(), safe_id), limit=1)
    if not record:
      raise NotExistError('There is no %r for identifier %r' % (
          cls.__name__, identifier))
    return cls(connection, record[0])

  @classmethod
  def List(cls, connection, conditions=None, limit=None, offset=None,
           order=None, yield_unlimited_total_first=False, search=None,
           tables=None, escape=True, fields=None):
    """Yields the latest Record for each versioned entry in the table.

    Arguments:
      @ connection: object
        Database connection to use.
      % conditions: str / iterable ~~ None
        Optional query portion that will be used to limit the list of results.
        If multiple conditions are provided, they are joined on an 'AND' string.
      % limit: int ~~ None
        Specifies a maximum number of items to be yielded. The limit happens on
        the database side, limiting the query results.
      % offset: int ~~ None
        Specifies the offset at which the yielded items should start. Combined
        with limit this enables proper pagination.
      % order: iterable of str/2-tuple
        Defines the fields on which the output should be ordered. This should
        be a list of strings or 2-tuples. The string or first item indicates the
        field, the second argument defines descending order (desc. if True).
      % yield_unlimited_total_first: bool ~~ False
        Instead of yielding only Record objects, the first item returned is the
        number of results from the query if it had been executed without limit.
      % search: str
        Specifies what string should be searched for in the default searchable
        database columns.
      % tables: str / iterable ~~ None
        Specifies what tables should be searched queried
      % escape: bool ~~ True
        Are conditions escaped?
      % fields: str / iterable ~~ *
        Specifies what fields should be returned

    Yields:
      Record: The Record with the newest version for each versioned entry.
    """
    if not tables:
      tables = [cls.TableName()]
    if fields:
      if fields != '*':
        if isinstance(fields, str):
          fields = connection.EscapeField(fields)
        else:
          fields = ', '.join(connection.EscapeField(fields))
    else:
      fields = "%s.*" % cls.TableName()
    if search:
      search = search.strip()
      tables, searchconditions = cls._GetSearchQuery(connection, tables, search)
      if conditions:
        if type(conditions) == list:
          conditions.extend(searchconditions)
        else:
          searchconditions.append(conditions)
          conditions = searchconditions
      else:
        conditions = searchconditions
    field_escape = connection.EscapeField if escape else lambda x: x
    if yield_unlimited_total_first and limit is not None:
      totalcount = 'SQL_CALC_FOUND_ROWS'
    else:
      totalcount = ''
    cacheable = False
    if hasattr(cls, '_addToCache'):
      #TODO dont cache partial / multi-table objects
      cacheable = True
      connection.modelcache['_stats']['queries'].append('%s VersionedRecord.List' % cls.TableName())
    with connection as cursor:
      records = cursor.Execute("""
          SELECT %(totalcount)s %(fields)s
          FROM %(tables)s
          JOIN (SELECT MAX(`%(primary)s`) AS `max`
                FROM `%(table)s`
                GROUP BY `%(record_key)s`) AS `versions`
              ON (`%(table)s`.`%(primary)s` = `versions`.`max`)
          WHERE %(conditions)s
          %(order)s
          %(limit)s
          """ % {'totalcount': totalcount,
                 'primary': cls._PRIMARY_KEY,
                 'record_key': cls.RecordKey(),
                 'fields': fields,
                 'table': cls.TableName(),
                 'tables': cursor._StringTable(tables, field_escape),
                 'conditions': cursor._StringConditions(conditions,
                                                      field_escape),
                 'order': cursor._StringOrder(order, field_escape),
                 'limit': cursor._StringLimit(limit, offset)})
    if yield_unlimited_total_first and limit is not None:
      with connection as cursor:
        records.affected = cursor._Execute('SELECT FOUND_ROWS()')[0][0]
      yield records.affected
    # turn sqltalk rows into model
    records = [cls(connection, record) for record in list(records)]
    yield from records
    if cacheable:
      list(cls._cacheListPreseed(records))

  @classmethod
  def Versions(cls, connection, identifier, conditions='1'):
    """Yields all versions for a given record identifier.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      % conditions: str
        Optional query portion that will be used to limit the list of results

    Yields:
      Record: One for each stored version for the identifier.
    """
    if isinstance(conditions, (list, tuple)):
      conditions = ' AND '.join(conditions)
    safe_id = connection.EscapeValues(identifier)
    with connection as cursor:
      records = cursor.Select(table=cls.TableName(),
                              conditions='`%s` = %s AND %s' % (
                                  cls.RecordKey(), safe_id, conditions))
    for record in records:
      yield cls(connection, record)

  # ############################################################################
  # Private methods to control VersionedRecord behaviour
  #
  @classmethod
  def _NextRecordKey(cls, cursor):
    """Returns the next record key to use, the previous (or zero) plus one."""
    return (cls._MaxRecordKey(cursor) or 0) + 1

  @classmethod
  def _MaxRecordKey(cls, cursor):
    """Returns the currently largest record key value."""
    last_key = cursor.Select(table=cls.TableName(), fields=cls.RecordKey(),
                             order=[(cls.RecordKey(), True)], limit=1)
    if last_key:
      return last_key[0][cls.RecordKey()]

  def _PreCreate(self, cursor):
    """Attaches a RecordKey to the Record if it doens't have one already.

    Before we create a new record, we need to acquire the next-in-line RecordKey
    if none has been provided. If one has been provided, we'll use that one.
    """
    if self.identifier is None:
      self.identifier = self._NextRecordKey(cursor)

  def _PreSave(self, cursor):
    """Before saving a record, reset the primary key value.

    This assures that we will not have a primary key conflict, though it does
    assume an AutoIncrement primary key field.
    """
    super(VersionedRecord, self)._PreSave(cursor)
    difference = self._Changes()
    if difference:
      self.key = None

  def _RecordUpdate(self, cursor):
    """All updates are handled as new inserts for the same Record Key."""
    difference = self._Changes()
    if difference:
      self._RecordCreate(cursor)

  # Pylint falsely believes this property is overwritten by its setter later on.
  # pylint: disable=E0202
  @property
  def identifier(self):
    """Returns the value of the version field of the record.

    This is used for the Save/Update methods, where foreign relations should be
    stored by their primary key.
    """
    return self.get(self.RecordKey())
  # pylint: enable=E0202

  # Pylint doesn't understand property setters at all.
  # pylint: disable=E0102, E0202, E1101
  @identifier.setter
  def identifier(self, value):
    """Sets the value of the primary key."""
    self[self.RecordKey()] = value
  # pylint: enable=E0102, E0202, E1101


class MongoRecord(BaseRecord):
  """Abstraction of MongoDB collection records."""
  _PRIMARY_KEY = '_id'
  _CONNECTOR = 'mongo'

  @classmethod
  def Collection(cls, connection):
    """Returns the collection that the MongoRecord resides in."""
    return getattr(connection, cls.TableName())

  @classmethod
  def Create(cls, connection, record):
    record = cls(connection, record, run_init_hook=False)
    # Accessing protected members of a foreign class.
    # pylint: disable=W0212
    record._PreCreate(None)
    record._StoreRecord()
    record._PostCreate(None)
    # pylint: enable=W0212
    return record

  @classmethod
  def DeletePrimary(cls, connection, pkey_value):
    collection = cls.Collection(connection)
    collection.remove({cls._PRIMARY_KEY: pkey_value})

  @classmethod
  def FromPrimary(cls, connection, pkey_value):
    from bson.objectid import ObjectId

    if not isinstance(pkey_value, ObjectId):
      pkey_value = ObjectId(pkey_value)
    collection = cls.Collection(connection)
    record = collection.find({cls._PRIMARY_KEY: pkey_value})
    if not record:
      raise NotExistError('There is no %r for primary key %r' % (
          cls.__name__, pkey_value))
    return cls(connection, record[0])

  @classmethod
  def List(cls, connection, conditions=None):
    for record in cls.Collection(connection).find(conditions or {}):
      yield cls(connection, record)

  def Save(self):
    changes = self._Changes()
    if changes:
      self._PreSave(None)
      self._StoreRecord()
      self._PostSave(None)
      self._record.update(changes)
    return self

  def _StoreRecord(self):
    self.key = self.Collection(self.connection).save(self._DataRecord())


def RecordTableNames():
  """Yields Record subclasses that have been defined outside this module.

  This is necessary to accurately perform automatic loading of foreign elements.
  There is one requirement to this, and that's that all subclasses of Record
  are loaded in memory by the time the first Record is instantiated, because
  this function will only be called once by default.
  """
  def GetSubTypes(cls, seen=None):
    """Recursively and depth-first retrieve subclasses of a given type."""
    seen = seen or set()
    # Pylint mistakenly believes there is no method __subclasses__
    # pylint: disable=E1101
    for sub in cls.__subclasses__():
    # pylint: enable=E1101
      if sub not in seen:
        seen.add(sub)
        yield sub
        yield from GetSubTypes(sub, seen)

  for cls in GetSubTypes(BaseRecord):
    # Do not yield subclasses defined in this module
    if cls.__module__ != __name__:
      yield cls.TableName(), cls


import functools

class CachedPage(object):
  """Abstraction class for the cached Pages table in the database."""

  MAXAGE = 61

  @classmethod
  def Clean(cls, connection, maxage=None):
    """Deletes all cached pages that are older than MAXAGE.

    An optional 'maxage' integer can be specified instead of MAXAGE.
    """
    with connection as cursor:
      cursor.Execute("""delete
        from
          %s
        where
          TIME_TO_SEC(TIMEDIFF(UTC_TIMESTAMP(), created)) > %d
          """ % (
          cls.TableName(),
          (cls.MAXAGE if maxage is None else maxage)
        ))

  @classmethod
  def FromSignature(cls, connection, maxage, name, modulename, args, kwargs):
    """Returns a cached page from the given signature."""
    with connection as cursor:
      cache = cursor.Execute("""select
          data,
          TIME_TO_SEC(TIMEDIFF(UTC_TIMESTAMP(), created)) as age,
          creating
        from
          %s
        where
          TIME_TO_SEC(TIMEDIFF(UTC_TIMESTAMP(), created)) < %d AND
          name = %s AND
          modulename = %s AND
          args = %s AND
          kwargs = %s
          order by created desc
          limit 1
          """ % (
        cls.TableName(),
        (cls.MAXAGE if maxage is None else maxage),
        connection.EscapeValues(name),
        connection.EscapeValues(modulename),
        connection.EscapeValues(args),
        connection.EscapeValues(kwargs)))

    if cache:
      if cache[0]['creating'] is not None:
        raise CurrentlyWorking(cache[0]['age'])
      return cls(connection, cache[0])
    else:
      raise cls.NotExistError('No cached data found')
