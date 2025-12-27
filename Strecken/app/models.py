from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import CheckConstraint
import sqlalchemy.orm as so
import enum
from app import db
from app import login
import requests
from hashlib import md5
from datetime import datetime
from geopy.geocoders import Nominatim
from typing import List

#############################################################
#################      User      ############################
#############################################################

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


class RoleEnum(enum.Enum):
    admin = "admin" #kann alles bearbeiten und löschen
    mitarbeiter = "mitarbeiter" # kann nur die Dinge anschauen


class User( UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256)) #Hash für Paswort

    role: so.Mapped[RoleEnum] = so.mapped_column(
        sa.Enum(RoleEnum),
        nullable=False,
        server_default=RoleEnum.mitarbeiter.value
    )

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    #generiert automatisch einen Avatar aus der
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'

#############################################################
#################     Bahnhof    ############################
#############################################################

class Bahnhof (db.Model):
    __tablename__ = 'bahnhof'
    bahnhofId: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    adresse: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    latitude: so.Mapped[float] = so.mapped_column(sa.Float, nullable=True)
    longitude: so.Mapped[float] = so.mapped_column(sa.Float, nullable=True)

    #Wandelt übergebene Adresse des übergebenen Bahnhofs in Koordinaten um indem sie nominatim aufruft
    def geocode_address(self):
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "format": "json",
            "q": self.adresse
        }

        response = requests.get(url, params=params, headers={"User-Agent": "Strecken_App"})
        data = response.json()

        if data:
            self.latitude = float(data[0]["lat"])
            self.longitude = float(data[0]["lon"])

    #Realtionships: geben alle Abschnitte zurück der Bahnhöfe zurück
    start_abschnitte: so.Mapped[list['Abschnitt']] = so.relationship(
            "Abschnitt",
            back_populates="startBahnhof",
            primaryjoin="Bahnhof.bahnhofId == Abschnitt.startBahnhofId"
    )
    end_abschnitte: so.Mapped[list['Abschnitt']] = so.relationship(
            "Abschnitt",
            back_populates="endBahnhof",
            primaryjoin="Bahnhof.bahnhofId == Abschnitt.endBahnhofId"
    )


#############################################################
#################     Warnung    ############################
#############################################################

#Assoziationstabelle für M2M-Beziehung zwischen Abschnitt und Warnung
abschnitt_warnung_m2m = sa.Table(
    'abschnitt_warnung',
    db.metadata,
    sa.Column('abschnitt_id', sa.Integer, sa.ForeignKey('abschnitt.abschnittId'), primary_key=True),
    sa.Column('warnung_id', sa.Integer, sa.ForeignKey('warnung.warnungId'), primary_key=True)
)


class Warnung(db.Model):
    __tablename__ = 'warnung'

    warnungId: so.Mapped[int] = so.mapped_column(primary_key=True)
    bezeichnung: so.Mapped[str] = so.mapped_column(sa.String(100))
    beschreibung: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    startZeit: so.Mapped[datetime] = so.mapped_column()
    endZeit: so.Mapped[Optional[datetime]] = so.mapped_column()

    abschnitte: so.Mapped[list["Abschnitt"]] = so.relationship(
        "Abschnitt",
        secondary=abschnitt_warnung_m2m,
        back_populates="warnungen"
    )


#############################################################
#################    Abschnitt   ############################
#############################################################

class Abschnitt(db.Model):
    __tablename__ = 'abschnitt'

    abschnittId: so.Mapped[int] = so.mapped_column(primary_key=True)
    spurweite: so.Mapped[float] = so.mapped_column()
    nutzungsentgelt: so.Mapped[float] = so.mapped_column()
    max_geschwindigkeit: so.Mapped[int] = so.mapped_column()
    laenge: so.Mapped[float] = so.mapped_column()

    #FK zu Bahnhöfen
    startBahnhofId: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey('bahnhof.bahnhofId'),
        index=True,
        nullable=False
    )
    endBahnhofId: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey('bahnhof.bahnhofId'),
        index=True,
        nullable=False
    )

    #Relationship
    startBahnhof: so.Mapped["Bahnhof"] = so.relationship(
        "Bahnhof",
        foreign_keys=[startBahnhofId],
        back_populates="start_abschnitte"
    )
    endBahnhof: so.Mapped["Bahnhof"] = so.relationship(
        "Bahnhof",
        foreign_keys=[endBahnhofId],
        back_populates="end_abschnitte"
    )

    warnungen: so.Mapped[list["Warnung"]] = so.relationship(
        "Warnung",
        secondary=abschnitt_warnung_m2m,
        back_populates="abschnitte"
    )

    #DB prüft, ob Start- und Endbahnhof unterschiedlich sind
    __table_args__ = (
        db.CheckConstraint(
            "startBahnhofId <> endBahnhofId",
            name="check_start_end_ungleich"
        ),
    )

    #erstellt einen Namen aus Start- und Endbahnhof
    @property
    def name(self):
        return f"{self.startBahnhof.name} → {self.endBahnhof.name}"




#############################################################
#################   Reigenfolge  ############################
#############################################################

class Reihenfolge(db.Model):
    __tablename__ = 'strecke_abschnitt'
    #PK besteht aus StreckeId und AbschnittId
    streckeId: so.Mapped[int] = so.mapped_column(sa.ForeignKey('strecken.streckenId'), primary_key=True)
    abschnittId: so.Mapped[int] = so.mapped_column(sa.ForeignKey('abschnitt.abschnittId'), primary_key=True)
    reihenfolge: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    abschnitt: so.Mapped['Abschnitt'] = so.relationship(backref="strecken_abschnitt_ref") #Relationship

    __table_args__ = (db.UniqueConstraint('streckeId', 'reihenfolge', name='_strecke_reihenfolge_uc'),)




#############################################################
#################    Strecke     ############################
#############################################################

class Strecke(db.Model):
    __tablename__ = 'strecken'

    streckenId: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False, unique=True)

    #Relationship
    reihenfolge: so.Mapped[List['Reihenfolge']] = so.relationship(
        'Reihenfolge',
        order_by='Reihenfolge.reihenfolge',
        cascade='all, delete-orphan'
    )

    #gibt Abschnitte in der Reihenfolge zurück
    @property
    def abschnitte_in_reihenfolge(self):
        return [verbindung.abschnitt for verbindung in self.reihenfolge]

    #ermittelt den Start- und Endbahnhof der Strecke
    @property
    def start_end_bahnhoefe(self):
        abschnitte = self.abschnitte_in_reihenfolge
        if not abschnitte:
            return None, None

        start_bhf = abschnitte[0].startBahnhof #Start-Bahnhof der Strecke = StartBahnhof des ersten Abschnitts
        end_bhf = abschnitte[-1].endBahnhof #End-Bahnhof der Strecke = EndBahnhof des letzten Abschnitts

        return start_bhf, end_bhf