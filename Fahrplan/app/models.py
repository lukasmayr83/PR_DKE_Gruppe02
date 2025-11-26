from __future__ import annotations

import enum
from typing import Optional, List

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
    strecke_id: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)

    fahrten: so.Mapped[List["Fahrtdurchfuehrung"]] = so.relationship(
        back_populates="halteplan",
        cascade="all, delete-orphan"
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
    zug_id: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)

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
    )

    def __repr__(self):
        return f"<Fahrt {self.fahrt_id} status={self.status.value}>"




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
        sa.ForeignKey("fahrtdurchfuehrung.fahrt_id"), nullable=False
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