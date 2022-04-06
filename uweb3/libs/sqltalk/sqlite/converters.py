import sqlite3
import datetime
import pytz
import time


INTERPRET_AS_UTC = pytz.utc.localize

def DateFromTicks(ticks):
  return datetime.date(*time.gmtime(ticks)[:3])


def TimeFromTicks(ticks):
  return INTERPRET_AS_UTC(datetime.time(*time.gmtime(ticks)[3:6]))


def TimestampFromTicks(ticks):
  return INTERPRET_AS_UTC(datetime.datetime.utcfromtimestamp(ticks))


def AdaptDate(date_obj):
  """Adapts a datetime.date object into its daynumber since Common Era."""
  return date_obj.toordinal()


def AdaptDatetime(date_obj):
  """Adapts a datetime.datetime object into a short string timestamp.

  The date portion is converted to its daynumber since Common Era.
  The time portion is converted to milliseconds past midnight.
  These two are joined by a 'T'.
  """
  try:
    date_obj = date_obj.astimezone(pytz.utc)
  except ValueError:
    pass  # naive datetime object
  timepart = date_obj.time()
  seconds = (timepart.hour * 3600000 + timepart.minute * 60000 +
             timepart.second * 1000 + timepart.microsecond // 1000)
  return '%dT%d' % (date_obj.toordinal(), seconds)


def AdaptReadableDate(date_obj):
  """Adapts a datetime.date object to its ISO-8601 date notation."""
  return date_obj.isoformat()


def AdaptReadableDatetime(date_obj):
  """Adapts a datetime.datetime object to its ISO-8601 date/time notation."""
  try:
    date_obj = date_obj.astimezone(pytz.utc)
  except ValueError:
    pass  # naive datetime object
  return date_obj.isoformat()


#TODO(Elmer): Docstrings, tests, sharp eyes.
def AdaptReadableTimeStruct(time_struct):
  return time.strftime('%FT%T', time_struct)


def AdaptTimeStruct(time_struct):
  return AdaptDatetime(datetime.datetime(*time_struct[:6]))


def ConvertDate(date_obj):
  """Converts an SQLite DATE field to a datetime.date object.

  Two stored formats are supported: The format as defined in SQLTalk, which is
  the number of days since Common Era, and the ISO-8601 date format."""
  try:
    # Assume date is the number of days since Common Era as a string.
    return datetime.date.fromordinal(int(date_obj))
  except ValueError:
    # Date was not a number, assume ISO-8601
    return datetime.date(*map(int, date_obj.split("-")))


def ConvertTimestamp(date_obj):
  """Converts an encoded timestamp to a datetime.datetime object.

  This reads both a ISO-8601 formatted string, as well as the Underdark custom
  compressed datetime format as defined in AdaptDatetime above.
  """
  sep = 'T' if 'T' in date_obj else ' '
  try:
    # Assume that the datepart is days since Common Era,
    # and the timepart is seconds past midnight.
    datepart, timepart = date_obj.split(sep)
    return INTERPRET_AS_UTC(
        datetime.datetime.fromordinal(int(datepart)) +
        datetime.timedelta(microseconds=int(timepart) * 1000))
  except ValueError:
    # Either part couldn't be interpreter as integer, meaning they are ISO-8601.
    date_obj, _sep, microseconds = date_obj.partition('.')
    time_tuple = time.strptime(date_obj, '%Y-%m-%d' + sep + '%H:%M:%S')[:6]
    if microseconds:
      microseconds = int((microseconds + '00000')[:6])
      time_tuple += microseconds,
    return INTERPRET_AS_UTC(datetime.datetime(*time_tuple))


sqlite3.register_adapter(datetime.date, AdaptDate)
sqlite3.register_adapter(datetime.datetime, AdaptDatetime)
sqlite3.register_adapter(time.struct_time, AdaptTimeStruct)
sqlite3.register_converter('DATE', ConvertDate)
sqlite3.register_converter('TIMESTAMP', ConvertTimestamp)
