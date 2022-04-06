from itertools import chain

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import reconstructor, sessionmaker
from sqlalchemy.orm.session import object_session

from uweb3.model import NotExistError


class AlchemyBaseRecord:
  def __init__(self, session, record):
    self.session = session
    self._BuildClassFromRecord(record)

  def _BuildClassFromRecord(self, record):
    if not isinstance(record, dict):
      return
    for key, value in record.items():
      if key not in self.__table__.columns.keys():
        raise AttributeError(f"Key '{key}' not specified in class '{self.__class__.__name__}'")
      setattr(self, key, value)
    if self.session:
      try:
        self.session.add(self)
      except:
        self.session.rollback()
        raise
      else:
        self.session.commit()

  def __hash__(self):
    """Returns the hashed value of the key."""
    return hash(self.key)

  def __del__(self):
    """Cleans up the connection at the end of its life cycle"""
    self.session.close()

  def __repr__(self):
    s = {}
    for key in self.__table__.columns.keys():
      value = getattr(self, key)
      if value:
        s[key] = value
    return f'{type(self).__name__}({s})'

  def __eq__(self, other):
    if type(self) != type(other):
      return False  # Types must be the same.
    elif not (self.key == other.key is not None):
      return False  # Records should have the same non-None primary key value.
    elif len(self) != len(other):
      return False  # Records must contain the same number of objects.
    for key in self.__table__.columns.keys():
      value = getattr(self, key)
      other_value = getattr(other, key)
      if isinstance(self, AlchemyBaseRecord) != isinstance(other, AlchemyBaseRecord):
        # Only one of the two is a BaseRecord instance
        if (isinstance(self, AlchemyBaseRecord) and value.key != other_value or
            isinstance(other, AlchemyBaseRecord) and other_value.key != value):
          return False
      elif value != other_value:
        return False
    return True

  def __ne__(self, other):
    """Returns the proper inverse of __eq__."""
    # Without this, the non-equal checks used in __eq__ will not work,
    # and the  `!=` operator would not be the logical inverse of `==`.
    return not self == other

  def __len__(self):
    return len({
        col: getattr(self, col)
        for col in self.__table__.columns.keys() if getattr(self, col)
    })

  def __int__(self):
    """Returns the integer key value of the Record.

    For record objects where the primary key value is not (always) an integer,
    this function will raise an error in the situations where it is not.
    """
    key_val = self.key
    if not isinstance(key_val, (int)):
      # We should not truncate floating point numbers.
      # Nor turn strings of numbers into an integer.
      raise ValueError('The primary key is not an integral number.')
    return key_val

  def copy(self):
    """Returns a shallow copy of the Record that is a new functional Record."""
    import copy
    return copy.copy(self)

  def deepcopy(self):
    import copy
    return copy.deepcopy(self)

  def __gt__(self, other):
    """Index of this record is greater than the other record's.

    This requires both records to be of the same record class.
    """
    if type(self) == type(other):
      return self.key > other.key
    return NotImplemented

  def __ge__(self, other):
    """Index of this record is greater than, or equal to, the other record's.

    This requires both records to be of the same record class.
    """
    if type(self) == type(other):
      return self.key >= other.key
    return NotImplemented

  def __lt__(self, other):
    """Index of this record is smaller than the other record's.

    This requires both records to be of the same record class.
    """
    if type(self) == type(other):
      return self.key < other.key
    return NotImplemented

  def __le__(self, other):
    """Index of this record is smaller than, or equal to, the other record's.

    This requires both records to be of the same record class.
    """
    if type(self) == type(other):
      return self.key <= other.key
    return NotImplemented

  def __getitem__(self, field):
    return getattr(self, field)

  def iteritems(self):
    """Yields all field+value pairs in the Record.

    This automatically loads in relationships.
    """
    return chain(((key, getattr(self, key)) for key in self.__table__.columns.keys()),
    ((child[0], getattr(self, child[0])) for child in inspect(type(self)).relationships.items()))

  def itervalues(self):
    """Yields all values in the Record, loads relationships"""
    return chain((getattr(self, key) for key in self.__table__.columns.keys()),
                 (getattr(self, child[0]) for child in inspect(type(self)).relationships.items()))

  def items(self):
    """Returns a list of field+value pairs in the Record.

    This automatically loads in relationships.
    """
    return list(self.iteritems())

  def values(self):
    """Returns a list of values in the Record, loading foreign references."""
    return list(self.itervalues())

  @property
  def key(self):
    return getattr(self, inspect(type(self)).primary_key[0].name)

  @classmethod
  def TableName(cls):
    """Returns the database table name for the Record class."""
    return cls.__tablename__

  @classmethod
  def _AlchemyRecordToDict(cls, record):
    """Turns the values of a given class into a dictionary. Doesn't trigger
    automatic loading of child classes.

    Arguments:
      @ record: cls
        AlchemyBaseRecord class that is retrieved from a database query
    Returns
      dict: dictionary with all table columns and values
      None: when record is empty
    """
    if not isinstance(record, type(None)):
      return {col: getattr(record, col) for col in record.__table__.columns.keys()}
    return None

  @reconstructor
  def reconstruct(self):
    """This is called instead of __init__ when the result comes from the database"""
    self.session = object_session(self)

  @classmethod
  def _PrimaryKeyCondition(cls, target):
    """Returns the name of the primary key of given class

    Arguments:
      @ target: cls
        Class that you want to know the primary key name from
    """
    return getattr(cls, inspect(cls).primary_key[0].name)

