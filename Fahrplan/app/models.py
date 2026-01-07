from __future__ import annotations

import enum
from typing import Optional, List
from datetime import datetime


import sqlalchemy as sa
import sqlalchemy.orm as so

from app import db, login

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


# ---------------------------------------------------
#  USER LOGIN
# ---------------------------------------------------

@login.user_loader
def load_user(id: str):
    return db.session.get(User, int(id))


class Role(enum.Enum):
    ADMIN = "Admin"
    MITARBEITER = "Mitarbeiter"


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    role: so.Mapped[Role] = so.mapped_column(
        sa.Enum(Role), nullable=False, default=Role.MITARBEITER
    )

    # 1:1 Beziehung zu Mitarbeiter
    mitarbeiter: so.Mapped["Mitarbeiter"] = so.relationship(
        back_populates="user", uselist=False
    )

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN



class FahrtdurchfuehrungStatus(enum.Enum):
    PLANMAESSIG = "planmäßig"
    VERSPAETET = "verspätet"
    AUSGEFALLEN = "ausgefallen"



class Halteplan(db.Model):
    __tablename__ = "halteplan"

    halteplan_id: so.Mapped[int] = so.mapped_column(primary_key=True)
    bezeichnung: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)

    strecke_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("strecke.id"), nullable=False, index=True
    )

    strecke: so.Mapped["Strecke"] = so.relationship("Strecke")

    fahrten: so.Mapped[List["Fahrtdurchfuehrung"]] = so.relationship(
        back_populates="halteplan",
        cascade="all, delete-orphan"
    )

    haltepunkte: so.Mapped[List["Haltepunkt"]] = so.relationship(
        "Haltepunkt",
        order_by="Haltepunkt.position",
        cascade="all, delete-orphan"
    )

    segmente: so.Mapped[List["HalteplanSegment"]] = so.relationship(
        "HalteplanSegment",
        order_by="HalteplanSegment.position",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Halteplan {self.halteplan_id} {self.bezeichnung}>"



class Fahrtdurchfuehrung(db.Model):
    __tablename__ = "fahrtdurchfuehrung"

    fahrt_id: so.Mapped[int] = so.mapped_column(primary_key=True)
    halteplan_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("halteplan.halteplan_id"), nullable=False
    )

    # extern
    zug_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("zug.id"), nullable=False, index=True
    )
    zug: so.Mapped["Zug"] = so.relationship("Zug")

    status: so.Mapped[FahrtdurchfuehrungStatus] = so.mapped_column(
        sa.Enum(FahrtdurchfuehrungStatus),
        nullable=False,
        default=FahrtdurchfuehrungStatus.PLANMAESSIG,
    )

    verspaetung_min: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer)

    halteplan: so.Mapped["Halteplan"] = so.relationship(back_populates="fahrten")

    dienstzuweisungen: so.Mapped[List["Dienstzuweisung"]] = so.relationship(
        back_populates="fahrt",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    halte: so.Mapped[List["FahrtHalt"]] = so.relationship(
        "FahrtHalt",
        back_populates="fahrt",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    segmente: so.Mapped[List["FahrtSegment"]] = so.relationship(
        "FahrtSegment",
        back_populates="fahrt",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    abfahrt_zeit: so.Mapped[datetime] = so.mapped_column(sa.DateTime(), nullable=False)
    price_factor: so.Mapped[float] = so.mapped_column(sa.Float, nullable=False, default=1.0)

    __table_args__ = (
        sa.CheckConstraint("price_factor >= 1", name="ck_fahrt_price_factor_ge1"),
    )

    def __repr__(self):
        return f"<Fahrt {self.fahrt_id} status={self.status.value}>"


class FahrtHalt(db.Model):
    __tablename__ = "fahrt_halt"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)

    fahrt_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("fahrtdurchfuehrung.fahrt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    bahnhof_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("bahnhof.id"), nullable=False, index=True
    )

    fahrt: so.Mapped["Fahrtdurchfuehrung"] = so.relationship(
        "Fahrtdurchfuehrung",
        back_populates="halte",
    )

    position: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)

    # abgeleitet aus abfahrt_zeit + segment-durations
    ankunft_zeit: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(), nullable=True)
    abfahrt_zeit: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(), nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("fahrt_id", "position", name="uq_fahrt_halt_pos"),
    )


class FahrtSegment(db.Model):
    __tablename__ = "fahrt_segment"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)

    fahrt_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("fahrtdurchfuehrung.fahrt_id", ondelete="CASCADE"), nullable=False, index=True
    )

    von_halt_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("fahrt_halt.id"), nullable=False
    )
    nach_halt_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("fahrt_halt.id"), nullable=False
    )

    position: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)

    final_price: so.Mapped[float] = so.mapped_column(sa.Float, nullable=False)
    duration_min: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=0)

    fahrt: so.Mapped["Fahrtdurchfuehrung"] = so.relationship(
        "Fahrtdurchfuehrung",
        back_populates="segmente",
    )

    __table_args__ = (
        sa.UniqueConstraint("fahrt_id", "position", name="uq_fahrt_seg_pos"),
        sa.CheckConstraint("final_price >= 0", name="ck_fahrt_seg_price_nonneg"),
    )




