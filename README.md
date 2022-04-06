# New and improved: µWeb3

Since µWeb inception we have used it for many projects, and while it did its job, there were plenty of rough edges. This new version intends to remove those and pull it into the current age.

µWeb3 is free software, distributed under the terms of the [GNU] General Public License as published by the Free Software Foundation, version 3 of the License (or any later version).  For more information, see the file LICENSE

# Notable changes

* wsgi complaint interface
* python3 native
* Better handling of strings and automatic escaping
* More options for template engines
* More options for SQL / database engines


## Example projects

The following example applications for uWeb3 exist:

* [uWeb3-scaffold](https://github.com/underdarknl/uweb3scaffold): This is an empty project which you can fork to start your own website

# µWeb3 installation

The easiest and quickest way to install µWeb3 is by running pip3 install uwebthree.

For a development version using Python's `virtualenv`. Install using the setuptools installation script, which will automatically gather dependencies.

```bash
# Set up the Python3 virtualenv
python3 -m venv env
source env/bin/activate

# Install uWeb3
python3 setup.py install

# Or you can install in development mode which allows easy modification of the source:
python3 setup.py develop  --user

# clone the uweb3scaffold project to get started
git clone git@github.com:underdarknl/uweb3scaffold.git
cd uweb3scaffold

python3 serve.py
```

## Ubuntu issues
On some ubuntu setups venv is broken and therefore does not install the activation scripts.

```bash
# Set up the Python3 virtualenv on Ubuntu
python3 -m venv --without-pip env
source env/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python
deactivate
source env/bin/activate

# then proceed to install µWeb3 like before.
```

# µWeb3 database setup

Setting up a database connection with µWeb3 is easy, navigate to the settings.ini file in the scaffold folder and add the following fields to the file:
```
[mysql] OR [sqlite]
host = 'host'
user = 'username'
password = 'pass'
database = 'dbname'
```
To access your database connection simply use the connection attribute in any class that inherits from PageMaker.

# Routing
The default way to create new routes in µWeb3 is to create a folder called routes.
In the routes folder create your pagemaker class of choice, the name doesn't matter as long as it inherits from PageMaker.
After creating your pagemaker be sure to add the route endpoint to routes list in base/__init__.py.

# New since v3
- In uweb3 __init__ a class called HotReload
- In pagemaker __init__:
  - A classmethod called loadModules that loads all pagemaker modules inheriting from PageMaker class
  - A XSRF class
    - Generates a xsrf token and creates a cookie if not in place
- In requests:
  - Self.method attribute
  - self.post.form attribute. This is the post request as a dict, includes blank values.
  - Method called Redirect #Moved from the response class to the request class so cookies that are set before a redirect are actually persist to the next request.
  - Method called DeleteCookie
  - An if statement that checks string like cookies and raises an error if the size is equal or bigger than 4096 bytes.
  - AddCookie method, now supports multiple calls to Set-Cookie setting all cookies instead of just the last.
- In pagemaker/decorators:
  - Loggedin decorator that validates if user is loggedin based on cookie with userid
  - Checkxsrf decorator that checks if the incorrect_xsrf_token flag is set
- In templatepaser:
  - Its possible to register tags to the parser, for example in your _postInit call
  - Its possible to register 'Just in Time' tags to the parser, which will be evaluated only when needed.
- In libs/sqltalk, use of PyMysql instead of c mysql functions
- Connections
  - All Connections are now all availabe on the self.connections member of the pagemaker, regardless of what type of backend they connect to
  - Cookies (signed and safe) are available as a connection
  - Config files (read/write) are available as a connection
