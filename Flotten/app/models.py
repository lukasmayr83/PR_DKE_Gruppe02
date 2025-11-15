from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from app import login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import enum

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

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Wagen (db.Model):
    __tablename__ = 'wagen'

    wagenid: so.Mapped[int] = so.mapped_column(primary_key=True)
    spurweite: so.Mapped[float] = so.mapped_column(sa.Float, nullable=False)
    istfrei: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer, default=None)

    type: so.Mapped[str] = so.mapped_column(sa.String(50), nullable=False)

    __mapper_args__ = {
        "polymorphic_on" : "type",
        "polymorphic_abstract" : True
    }

    def __repr__(self):
        return "<{self.__class__.__name__}(ID={self.wagenid})>"

class Personenwagen (Wagen):
    __tablename__ = 'personenwagen'

    personenwagenid: so.Mapped[int] = so.mapped_column(sa.ForeignKey('wagen.wagenid'), primary_key=True)
    kapazitaet: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    maxgewicht: so.Mapped[float] = so.mapped_column(sa.Float,nullable=False)

    __mapper_args__ = {
        "polymorphic_identity" : "personenwagen",
    }

class Triebwagen(Wagen):
    __tablename__ = 'triebwagen'

    triebwagenid: so.Mapped[int] = so.mapped_column(sa.ForeignKey('wagen.wagenid'),primary_key=True)

    maxzugkraft: so.Mapped[float] = so.mapped_column(sa.Float, nullable=False)

    __mapper_args__ = {
        "polymorphic_identity" : "triebwagen",
    }