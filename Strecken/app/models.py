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

@login.user_loader #Decorator für Flask Login
#Funktion, die einen User anhand seiner Id aus der DB lädt
def load_user(id):
    return db.session.get(User, int(id))

#Enumeration-Klasse für Benutzerrollen (admin & Mitarbeiter)
class RoleEnum(enum.Enum):
    admin = "admin" #kann alles bearbeiten und löschen
    mitarbeiter = "mitarbeiter" # kann nur die Dinge anschauen

#User-Modell
class User( UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True) #PK
    #Benutzername: einzigartiger String mit max. 64 Zeichen
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    # Email: einzigartiger String mit max. 120 Zeichen
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    # Hash für Passwort (max 256 Zeichen)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))

    #Benutzerrolle: verwendet RoleEnum von oben; kann nicht null sein; standardmäßig MA
    role: so.Mapped[RoleEnum] = so.mapped_column(
        sa.Enum(RoleEnum),
        nullable=False,
        server_default=RoleEnum.mitarbeiter.value
    )

    # String-Repräsentation des User-Objekts für Debugging
    def __repr__(self):
        return '<User {}>'.format(self.username)

    #Methode: um Passwort zu setzen
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    #Methode: um Passwort zu überprüfen
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    #generiert automatisch einen Avatar aus der Email
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'

#############################################################
#################     Bahnhof    ############################
#############################################################

#Bahnhof-Modell
class Bahnhof (db.Model):
    __tablename__ = 'bahnhof' #Tabellenname in der DB
    bahnhofId: so.Mapped[int] = so.mapped_column(primary_key=True) #PK
    #Name des Bahnhofs: einzigartiger STring mit max. 64 Zeichen
    name: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    #Adresse des Bahnhofs: einzigartiger STring mit max. 120 Zeichen
    adresse: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    #Breitengrad: Float + kann null sein
    latitude: so.Mapped[float] = so.mapped_column(sa.Float, nullable=True)
    # Längengrad: Float + kann null sein
    longitude: so.Mapped[float] = so.mapped_column(sa.Float, nullable=True)

    #Wandelt übergebene Adresse des übergebenen Bahnhofs in Koordinaten um indem sie nominatim aufruft
    #wird 7 Mal von routes.py aufgerufen
    def geocode_address(self):
        url = "https://nominatim.openstreetmap.org/search" #URL für Nominatim Geocoding-API
        #Parameter für die API-Abfrage
        params = {
            "format": "json",
            "q": self.adresse
        }
        # Sendet GET-Request an Nominatim mit User-Agent Header
        response = requests.get(url, params=params, headers={"User-Agent": "Strecken_App"})
        data = response.json() #JSON parsen

        if data: #wenn Ergebnisse vorhanden sind
            self.latitude = float(data[0]["lat"]) #setzt Breitengrad aus dem ersten Ergebnis (Erste Ergebnis = beste Ergebnis)
            self.longitude = float(data[0]["lon"]) #setzt Längengrad aus dem ersten Ergebnis (Erste Ergebnis = beste Ergebnis)

    # Relationship: Alle Abschnitte, bei denen dieser Bahnhof der Startbahnhof ist
    start_abschnitte: so.Mapped[list['Abschnitt']] = so.relationship(
            "Abschnitt",
            back_populates="startBahnhof", # Rückwärts-Referenz im Abschnitt-Modell
            primaryjoin="Bahnhof.bahnhofId == Abschnitt.startBahnhofId" # Join-Bedingung: verknüpft bahnhofId mit startBahnhofId
    )
    # Relationship: Alle Abschnitte, bei denen dieser Bahnhof der Endbahnhof ist
    end_abschnitte: so.Mapped[list['Abschnitt']] = so.relationship(
            "Abschnitt",
            back_populates="endBahnhof", # Rückwärts-Referenz im Abschnitt-Modell
            primaryjoin="Bahnhof.bahnhofId == Abschnitt.endBahnhofId" # Join-Bedingung: verknüpft bahnhofId mit endBahnhofId
    )


