#!/usr/bin/python3
"""Module to send emails through an smtp server"""

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.3'

# Standard modules
import base64
import os
import smtplib
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from uweb3.libs.safestring import  EmailAddresssafestring, EmailHeadersafestring


class MailError(Exception):
  """Something went wrong sending your email"""


class MailSender:
  """Easy context-interface for sending mail."""
  def __init__(self, host='localhost', port=25,
               local_hostname=None, timeout=5):
    """Sets up the connection to the SMTP server.

    Arguments:
      % host: str ~~ 'localhost'
        The SMTP hostname to connect to.
      % port: int ~~ 25
        Port for the SMTP server.
      % local_hostname: str ~~ from local hostname
        The hostname for which we want to send messages.
      % timeout: int ~~ 5
        Timeout in seconds.
    """
    self.server = None
    self.options = {'host': host, 'port': port,
                    'local_hostname': local_hostname or os.uname()[1],
                    'timeout': timeout}

  def __enter__(self):
    """Returns a SendMailContext for sending emails."""
    try:
      self.server = smtplib.SMTP(**self.options)
    except ConnectionRefusedError as error:
      raise SMTPConnectError(error, 'Connection refused.')
    return SendMailContext(self.server)

  def __exit__(self, *_exc_args):
    """Done sending mail, closes the smtp server connection."""
    self.server.quit()


class SendMailContext:
  """Context to use for sending emails."""
  def __init__(self, server):
    """Stores the server object locally."""
    self.server = server

  def Text(self, recipients, subject, content,
           sender=None, reply_to=None, charset='utf8'):
    """Send a text message

    Arguments:
      @ recipients: str / list of str
        Email address(es) of all TO: recipients.
      @ subject:  str
        Email subject
      @ content: str
        Body of the email
      % sender: str ~~ self.Noreply()
        The sender email addres, this defaults to the no-reply address.
      % reply_to: str ~~ None
        Optional reply-to address that differs from sender.
      % charset: str ~~ 'utf8'
        Character set to encode mail to.
    """
    message = MIMEMultipart()
    message['From'] = EmailAddresssafestring('') + (sender or self.Noreply())
    message['To'] = self.ParseRecipients(recipients)
    message['Subject'] = EmailHeadersafestring('') + ' '.join(subject.strip().split())
    message.attach(MIMEText(content.encode(charset), 'plain', charset))
    if reply_to:
      message['Reply-to'] = self.ParseRecipients(reply_to)
    self.server.sendmail(message['From'], recipients, message.as_string())

  def Attachments(self, recipients, subject, content,
                  attachments, sender=None, reply_to=None, charset='utf8'):
    """Sends email with attachments.

    Arguments like `Text()` but adds `attachments` after content. This should
    be a list of `str` (filename), `file` or 2-tuples with name and content.
    Content in case of 2-tuple can be `str` or any file-like object.
    """
    message = MIMEMultipart()
    message['From'] = EmailAddresssafestring('') + (sender or self.Noreply())
    message['To'] = self.ParseRecipients(recipients)
    message['Subject'] = EmailHeadersafestring('') + ' '.join(subject.strip().split())
    if reply_to:
      message['Reply-to'] = self.ParseRecipients(reply_to)
    message.attach(MIMEText(content.encode(charset), 'plain', charset))
    if isinstance(attachments, str):
      message.attach(self.ParseAttachment(attachments))
    else:
      for attachment in attachments:
        message.attach(self.ParseAttachment(attachment))
    self.server.sendmail(message['From'], recipients, str(message))

  @staticmethod
  def ParseAttachment(attachment):
    """Parses an attachment descriptor and returns a MIMEBase part for email."""
    if isinstance(attachment, tuple):
      name, contents = attachment
      if hasattr(contents, 'read'):
        contents = contents.read()
    elif isinstance(attachment, str):
      name = os.path.basename(attachment)
      contents = file(attachment, 'rb').read()
    elif isinstance(attachment, file):
      name = os.path.basename(attachment.name)
      attachment.seek(0)
      contents = attachment.read()

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(Wrap(base64.b64encode(contents)))
    part.add_header('Content-Transfer-Encoding', 'base64')
    part.add_header('Content-Disposition', 'attachment; filename="%s"' % name)
    return part

  @staticmethod
  def ParseRecipients(recipients):
    """Ensures multiple recipients are returned as a safestring without
    newlines."""
    if isinstance(recipients, str):
      return EmailAddresssafestring('') + recipients
    return EmailAddresssafestring('') + ', '.join(recipients)

  def Noreply(self):
    """Returns the no-reply email address for the configured local hostname."""
    return 'no-reply <no-reply@%s>' % self.server.local_hostname


def Wrap(content, cols=76):
  """Wraps multipart mime content into 76 column lines for niceness."""
  lines = []
  while content:
    lines.append(content[:cols])
    content = content[cols:]
  return '\r\n'.join(lines)


SMTPConnectError = smtplib.SMTPConnectError
SMTPRecipientsRefused = smtplib.SMTPRecipientsRefused
