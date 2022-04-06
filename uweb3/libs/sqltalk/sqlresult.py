#!/usr/bin/python3
"""SQL result abstraction module.

Classes:
  ResultRow: Dict-like object that represents a single database result row.
  ResultSet: Abstraction for a database resultset.

Error Classes:
  Error: Exception base class.
  FieldError: Field- index or name does not exist.
  NotSupportedError: Operation is not supported
"""
__author__ = ('Elmer de Looff <elmer@underdark.nl>',
              'Jan Klopper <jan@underdark.nl>')
__version__ = '1.4'

# Standard modules
import operator

GET_FIELD_NAME = operator.itemgetter(0)


class Error(Exception):
  """Exception base class."""


class FieldError(Error, LookupError):
  """Field- index or name does not exist."""


class NotSupportedError(Error, TypeError):
  """Operation is not supported."""


class ResultRow(object):
  """SQL Result row - an ordered dictionary-like record abstraction.

  ResultRow has two item retrieval interfaces:
    1) Key-based access like that of a dictionary.
    2) Indexed access like a tuple. (field-order is preserved)

  Deleting items from the ResultRow can be done both on index and key. Updating
  or adding fields to the ResultRow can only be done on a key-basis.

  Members:
    % names: tuple (read-only)
      Names for the fields that the ResultRow contains.
  """
  # We expect many ResultRow instances, __slots__ cuts the memory footprint
  # in half for small rows. This seems like a reasonable tradeoff.
  __slots__ = ('_fields', '_values')

  def __init__(self, fields, values):
    """Sets up the ordered dict.

    Arguments:
      @ fields: iterable
        Fieldnames for the SQL result
      @ values: iterable
        Values that belong to the provided fields
    """
    self._fields = list(fields)
    self._values = list(values)

  def __eq__(self, other):
    """Checks equality of the ResultRow to another ResultRow or object.

    A ResultRow can only be equal to another ResultRow, and then only if both
    fieldnames and fieldvalues are the same (data and order).
    """
    return isinstance(other, type(self)) and self.items() == other.items()

  def __getitem__(self, key):
    try:
      if isinstance(key, int):
        return self._values[key]
      else:
        return self._values[self._fields.index(key)]
    except (LookupError, ValueError) as message:
      raise FieldError(message)

  def __repr__(self):
    """Returns a string representation of the ResultRow."""
    return '%s(%s)' % (self.__class__.__name__,
                       ', '.join('%s=%r' % item for item in self.iteritems()))

  def get(self, key, default=None):
    try:
      return self[key]
    except FieldError:
      return default

  @property
  def names(self):
    return self.keys()

  # ############################################################################
  # Iteration on dictionary / record entries
  #
  def __len__(self):
    """Returns the length of the ResultRow."""
    return len(self._values)

  def __iter__(self):
    """Returns an iterator for the values of the ResultRow."""
    return iter(self._values)

  def __reversed__(self):
    """Returns a reversed value iterator."""
    return reversed(self._values)

  def iterkeys(self):
    return iter(self._fields)

  def itervalues(self):
    return iter(self._values)

  def iteritems(self):
    return zip(self._fields, self._values)

  def keys(self):
    return self._fields[:]

  def values(self):
    return self._values[:]

  def items(self):
    return zip(self._fields, self._values)

  # ############################################################################
  # Methods to keep the dictionary neat and ordered
  #
  def __delitem__(self, key):
    """Removes a key or index from the ResultRow."""
    try:
      index = key if isinstance(key, int) else self._fields.index(key)
      del self._fields[index]
      del self._values[index]
    except (LookupError, ValueError):
      raise FieldError('The ResultRow has no field %r' % key)

  def __setitem__(self, field, value):
    """Sets or updates a dictionary value.

    N.B. The implementation for this is slow for large ResultRow objects.
    """
    try:
      self._values[self._fields.index(field)] = value
    except ValueError:
      # The field does not already occur in the ResultRow, add it at the end
      self._fields.append(field)
      self._values.append(value)

  def pop(self, key, *default):
    try:
      index = self._fields.index(key)
      del self._fields[index]
      return self._values.pop(index)
    except ValueError:
      if default:
        return default[0]
      raise FieldError('No field %r in this ResultRow', key)

  def popitem(self):
    """Pops the key,value pair at the end of the dictionary."""
    if not self:
      raise KeyError
    return self._fields.pop(), self._values.pop()


