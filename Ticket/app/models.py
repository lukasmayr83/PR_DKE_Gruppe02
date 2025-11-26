from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)

    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    birthdate = db.Column(db.Date)

    password_hash = db.Column(db.String(256), nullable=False)


    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Aktion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    beschreibung = db.Column(db.Text, nullable=True)
    startZeit = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    endeZeit = db.Column(db.DateTime, nullable=False)
    aktiv = db.Column(db.Boolean, default=False, nullable=False)
    rabattWert = db.Column(db.Float, default=0.0, nullable=False)  # Prozent
    typ = db.Column(db.String(20), nullable=False)  # "global" oder "halteplan"
    halteplanId = db.Column(db.Integer, nullable=True)  # falls typ="halteplan"

    def __repr__(self) -> str:
        return f"<Aktion {self.name} ({self.typ})>"