class Mitarbeiter(db.Model):
    __tablename__ = "mitarbeiter"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)

    # Verknüpfung zu User (1:1)
    user_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("user.id"), unique=True, nullable=False
    )
    user: so.Mapped["User"] = so.relationship(back_populates="mitarbeiter")

    dienstzuweisungen: so.Mapped[List["Dienstzuweisung"]] = so.relationship(
        back_populates="mitarbeiter",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Mitarbeiter {self.id} {self.name}>"



class Dienstzuweisung(db.Model):
    __tablename__ = "dienstzuweisung"

    dienst_id: so.Mapped[int] = so.mapped_column(primary_key=True)

    fahrt_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("fahrtdurchfuehrung.fahrt_id", ondelete="CASCADE"), nullable=False, index=True,
    )
    mitarbeiter_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("mitarbeiter.id"), nullable=False
    )

    fahrt: so.Mapped["Fahrtdurchfuehrung"] = so.relationship(
        back_populates="dienstzuweisungen"
    )
    mitarbeiter: so.Mapped["Mitarbeiter"] = so.relationship(
        back_populates="dienstzuweisungen"
    )

    def __repr__(self):
        return (
            f"<Dienst {self.dienst_id} fahrt={self.fahrt_id} ma={self.mitarbeiter_id}>"
        )






class Haltepunkt(db.Model):
    __tablename__ = "haltepunkt"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)

    halteplan_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("halteplan.halteplan_id"), nullable=False, index=True
    )

    bahnhof_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("bahnhof.id"), nullable=False, index=True
    )

    position: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)

    halte_dauer_min: so.Mapped[int] = so.mapped_column(
        sa.Integer, nullable=False, default=0
    )

    __table_args__ = (
        sa.UniqueConstraint("halteplan_id", "position", name="uq_haltepunkt_pos"),
    )


class HalteplanSegment(db.Model):
    __tablename__ = "halteplan_segment"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)

    halteplan_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("halteplan.halteplan_id"), nullable=False, index=True
    )

    von_haltepunkt_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("haltepunkt.id"), nullable=False, index=True
    )
    nach_haltepunkt_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("haltepunkt.id"), nullable=False, index=True
    )

    position: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)

    base_price: so.Mapped[float] = so.mapped_column(sa.Float, nullable=False, default=0.0)
    duration_min: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=0)

    min_cost: so.Mapped[float] = so.mapped_column(sa.Float, nullable=False, default=0.0)  # Nutzungsentgelt-Summe

    __table_args__ = (
        sa.UniqueConstraint("halteplan_id", "position", name="uq_hpseg_pos"),
        sa.CheckConstraint("base_price >= 0", name="ck_hpseg_base_price_nonneg"),
        sa.CheckConstraint("duration_min >= 0", name="ck_hpseg_duration_nonneg"),
        sa.CheckConstraint("min_cost >= 0", name="ck_hpseg_mincost_nonneg"),
        sa.CheckConstraint("von_haltepunkt_id <> nach_haltepunkt_id", name="ck_hpseg_from_to_diff"),
    )




############## Externe Tables/Synchonisierte tables ####################


class Bahnhof(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.Integer, unique=True)  # aus Strecken
    name = db.Column(db.String(100))


class Abschnitt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.Integer, unique=True)

    spurweite = db.Column(db.Float)
    max_geschwindigkeit = db.Column(db.Integer)
    nutzungsentgelt = db.Column(db.Float)
    laenge = db.Column(db.Float)

    start_bahnhof_id = db.Column(db.Integer, db.ForeignKey("bahnhof.id"))
    end_bahnhof_id = db.Column(db.Integer, db.ForeignKey("bahnhof.id"))



class Strecke(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.Integer, unique=True)
    name = db.Column(db.String(100))



class StreckeAbschnitt(db.Model):
    strecke_id = db.Column(db.Integer, db.ForeignKey("strecke.id"), primary_key=True)
    abschnitt_id = db.Column(db.Integer, db.ForeignKey("abschnitt.id"), primary_key=True)
    position = db.Column(db.Integer)


class Zug(db.Model):
    __tablename__ = "zug"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)

    # aus Flotten-Service: zugId
    external_id: so.Mapped[int] = so.mapped_column(sa.Integer, unique=True, index=True, nullable=False)

    bezeichnung: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, nullable=False)

    spurweite: so.Mapped[float | None] = so.mapped_column(sa.Float, nullable=True)

    wartungen: so.Mapped[list["ZugWartung"]] = so.relationship(
        "ZugWartung",
        back_populates="zug",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Zug ext={self.external_id} {self.bezeichnung}>"


class ZugWartung(db.Model):
    __tablename__ = "zug_wartung"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)

    zug_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("zug.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    external_wartungszeitid: so.Mapped[int] = so.mapped_column(
        sa.Integer,
        nullable=False,
        index=True,
    )

    von: so.Mapped[datetime] = so.mapped_column(sa.DateTime(), nullable=False)
    bis: so.Mapped[datetime] = so.mapped_column(sa.DateTime(), nullable=False)

    zug: so.Mapped["Zug"] = so.relationship("Zug", back_populates="wartungen")

    __table_args__ = (
        sa.UniqueConstraint("zug_id", "external_wartungszeitid", name="uq_zugwartung_zug_ext"),
        sa.CheckConstraint("bis > von", name="ck_zugwartung_bis_gt_von"),
    )
