from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
import enum
from app import db
from app import login
from geopy.geocoders import Nominatim

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

class Bahnhof (db.Model):
    bahnhofId: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    adresse: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    latitude: so.Mapped[float] = so.mapped_column(sa.Float, nullable=True)
    longitude: so.Mapped[float] = so.mapped_column(sa.Float, nullable=True)

    def geocode_address(self): geolocator = Nominatim(user_agent="Lukas Mayr")

    def geocode_address(self):
        geolocator = Nominatim(user_agent="my_flask_app", timeout=10)
        location = geolocator.geocode(self.adresse)
        if location:
            self.latitude = location.latitude
            self.longitude = location.longitude


