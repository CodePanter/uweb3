#!/usr/bin/python3
"""Module to validate uploaded files against some config vars if present"""

__author__ = 'Jan Klopper <jan@underdark.nl>'
__version__ = '0.1'

import magic

class UploadLimiter:
    def __init__(self, options=None, size=None, filetypes=None):
        self.options = options
        self.size = int(self.options.get('upload', {}).get('size', size) if options else size)
        self.filetypes = None
        filetypes = self.options.get('upload', {}).get('filetypes', filetypes) if options else filetypes
        if filetypes:
            filetypes = filetypes.lower().replace(' ', ',').split(',')
            self.filetypes = [filetype.strip() for filetype in filetypes if filetype.strip()]

    def ValidFileType(self, content_type):
        if content_type.lower() not in self.filetypes:
            for filetype in self.filetypes:
                if content_type.startswith(filetype):
                    return True
            raise ContentTypeUploadException('%s is not an allowed file type.' % content_type)
        return True

    def Validate(self, file):
        if self.size and len(file) > self.size:
            raise FilesizeUploadException('File is too big: %db > %db' % (len(file), self.size))

        if self.filetypes:
            content_type = magic.from_buffer(file, mime=True)
            if not content_type:
                content_type = 'text/plain'
            return self.ValidFileType(content_type)
        return True


class UploadException(Exception):
    """There was an exception while uploading"""

class FilesizeUploadException(UploadException):
    """There was an exception while uploading due to filesize"""

class ContentTypeUploadException(UploadException):
    """There was an exception while uploading due to an invalid ContentType"""