#############################################################
#################     Warnung    ############################
#############################################################

#Assoziationstabelle für M2M-Beziehung zwischen Abschnitt und Warnung
abschnitt_warnung_m2m = sa.Table(
    'abschnitt_warnung', #Name der Tabelle in der DB
    db.metadata, #Metadata-Objekt in der DB
    #FK zu Abschnitt; Teil des zusammengesetzten PK
    sa.Column('abschnitt_id', sa.Integer, sa.ForeignKey('abschnitt.abschnittId'), primary_key=True),
    #FK zu Warnung; Teil des zusammengesetzten PK
    sa.Column('warnung_id', sa.Integer, sa.ForeignKey('warnung.warnungId'), primary_key=True)
)

#Warnung-Modell
class Warnung(db.Model):
    __tablename__ = 'warnung' #Name der Tabelle in der DB

    warnungId: so.Mapped[int] = so.mapped_column(primary_key=True) #PK
    # Bezeichnung der Warnung: String mit max. 100 Zeichen
    bezeichnung: so.Mapped[str] = so.mapped_column(sa.String(100))
    #Beschreibung der Warnung: Textfeld; optional
    beschreibung: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    #Startzeit der Warnung
    startZeit: so.Mapped[datetime] = so.mapped_column()
    # Endzeit der Warnung: kann null sein
    endZeit: so.Mapped[Optional[datetime]] = so.mapped_column()

    # Relationship: Alle Abschnitte, die von dieser Warnung betroffen sind

    abschnitte: so.Mapped[list["Abschnitt"]] = so.relationship(
        "Abschnitt",
        secondary=abschnitt_warnung_m2m, # Assoziationstabelle für Many-to-Many Beziehung
        back_populates="warnungen" # Rückwärts-Referenz im Abschnitt-Modell
    )


#############################################################
#################    Abschnitt   ############################
#############################################################

#Abschnitt-Modell
class Abschnitt(db.Model):
    __tablename__ = 'abschnitt' #Tabellenname in der DB

    abschnittId: so.Mapped[int] = so.mapped_column(primary_key=True) #PK
    #Spurweite des Abschnitts: FLoat-Wert
    spurweite: so.Mapped[float] = so.mapped_column()
    #Nutzungsentgelt des Abschnitts: FLoat-Wert
    nutzungsentgelt: so.Mapped[float] = so.mapped_column()
    # max. Geschwindigkeit des Abschnitts: Integer-Wert (macht keinen sinn die max. Geschwindigkeit genauer anzugebn als eine ganze Zahl)
    max_geschwindigkeit: so.Mapped[int] = so.mapped_column()
    # Länge des Abschnitts: FLoat-Wert
    laenge: so.Mapped[float] = so.mapped_column()

    #FK: ID des Startbahnhofs
    startBahnhofId: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey('bahnhof.bahnhofId'), # Referenz auf bahnhofId in der Bahnhof-Tabelle
        index=True,
        nullable=False #darf nicht null sein
    )

    # FK: ID des Endbahnhofs
    endBahnhofId: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey('bahnhof.bahnhofId'), # Referenz auf bahnhofId in der Bahnhof-Tabelle
        index=True,
        nullable=False #darf nicht null sein
    )

    #Relationship: Referenz zum Startbahnhof-Objekt (damit ich später einfach Abschnitt.startBahnhof.name etc. shcreiben kann)
    startBahnhof: so.Mapped["Bahnhof"] = so.relationship(
        "Bahnhof", #Zielmodell der Beziehung
        foreign_keys=[startBahnhofId], #FK=startBahnhofId
        back_populates="start_abschnitte" # Rückwärts-Referenz im Bahnhof-Modell
    )
    # Relationship: Referenz zum Startbahnhof-Objekt
    endBahnhof: so.Mapped["Bahnhof"] = so.relationship(
        "Bahnhof", #Zielmodell der Beziehung
        foreign_keys=[endBahnhofId], #FK=startBahnhofId
        back_populates="end_abschnitte" # Rückwärts-Referenz im Bahnhof-Modell
    )

    # Relationship: Alle Warnungen für diesen Abschnitt
    warnungen: so.Mapped[list["Warnung"]] = so.relationship(
        "Warnung", #Zielmodell der Beziehung
        secondary=abschnitt_warnung_m2m, # Assoziationstabelle für Many-to-Many Beziehung
        back_populates="abschnitte"  # Rückwärts-Referenz im Warnung-Modell
    )

    #Constrints: DB prüft, ob Start- und Endbahnhof unterschiedlich sind
    __table_args__ = (
        db.CheckConstraint(
            "startBahnhofId <> endBahnhofId", # SQL-Bedingung: Startbahnhof ungleich EndBahnhof
            name="check_start_end_ungleich" # Name des Constraints in der Datenbank
        ),
    )

    #Property: erstellt einen Namen für den Abschnitt aus Start- und Endbahnhof
    @property
    def name(self):
        return f"{self.startBahnhof.name} → {self.endBahnhof.name}" #Name aus den Bahnhofsnamen + Pfeil dazwischen




