"""
ConPaaS director: add user
"""

import sys

import app 

if __name__ == "__main__":
    try:
        email, username, password = sys.argv[1:]
        app.create_user(username, "", "", email, "", password, 120)
    except ValueError:
        print "Usage: %s email username password" % sys.argv[0]
