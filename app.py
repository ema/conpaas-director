from flask import Flask, jsonify, helpers, request
from flask.ext.sqlalchemy import SQLAlchemy

import os
import simplejson
from datetime import datetime

import common
common.extend_path()
import actions

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = common.config.get(
    'director', 'DATABASE_URI')
db = SQLAlchemy(app)

@app.route("/start/<servicetype>")
def start(servicetype):
    s = Service(name="New %s service" % servicetype,
                type=servicetype)
                
    s.manager, s.vmid = actions.start(servicetype, s.sid)
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict())

@app.route("/stop/<int:serviceid>")
def stop(serviceid):
    s = Service.query.filter_by(sid=serviceid).first()
    if s:
        actions.stop(s.vmid)
        db.session.delete(s)
        db.session.commit()
        return simplejson.dumps(True)

    return simplejson.dumps(False)

@app.route("/download/ConPaaS.tar.gz", methods=['GET'])
def download():
    return helpers.send_from_directory(os.path.dirname(__file__), 
        "ConPaaS.tar.gz")

@app.route("/callback/decrementUserCredit.php", methods=['POST'])
def credit():
    service_id, decrement = request.values['sid'], request.values['decrement']
    return jsonify({ 'error': False })

@app.route("/callback/terminateService.php")
def terminate():
    pass

class User(db.Model):
    uid = db.Column(db.Integer, primary_key=True, 
        autoincrement=True)
    username = db.Column(db.String(80), unique=True)
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
