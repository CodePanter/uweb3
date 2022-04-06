#!/usr/bin/python3
"""uWeb3 installer."""

import os
import re
from setuptools import setup, find_packages

def Requirements():
  """Returns the contents of the Requirements.txt file."""
  with open(os.path.join(os.path.dirname(__file__), 'requirements.txt')) as r_file:
    return r_file.read()

def Description():
  """Returns the contents of the README.md file as description information."""
  with open(os.path.join(os.path.dirname(__file__), 'README.md')) as r_file:
    return r_file.read()

def Version():
  """Returns the version of the library as read from the __init__.py file"""
  main_lib = os.path.join(os.path.dirname(__file__), 'uweb3', '__init__.py')
  with open(main_lib) as v_file:
    return re.match(".*__version__ = '(.*?)'", v_file.read(), re.S).group(1)


setup(
    name='uWebthree',
    version=Version(),
    description='uWeb, python3, uswgi compatible micro web platform',
    long_description=Description(),
    long_description_content_type='text/markdown',
    license='ISC',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    author='Jan Klopper',
    author_email='jan@underdark.nl',
    url='https://github.com/underdark.nl/uweb3',
    keywords='minimal python web framework',
    packages=find_packages(),
    include_package_data=True,
    install_requires=Requirements(),
    python_requires='>=3.5')