class AlchemyRecord(AlchemyBaseRecord):
  """ """
  @classmethod
  def FromPrimary(cls, session, p_key):
    """Finds record based on given class and supplied primary key.

    Arguments:
      @ session: sqlalchemy session object
        Available in the pagemaker with self.session
      @ p_key: integer
        primary_key of the object to delete
    Returns
      cls
      None
    """
    try:
      record = session.query(cls).filter(cls._PrimaryKeyCondition(cls) == p_key).first()
    except:
      session.rollback()
      raise
    else:
      if not record:
        raise NotExistError(f"Record with primary key {p_key} does not exist")
      return record

  @classmethod
  def DeletePrimary(cls, session, p_key):
    """Deletes record base on primary key from given class.

    Arguments:
      @ session: sqlalchemy session object
        Available in the pagemaker with self.session
      @ p_key: integer
        primary_key of the object to delete

    Returns:
      isdeleted: boolean
    """
    try:
      isdeleted = session.query(cls).filter(cls._PrimaryKeyCondition(cls) == p_key).delete()
    except:
      session.rollback()
      raise
    else:
      session.commit()
      return isdeleted

  @classmethod
  def Create(cls, session, record):
    """Creates a new instance and commits it to the database

    Arguments:
      @ session: sqlalchemy session object
        Available in the pagemaker with self.session
      @ record: dict
        Dictionary with all key:value pairs that are required for the db record
    Returns:
      cls
    """
    return cls(session, record)

  @classmethod
  def List(cls, session, conditions=None, limit=None, offset=None,
           order=None, yield_unlimited_total_first=False):
    """Yields a Record object for every table entry.

    Arguments:
      @ session: sqlalchemy session object
        Available in the pagemaker with self.session
      % conditions: list
        Optional query portion that will be used to limit the list of results.
        If multiple conditions are provided, they are joined on an 'AND' string.
        For example: conditions=[User.id <= 10, User.id >=]
      % limit: int ~~ None
        Specifies a maximum number of items to be yielded. The limit happens on
        the database side, limiting the query results.
      % offset: int ~~ None
        Specifies the offset at which the yielded items should start. Combined
        with limit this enables proper pagination.
      % order: tuple of operants
        For example the User class has 3 fields; id, username, password. We can pass
        the field we want to order on to the tuple like so;
        (User.id.asc(), User.username.desc())
      % yield_unlimited_total_first: bool ~~ False
        Instead of yielding only Record objects, the first item returned is the
        number of results from the query if it had been executed without limit.

    Returns:
      integer: integer with length of results.
      list: List of classes from request type
    """
    try:
      query = session.query(cls)
      if conditions:
        for condition in conditions:
          query = query.filter(condition)
      if order:
        for item in order:
          query = query.order_by(item)
      if limit:
        query = query.limit(limit)
      if offset:
        query = query.offset(offset)
      result = query.all()
    except:
      session.rollback()
      raise
    else:
      if yield_unlimited_total_first:
        return len(result)
      return result

  @classmethod
  def Update(cls, session, conditions, values):
    """Update table based on conditions.

    Arguments:
      @ session: sqlalchemy session object
          Available in the pagemaker with self.session
      @ conditions: list|tuple
        for example: [User.id > 2, User.id < 100]
      @ values: dict
        for example: {User.username: 'value'}
    """
    try:
      query = session.query(cls)
      for condition in conditions:
        query = query.filter(condition)
      query = query.update(values)
    except:
      session.rollback()
      raise
    else:
      session.commit()

  def Delete(self):
    """Delete current instance from the database"""
    try:
      isdeleted = self.session.query(type(self)).filter(self._PrimaryKeyCondition(self) == self.key).delete()
    except:
      self.session.rollback()
      raise
    else:
      self.session.commit()
      return isdeleted

  def Save(self):
    """Saves any changes made in the current record. Sqlalchemy automatically detects
    these changes and only updates the changed values. If no values are present
    no query will be commited."""
    self.session.commit()


