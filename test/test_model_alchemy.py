#!/usr/bin/python3
"""Test suite for the database abstraction module (model)."""

# Too many public methods
# pylint: disable=R0904

# Standard modules
import unittest

import sqlalchemy
from sqlalchemy import (Column, ForeignKey, Integer, MetaData, String, Table,
                        create_engine)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import lazyload, relationship

import uweb3
from uweb3.alchemy_model import AlchemyRecord
from uweb3.libs.sqltalk import mysql

# ##############################################################################
# Record classes for testing
#
Base = declarative_base()

class BasicTestRecord(AlchemyRecord, Base):
  """Test record for offline tests."""
  __tablename__ = 'basicTestRecord'
  ID = Column(Integer, primary_key=True)
  name = Column(String(32), nullable=False)
  x = Column(String(32))

class Author(AlchemyRecord, Base):
  __tablename__ = 'author'
  ID = Column(Integer, primary_key=True)
  name = Column(String(32), nullable=False)

class Writers(AlchemyRecord, Base):
  __tablename__ = 'writers'
  ID = Column(Integer, primary_key=True)
  name = Column(String(32), nullable=False)

class Book(AlchemyRecord, Base):
  """Book class for testing purposes."""
  __tablename__ = 'book'
  ID = Column(Integer, primary_key=True)
  title = Column(String(32), nullable=False)
  authorid = Column('authorid', Integer, ForeignKey('author.ID'))
  author = relationship("Author",  lazy="select")

class BaseRecordTests(unittest.TestCase):
  """Offline tests of methods and behavior of the BaseRecord class."""
  def setUp(self):
    """Sets up the tests for the offline Record test."""
    self.record_class = BasicTestRecord

  def testTableName(self):
    """[BaseRecord] TableName returns the expected value and obeys _TABLE"""
    self.assertEqual(self.record_class.TableName(), 'basicTestRecord')

  def testPrimaryKey(self):
    """[BaseRecord] Primary key value on `key` property, default field 'ID'"""
    record = self.record_class(None, {'ID': 12, 'name': 'J.R.R. Tolkien'})
    self.assertEqual(record.key, 12)

  def testEquality(self):
    """[BaseRecord] Records of the same content are equal to eachother"""
    record_one = self.record_class(None, {'ID': 2, 'name': 'Rowling'})
    record_two = self.record_class(None, {'ID': 2, 'name': 'Rowling'})
    record_three = self.record_class(None, {'ID': 3, 'name': 'Rowling'})
    record_four = self.record_class(None, {'ID': 2, 'name': 'Rowling', 'x': 2})
    self.assertFalse(record_one is record_two)
    self.assertEqual(record_one, record_two)
    self.assertNotEqual(record_one, record_three)
    self.assertNotEqual(record_one, record_four)

