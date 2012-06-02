"""
ConPaaS director: authentication module
"""

import sys
import hashlib

import app 

def create_user(username, fname, lname, email, affiliation, password, credit):
    """Create a new user with the given attributes. Return a new User object
    in case of successful creation. None otherwise."""
    user = app.User(username=username, 
                    fname=fname, 
                    lname=lname, 
                    email=email, 
                    affiliation=affiliation, 
                    password=hashlib.md5(password).hexdigest(), 
                    credit=credit)

    app.db.session.add(user)

    try:
        app.db.session.commit()
        return user
    except Exception:
        app.db.session.rollback()

def auth_user(username, password):
    """Return a User object if the specified (username, password) combination
    is valid. False otherwise."""
    res = app.User.query.filter_by(username=username, 
        password=hashlib.md5(password).hexdigest()).first()

    if res:
        return res

    return False

if __name__ == "__main__":
    try:
        email, username, password = sys.argv[1:]
        create_user(username, "", "", email, "", password, 120)
    except ValueError:
        print "Usage: %s email username password" % sys.argv[0]