class AlchemyRecord(AlchemyBaseRecord):
  """ """
  @classmethod
  def FromPrimary(cls, session, p_key):
    """Finds record based on given class and supplied primary key.

    Arguments:
      @ session: sqlalchemy session object
        Available in the pagemaker with self.session
      @ p_key: integer
        primary_key of the object to delete
    Returns
      cls
      None
    """
    try:
      record = session.query(cls).filter(cls._PrimaryKeyCondition(cls) == p_key).first()
    except:
      session.rollback()
      raise
    else:
      if not record:
        raise NotExistError(f"Record with primary key {p_key} does not exist")
      return record

  @classmethod
  def DeletePrimary(cls, session, p_key):
    """Deletes record base on primary key from given class.

    Arguments:
      @ session: sqlalchemy session object
        Available in the pagemaker with self.session
      @ p_key: integer
        primary_key of the object to delete

    Returns:
      isdeleted: boolean
    """
    try:
      isdeleted = session.query(cls).filter(cls._PrimaryKeyCondition(cls) == p_key).delete()
    except:
      session.rollback()
      raise
    else:
      session.commit()
      return isdeleted

  @classmethod
  def Create(cls, session, record):
    """Creates a new instance and commits it to the database

    Arguments:
      @ session: sqlalchemy session object
        Available in the pagemaker with self.session
      @ record: dict
        Dictionary with all key:value pairs that are required for the db record
    Returns:
      cls
    """
    return cls(session, record)

  @classmethod
  def List(cls, session, conditions=None, limit=None, offset=None,
           order=None, yield_unlimited_total_first=False):
    """Yields a Record object for every table entry.

    Arguments:
      @ session: sqlalchemy session object
        Available in the pagemaker with self.session
      % conditions: list
        Optional query portion that will be used to limit the list of results.
        If multiple conditions are provided, they are joined on an 'AND' string.
        For example: conditions=[User.id <= 10, User.id >=]
      % limit: int ~~ None
        Specifies a maximum number of items to be yielded. The limit happens on
        the database side, limiting the query results.
      % offset: int ~~ None
        Specifies the offset at which the yielded items should start. Combined
        with limit this enables proper pagination.
      % order: tuple of operants
        For example the User class has 3 fields; id, username, password. We can pass
        the field we want to order on to the tuple like so;
        (User.id.asc(), User.username.desc())
      % yield_unlimited_total_first: bool ~~ False
        Instead of yielding only Record objects, the first item returned is the
        number of results from the query if it had been executed without limit.

    Returns:
      integer: integer with length of results.
      list: List of classes from request type
    """
    try:
      query = session.query(cls)
      if conditions:
        for condition in conditions:
          query = query.filter(condition)
      if order:
        for item in order:
          query = query.order_by(item)
      if limit:
        query = query.limit(limit)
      if offset:
        query = query.offset(offset)
      result = query.all()
    except:
      session.rollback()
      raise
    else:
      if yield_unlimited_total_first:
        return len(result)
      return result

  @classmethod
  def Update(cls, session, conditions, values):
    """Update table based on conditions.

    Arguments:
      @ session: sqlalchemy session object
          Available in the pagemaker with self.session
      @ conditions: list|tuple
        for example: [User.id > 2, User.id < 100]
      @ values: dict
        for example: {User.username: 'value'}
    """
    try:
      query = session.query(cls)
      for condition in conditions:
        query = query.filter(condition)
      query = query.update(values)
    except:
      session.rollback()
      raise
    else:
      session.commit()

  def Delete(self):
    """Delete current instance from the database"""
    try:
      isdeleted = self.session.query(type(self)).filter(self._PrimaryKeyCondition(self) == self.key).delete()
    except:
      self.session.rollback()
      raise
    else:
      self.session.commit()
      return isdeleted

  def Save(self):
    """Saves any changes made in the current record. Sqlalchemy automatically detects
    these changes and only updates the changed values. If no values are present
    no query will be commited."""
    self.session.commit()
