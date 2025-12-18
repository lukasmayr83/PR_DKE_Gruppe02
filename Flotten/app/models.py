from typing import Optional, List
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from app import login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import enum
from datetime import datetime, date

class Role(enum.Enum):
    ADMIN = "Admin"
    MITARBEITER = "Mitarbeiter"

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

class User(UserMixin,db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    role: so.Mapped[Role] = so.mapped_column(sa.Enum(Role), nullable=False, default=Role.MITARBEITER)
    mitarbeiter: so.Mapped["Mitarbeiter"] = so.relationship(back_populates="user",uselist=False) #1zu1 beziehung

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Zuege(db.Model):
    __tablename__ = 'zuege'

    zugid: so.Mapped[int] = so.mapped_column(primary_key=True)
    bezeichnung: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, nullable=False)

    wagen: so.Mapped[list['Wagen']] = so.relationship(back_populates='zug', lazy = "selectin")

    wartungen: so.Mapped[list["Wartung"]] = so.relationship(back_populates='zug')

# Gibt die ID des Triebwagens im Zug zurück
    @property
    def triebwagen_id(self):
        for w in self.wagen:
            if w.type == "triebwagen":
                return w.wagenid
        return None

# Gibt die ids aller Personenwagen in dem Zug zurück mit , getrennt
    @property
    def personenwagen_ids(self):
        ##Liste der Personenwagen im Zug
        personenwagen = []
        for w in self.wagen:
            if w.type == "personenwagen":
                personenwagen.append(str(w.wagenid))

        return ", ".join(personenwagen)

    @property
    def aktuelle_wartungs_anzeige(self) -> str:
       # Gibt die Wartungszeit-ID zurück, wenn der Zug aktuell in Wartung ist, andernfalls 'FALSE'.
        now = datetime.now()

        # Durchsuche alle Wartungen des Zuges
        for wartung in self.wartungen:
            wzr = wartung.wartungszeitraum

            start_dt = datetime.combine(wzr.datum, wzr.von.time())
            end_dt = datetime.combine(wzr.datum, wzr.bis.time())

            # Überprüfen ob die aktuelle Zeit im Wartungszeitraum liegt
            if start_dt <= now <= end_dt:
                return str(wzr.wartungszeitid)

        return "FALSE"

class Wagen (db.Model):
    __tablename__ = 'wagen'

    wagenid: so.Mapped[int] = so.mapped_column(primary_key=True)
    spurweite: so.Mapped[float] = so.mapped_column(sa.Float,index=True, nullable=False)
    istfrei: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('zuege.zugid', name="fk_wagen_zug_id"),index=True, nullable=True, default=None)

    zug: so.Mapped[Optional[Zuege]] = so.relationship(back_populates='wagen')

    type: so.Mapped[str] = so.mapped_column(sa.String(50), nullable=False)

    __mapper_args__ = {
        "polymorphic_on" : "type",
        "polymorphic_abstract" : True
    }

    def __repr__(self):
        return f"<{self.__class__.__name__}(ID={self.wagenid})>"

class Personenwagen (Wagen):
    __tablename__ = 'personenwagen'

    personenwagenid: so.Mapped[int] = so.mapped_column(sa.ForeignKey('wagen.wagenid'), primary_key=True)
    kapazitaet: so.Mapped[int] = so.mapped_column(sa.Integer, index=True, nullable=False)
    maxgewicht: so.Mapped[float] = so.mapped_column(sa.Float,index=True, nullable=False)

    __mapper_args__ = {
        "polymorphic_identity" : "personenwagen",
    }

class Triebwagen(Wagen):
    __tablename__ = 'triebwagen'

    triebwagenid: so.Mapped[int] = so.mapped_column(sa.ForeignKey('wagen.wagenid'),primary_key=True)

    maxzugkraft: so.Mapped[float] = so.mapped_column(sa.Float,index=True, nullable=False)

    __mapper_args__ = {
        "polymorphic_identity" : "triebwagen",
    }

class Mitarbeiter(db.Model):
    __tablename__ = 'mitarbeiter'

    svnr: so.Mapped[int] = so.mapped_column(primary_key=True)
    vorname: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, nullable=False)
    nachname: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, nullable=False)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user.id'), unique=True, nullable=False)

    user: so.Mapped["User"] = so.relationship(back_populates="mitarbeiter")

    wartungen: so.Mapped[list["Wartung"]] = so.relationship(back_populates="mitarbeiter",cascade="all, delete-orphan")

class Wartungszeitraum(db.Model):
    __tablename__ = 'wartungszeitraum'

    wartungszeitid: so.Mapped[int] = so.mapped_column(primary_key=True)
    datum: so.Mapped[date] = so.mapped_column(sa.Date, index=True, nullable=False)
    von: so.Mapped[datetime] = so.mapped_column(sa.DateTime, nullable=False)
    bis: so.Mapped[datetime] = so.mapped_column(sa.DateTime, nullable=False)
    dauer: so.Mapped[int] = so.mapped_column(sa.Integer,nullable=False)

    wartungen: so.Mapped[list["Wartung"]] = so.relationship(back_populates="wartungszeitraum")

    # Composite Unique Constraint - Kombination der drei Spalten muss in der gesamten Tabelle eindeutig sein
    __table_args__ = (
        sa.UniqueConstraint('datum', 'von', 'bis', name='unique_datum_von_bis'),
    )


class Wartung(db.Model):
    __tablename__ = 'wartung'

    wartungid: so.Mapped[int] = so.mapped_column(primary_key=True)

    svnr: so.Mapped[int] = so.mapped_column(sa.ForeignKey("mitarbeiter.svnr", ondelete="cascade"))
    zugid: so.Mapped[int] = so.mapped_column(sa.ForeignKey("zuege.zugid"))
    wartungszeitid: so.Mapped[int] = so.mapped_column(sa.ForeignKey("wartungszeitraum.wartungszeitid"))

    mitarbeiter: so.Mapped["Mitarbeiter"] = so.relationship(back_populates="wartungen")
    zug: so.Mapped["Zuege"] = so.relationship(back_populates="wartungen")
    wartungszeitraum: so.Mapped["Wartungszeitraum"] = so.relationship(back_populates="wartungen")
