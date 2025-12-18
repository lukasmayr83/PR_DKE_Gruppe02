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


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Zu welchem User gehört das Ticket
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    # Status + Metadaten
    erstelltAm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="aktiv")  # "aktiv", "storniert"

    # Wo steige ich ein / aus + Info zum Umstieg
    start_halt = db.Column(db.String(120), nullable=False)
    ziel_halt = db.Column(db.String(120), nullable=False)
    anzahl_umstiege = db.Column(db.Integer, nullable=False, default=0)

    # Fahrtdaten (für Anzeige in "Meine Tickets")
    abfahrt = db.Column(db.DateTime, nullable=False)
    ankunft = db.Column(db.DateTime, nullable=False)

    # Referenzen auf das Fahrplan-System (vereinfachte IDs)
    fahrt_id = db.Column(db.Integer, nullable=False)
    halteplan_id = db.Column(db.Integer, nullable=True)

    # Preis +Sitzplatz
    gesamtPreis = db.Column(db.Float, nullable=False)
    sitzplatzReservierung = db.Column(db.Boolean, nullable=False, default=False)

    # Aktion (falls verwendet)
    aktion_id = db.Column(db.Integer, db.ForeignKey("aktion.id", ondelete="SET NULL"), nullable=True)

 # obsolet? backref debugging
    kunde = db.relationship("User", backref=db.backref("tickets", lazy=True, passive_deletes=True))
    aktion = db.relationship("Aktion", backref=db.backref("tickets", lazy=True, passive_deletes=True))

    def __repr__(self):
        return f"<Ticket {self.id} ({self.start_halt} -> {self.ziel_halt})>"
