"""
ConPaaS director: authentication module
"""

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
    """Return True if the specified (username, password) combination is valid.
    False otherwise."""
    res = app.User.query.filter_by(username=username, 
        password=hashlib.md5(password).hexdigest()).first()
    return res is not None

if __name__ == "__main__":
    app.db.create_all()
    u = create_user("ema", "Emanuele", "Rocca", "ema@linux.it", 
        "VU University Amsterdam", "testpass", 120)

    print auth_user("ema2", "testpass")
    print auth_user("ema", "testpassa")
    print auth_user("ema", "testpass")
