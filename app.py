from flask import Flask, jsonify, helpers, request
from flask.ext.sqlalchemy import SQLAlchemy

import os
import hashlib
import simplejson
from datetime import datetime

import common
# Add ConPaaS src to PYTHONPATH
common.extend_path()
import actions

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = common.config.get(
    'director', 'DATABASE_URI')
db = SQLAlchemy(app)

def create_user(username, fname, lname, email, affiliation, password, credit):
    """Create a new user with the given attributes. Return a new User object
    in case of successful creation. None otherwise."""
    user = User(username=username, 
                    fname=fname, 
                    lname=lname, 
                    email=email, 
                    affiliation=affiliation, 
                    password=hashlib.md5(password).hexdigest(), 
                    credit=credit)

    db.session.add(user)

    try:
        db.session.commit()
        return user
    except Exception:
        db.session.rollback()

def auth_user(username, password):
    """Return a User object if the specified (username, password) combination
    is valid. False otherwise."""
    res = User.query.filter_by(username=username, 
        password=hashlib.md5(password).hexdigest()).first()

    if res:
        return res

    return False

@app.route("/start/<servicetype>", methods=['POST'])
def start(servicetype):
    """eg: POST /start/php

    POSTed values must contain username and password.

    Returns a dictionary with service data (manager's vmid and IP address,
    service name and ID) in case of successful authentication and correct
    service creation. An empty dictionary is returned otherwise.
    """
    user = auth_user(request.values.get('username', ''), 
        request.values.get('password', ''))

    if not user:
        # Authentication failed
        return jsonify({})

    # New service with default name, proper servicetype and user relationship
    s = Service(name="New %s service" % servicetype, type=servicetype, 
        user=user)
                
    db.session.add(s)
    # flush() is needed to get auto-incremented sid
    db.session.flush()
    s.manager, s.vmid = actions.start(servicetype, s.sid)
    db.session.commit()
    return jsonify(s.to_dict())

@app.route("/stop/<int:serviceid>", methods=['POST'])
def stop(serviceid):
    """eg: POST /stop/3

    POSTed values must contain username and password.

    Returns a boolean value. True in case of successful authentication and
    proper service termination. False otherwise.
    """
    user = auth_user(request.values.get('username', ''), 
        request.values.get('password', ''))

    if user:
        # Authentication succeeded
        s = Service.query.filter_by(sid=serviceid).first()
        if s and s in user.services:
            # If a service with id 'serviceid' exists and user is the owner
            actions.stop(s.vmid)
            db.session.delete(s)
            db.session.commit()
            return simplejson.dumps(True)

    return simplejson.dumps(False)

@app.route("/download/ConPaaS.tar.gz", methods=['GET'])
def download():
    """GET /download/ConPaaS.tar.gz

    Returns ConPaaS tarball.
    """
    return helpers.send_from_directory(os.path.dirname(__file__), 
        "ConPaaS.tar.gz")

@app.route("/callback/decrementUserCredit.php", methods=['POST'])
def credit():
    """POST /callback/decrementUserCredit.php

    POSTed values must contain sid and decrement.

    Returns a dictionary with the 'error' attribute set to False if the user
    had enough credit, True otherwise.
    """
    service_id = int(request.values.get('sid', -1))
    decrement  = int(request.values.get('decrement', 0))

    s = Service.query.filter_by(sid=service_id).first()
    if not s:
        # The given service does not exist
        return jsonify({ 'error': True })
    
    if request.remote_addr and request.remote_addr != s.manager:
        # Possible attack: the request is coming from an IP address which is
        # NOT the manager's
        return jsonify({ 'error': True })

    # Decrement user's credit
    s.user.credit -= decrement

    if s.user.credit > -1:
        # User has enough credit
        db.session.commit()
        return jsonify({ 'error': False })

    # User does not have enough credit
    db.session.rollback()
    return jsonify({ 'error': True })

@app.route("/callback/terminateService.php")
def terminate():
    """To be implemented."""
    pass

class User(db.Model):
    uid = db.Column(db.Integer, primary_key=True, 
        autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    fname = db.Column(db.String(256))
    lname = db.Column(db.String(256))
    email = db.Column(db.String(256), unique=True)
    affiliation = db.Column(db.String(256))
    password = db.Column(db.String(256))
    created = db.Column(db.DateTime)
    credit = db.Column(db.Integer)

    def __init__(self, **kwargs):
        # Default values
        self.credit = 0
        self.created = datetime.now()

        for key, val in kwargs.items():
            setattr(self, key, val)

class Service(db.Model):
    sid = db.Column(db.Integer, primary_key=True, 
        autoincrement=True)
    name = db.Column(db.String(256))
    type = db.Column(db.String(32))
    state = db.Column(db.String(32))
    created = db.Column(db.DateTime)
    manager = db.Column(db.String(512))
    vmid = db.Column(db.String(256))

    user_id = db.Column(db.Integer, db.ForeignKey('user.uid'))
    user = db.relationship('User', backref=db.backref('services', 
        lazy="dynamic"))

    def __init__(self, **kwargs):
        # Default values
        self.state = "INIT"
        self.created = datetime.now()

        for key, val in kwargs.items():
            setattr(self, key, val)

    def to_dict(self):
        ret = {}
        for c in self.__table__.columns:
            ret[c.name] = getattr(self, c.name)
            if type(ret[c.name]) is datetime:
                ret[c.name] = ret[c.name].isoformat()

        return ret

if __name__ == "__main__":
    db.create_all()
    app.run(host="0.0.0.0", debug=True)