class RecordTests(unittest.TestCase):
  """Online tests of methods and behavior of the Record class."""

  def setUp(self):
    """Sets up the tests for the Record class."""
    self.engine = DatabaseConnection()
    self.session = Create_session(self.engine)
    self.meta = MetaData()
    book = Table(
      'book', self.meta,
      Column('ID', Integer, primary_key=True),
      Column('authorid', Integer, ForeignKey('author.ID')),
      Column('title', String(32), nullable=False)
    )
    author = Table(
      'author', self.meta,
      Column('ID', Integer, primary_key=True),
      Column('name', String(32), nullable=False),
    )
    writers = Table(
      'writers', self.meta,
      Column('ID', Integer, primary_key=True),
      Column('name', String(32), nullable=False),
    )
    self.meta.create_all(self.engine)

  def tearDown(self):
    """Destroy tables after testing."""
    self.session.close()
    Book.__table__.drop(self.engine)
    Author.__table__.drop(self.engine)

  def testLoadPrimary(self):
    """[Record] Records can be loaded by primary key using FromPrimary()"""
    inserted = Author.Create(self.session, {'name': 'A. Chrstie'})
    author = Author.FromPrimary(self.session, inserted.key)
    self.assertEqual(type(author), Author)
    self.assertEqual(len(author), 2)
    self.assertEqual(author.key, author.ID)
    self.assertEqual(author.name, 'A. Chrstie')

  def testCreateRecord(self):
    """Database records can be created using Create()"""
    new_author = Author.Create(self.session, {'name': 'W. Shakespeare'})
    author = Author.FromPrimary(self.session, new_author.key)
    self.assertEqual(author.name, 'W. Shakespeare')

  def testCreateRecordWithBadField(self):
      """Database record creation fails if there are unknown fields present"""
      self.assertRaises(AttributeError, Author.Create, self.session,
                        {'name': 'L. Tolstoy', 'email': 'leo@tolstoy.ru'})

  def testUpdateRecord(self):
    """The record can be given new values and these are properly stored"""
    author = Author.Create(self.session, {'name': 'B. King'})
    author.name = 'S. King'
    author.Save()
    same_author = Author.FromPrimary(self.session, author.key)
    self.assertEqual(author.name, 'S. King')
    self.assertEqual(author, same_author)

  def testUpdatingDeletedRecord(self):
    """Should raise an error because the record no longer exists"""
    author = Author.Create(self.session, {'name': 'B. King'})
    Author.DeletePrimary(self.session, author.key)
    author.name = 'S. King'
    self.assertRaises(sqlalchemy.orm.exc.StaleDataError, author.Save())

  def testUpdatePrimaryKey(self):
    """Saving with an updated primary key properly saved the record"""
    author = Author.Create(self.session, {'name': 'C. Dickens'})
    self.assertEqual(author.key, 1)
    author.ID = 101
    author.Save()
    self.assertRaises(uweb3.model.NotExistError, Author.FromPrimary,
                      self.session, 1)
    same_author = Author.FromPrimary(self.session, 101)
    self.assertEqual(same_author, author)

  def testLoadRelated(self):
    """Fieldnames that match tablenames trigger automatic loading"""
    author = Author.Create(self.session, {'name': 'D. Koontz'})
    book = Book.Create(self.session, {'title': 'The eyes of Darkness', 'authorid': 1})
    self.assertEqual(type(author), Author)
    self.assertEqual(type(book.author), Author)
    self.assertEqual(book.author.name, 'D. Koontz')
    self.assertEqual(book.author.key, 1)

  def testLoadRelatedFailure(self):
    """Automatic loading raises IntegrityError if the foreign record is absent"""
    self.assertRaises(IntegrityError, Book.Create, self.session, {'title': 'The eyes of Darkness', 'authorid': 1})

  def testLoadRelatedSuppressedForNone(self):
    """Automatic loading is not attempted when the field value is `None`"""
    self.assertRaises(OperationalError, Book.Create, self.session, {'title': None})

  def testVerifyNoLoad(self):
    """No loading is performed on a field that matches a class but no table"""
    self.assertRaises(AttributeError, Book, self.session, {'writer': 1})

  def testValues(self):
    author = Author.Create(self.session, {'name': 'D. Koontz'})
    self.assertEqual(author.values(), [1, 'D. Koontz'])
    book = Book.Create(self.session, {'title': 'The eyes of Darkness', 'authorid': author.key})
    self.assertEqual(book.values(), [1, 'The eyes of Darkness', 1, Author(None, {'ID': 1, 'name': 'D. Koontz'})])

  def testItems(self):
    author = Author.Create(self.session, {'name': 'D. Koontz'})
    self.assertEqual(author.items(), [('ID', 1), ('name', 'D. Koontz')])
    book = Book.Create(self.session, {'title': 'The eyes of Darkness', 'authorid': author.key})
    self.assertEqual(book.items(),
                     [('ID', 1),
                      ('title', 'The eyes of Darkness'),
                      ('authorid', 1),
                      ('author', Author(None, {'ID': 1, 'name': 'D. Koontz'}))])

def DatabaseConnection():
  """Returns an SQLTalk database connection to 'uWeb3_model_test'."""
  return create_engine('mysql://{user}:{passwd}@{host}/{db}'.format(
    host='localhost',
    user='stef',
    passwd='24192419',
    db='uweb_test'
  ))

def Create_session(engine):
  from sqlalchemy.orm import sessionmaker
  Session = sessionmaker(autocommit=False)
  Session.configure(bind=engine)
  return Session()

if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