#############################################################
#################   Reigenfolge  ############################
#############################################################

#Reihenfolge-Modell: definiert die Reihenfolge von Abschnitten in einer STrecke
class Reihenfolge(db.Model):
    __tablename__ = 'strecke_abschnitt'
    #PK besteht aus StreckeId und AbschnittId
    streckeId: so.Mapped[int] = so.mapped_column(sa.ForeignKey('strecken.streckenId'), primary_key=True) #FK zu Strecke
    abschnittId: so.Mapped[int] = so.mapped_column(sa.ForeignKey('abschnitt.abschnittId'), primary_key=True) #FK zu Abschnitt
    reihenfolge: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False) #Position des Abschnitts
    # Relationship: Referenz zum zugehörigen Abschnitt-Objekt
    abschnitt: so.Mapped['Abschnitt'] = so.relationship(backref="strecken_abschnitt_ref")
    #unique Constraint: Reihenfolge in Kombi mit StreckenId muss einzigartig sein
    __table_args__ = (db.UniqueConstraint('streckeId', 'reihenfolge', name='_strecke_reihenfolge_uc'),)




#############################################################
#################    Strecke     ############################
#############################################################

#Strecke-Modell
class Strecke(db.Model):
    __tablename__ = 'strecken' #Tabellenname in der DB

    streckenId: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True) #PK
    #Name der Strecke:einzigartiger String mit max. 100 Zeichen
    name: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False, unique=True)

    #Relationship
    reihenfolge: so.Mapped[List['Reihenfolge']] = so.relationship(
        'Reihenfolge', # Zielmodell der Beziehung
        order_by='Reihenfolge.reihenfolge', # Sortiert nach der reihenfolge-Spalte
        cascade='all, delete-orphan' # Löscht alle Reihenfolge-Einträge wenn Strecke gelöscht wird
    )

    # Property: gibt Liste der Abschnitte in der richtigen Reihenfolge zurück
    @property
    def abschnitte_in_reihenfolge(self):
        return [verbindung.abschnitt for verbindung in self.reihenfolge]

    # Property: ermittelt Start- und Endbahnhof der gesamten Strecke
    @property
    def start_end_bahnhoefe(self):
        abschnitte = self.abschnitte_in_reihenfolge # Holt die Liste der Abschnitte in Reihenfolge
        #wenn keine Abschnitte vorhanden sind -> gib None zurück
        if not abschnitte:
            return None, None

        start_bhf = abschnitte[0].startBahnhof #Start-Bahnhof der Strecke = StartBahnhof des ersten Abschnitts
        end_bhf = abschnitte[-1].endBahnhof #End-Bahnhof der Strecke = EndBahnhof des letzten Abschnitts

        return start_bhf, end_bhf # Gibt Tuple mit Start- und Endbahnhof zurück