class ResultSet(object):
  """SQL Result set - stores the query, the returned result, and other info.

  ResultSet is created from immutable objects. Once defined, none of its
  attributes can be altered or overwritten. The exception to this is the private
  member _fieldnames which has to be a list for fieldname lookup purposes.

  Members:
    @ affected - int
      Number of rows affected by last action.
    @ charset - str
      Character set used for this connection.
    @ fields - tuple
      Fields in the ResultSet.
    @ insertid - int
      Auto-increment ID that was generated upon the last insert.
    @ query - str
      The executed query that gave this result set.
    @ result:   tuple
      SQL Result set for the last executed query.
    @ _fieldnames - list
      Names of the fields in the result, used for reverse-indexing.
    % fieldnames - tuple (read-only)
      Names of the fields in the result.
  """

  def __init__(self, query='', charset='', result=None, fields=None,
               affected=0, insertid=0, row_class=ResultRow):
    """Initializes a new ResultSet.

    Arguments:
      % affected: int ~~ 0
        Number of affected rows from this operation.
      % charset: str ~~ ''
        Character set used by the connection that executed this operation.
      % fields: tuple of strings ~~ None
        Description of fields involved in this operation.
      % insertid: int ~~ 0
        Auto-increment ID that was generated upon the last insert.
      % query ~~ ''
        The query that was executed for this operation.
      % result ~~ None
        SQL Result set for the this operation.
    """
    self.affected = affected
    self.charset = charset
    self.insertid = insertid
    self.query = query
    self.warnings = []

    if result:
      self.fields = fields
      self.raw = result
      self.result = [row_class(fields, row.values()) for row in result]
    else:
      self.fields = ()
      self.result = []

  def __eq__(self, other):
    """Checks equality of the ResultSet to another ResultSet or object.

    A ResultSet can only be equal to another ResultSet, and then only if all
    their public members compare equal.
    """
    if self is other:
      return True
    elif isinstance(other, self.__class__):
      return (self.affected == other.affected and
              self.insertid == other.insertid and
              self.fields == other.fields and
              self.result == other.result)
    else:
      return False

  def __getitem__(self, item):
    """Returns a row or column from the ResultSet by either index or fieldname.

    Arguments:
      @ item: int / str
        Rownumber or fieldname:
        - If given a rownumber, the corresponding ResultRow is returned.
        - If given a fieldname, a tuple with the field's values is returned.

    Returns:
      ResultRow / tuple: As detailed in the Arguments section.
    """
    try:
      return self.result[item]
    except IndexError:
      raise FieldError('Bad field index: %r.' % item)
    except FieldError:
      raise
    except TypeError:
      # The item type is incorrect, try grabbing a column for this fieldname.
      try:
        index = self._fields.index(item)
        return tuple(row[index] for row in self.result)
      except ValueError:
        raise FieldError('Bad field name: %r.' %  item)

  def __iter__(self):
    """Returns an iterator for the contained ResultRows."""
    return iter(self.result)

  def __len__(self):
    """Returns an integer equal to the number of rows contained."""
    return len(self.result)

  def __nonzero__(self):
    """Boolean truthness of the ResultSet. True if it has 1+ ResultRow"""
    return bool(self.result)

  def __repr__(self):
    """Returns a string representation of the ResultSet."""
    return '%s instance: %d row%s' % (
        self.__class__.__name__, len(self.result), 's'[len(self.result) == 1:])

  def FilterRowsByFields(self, *fields):
    """Yields ResultRows containing only selected fields.

    Arguments:
      @ *fields: list of str
        The fieldnames to filter.

    Raises:
      BadFieldError: One of the given fieldnames did not exist.

    Yields:
      ResultRow: Each ResultRow contains only the filtered fields.
    """
    try:
      indices = tuple(self._fields.index(field) for field in fields)
    except ValueError:
      raise FieldError('Bad fieldnames in filter request.')
    for row in self:
      yield ResultRow(zip(fields, tuple(row[index] for index in indices)))

  def PopField(self, field):
    try:
      self._fields.remove(field)
    except ValueError:
      raise FieldError('Fieldname %r does not occur in the ResultSet.' % field)
    return [row.pop(field) for row in self]

  def PopRow(self, row_index):
    return self.result.pop(row_index)

  @property
  def fieldnames(self):
    """Returns a tuple of the fieldnames that are in this ResultSet."""
    return tuple(self._fields)
