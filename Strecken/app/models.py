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
    admin = "admin"
    mitarbeiter = "mitarbeiter"


class User( UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))

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

    def __repr__(self):
        return f'<Warnung {self.warnungId}: {self.bezeichnung}>'

#############################################################
#################    Abschnitt   ############################
#############################################################

class Abschnitt(db.Model):
    __tablename__ = 'abschnitt'

    abschnittId: so.Mapped[int] = so.mapped_column(primary_key=True)
    spurweite: so.Mapped[float] = so.mapped_column()
    nutzungsentgelt: so.Mapped[float] = so.mapped_column()
    max_geschwindigkeit: so.Mapped[int] = so.mapped_column()

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


    def warnung_hinzufuegen(self, warnung):
        if not self.hat_warnung(warnung):
            self.warnungen.add(warnung)

    def warnung_entfernen(self, warnung):
        if self.hat_warnung(warnung):
            self.warnungen.remove(warnung)

    def hat_warnung(self, warnung):
        query = self.warnungen.select().where(
            Warnung.warnungId == warnung.warnungId
        )
        return db.session.scalar(query) is not None

#############################################################
#################   Reigenfolge  ############################
#############################################################

class Reihenfolge(db.Model):
    __tablename__ = 'strecke_abschnitt'


    streckeId: so.Mapped[int] = so.mapped_column(sa.ForeignKey('strecken.streckenId'), primary_key=True)
    abschnittId: so.Mapped[int] = so.mapped_column(sa.ForeignKey('abschnitt.abschnittId'), primary_key=True)
    reihenfolge: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    abschnitt: so.Mapped['Abschnitt'] = so.relationship(backref="strecken_abschnitt_ref")


    __table_args__ = (db.UniqueConstraint('streckeId', 'reihenfolge', name='_strecke_reihenfolge_uc'),)

    def __repr__(self):
        return f"<Reihenfolge StreckeID={self.streckeId} AbschnittID={self.abschnittId} Pos={self.reihenfolge}>"



#############################################################
#################    Strecke     ############################
#############################################################

class Strecke(db.Model):
    __tablename__ = 'strecken'

    streckenId: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False, unique=True)


    reihenfolge: so.Mapped[List['Reihenfolge']] = so.relationship(
        'Reihenfolge',
        order_by='Reihenfolge.reihenfolge',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Strecke {self.name}>"

    @property
    def abschnitte_in_reihenfolge(self):
        return [verbindung.abschnitt for verbindung in self.reihenfolge]

    @property
    def start_end_bahnhoefe(self):
        abschnitte = self.abschnitte_in_reihenfolge
        if not abschnitte:
            return None, None

        start_bhf = abschnitte[0].startBahnhof
        end_bhf = abschnitte[-1].endBahnhof

        return start_bhf, end_bhf