from app import db
from app.models import Mitarbeiter, User, Personenwagen, Triebwagen, Zuege, Wartungszeitraum, Wartung
import sqlalchemy as sa
from sqlalchemy import or_
from datetime import datetime

def search_mitarbeiter(request):
    # strip() entfernt Leerzeichen am Anfang/Ende.
    suchbegriff = request.args.get('q', '').strip()
    query = db.select(Mitarbeiter).join(User).order_by(Mitarbeiter.svnr)
    if suchbegriff:
        query = query.where(
            or_(
                Mitarbeiter.vorname.like(f"%{suchbegriff}%"),
                Mitarbeiter.nachname.like(f"%{suchbegriff}%"),
                Mitarbeiter.svnr.cast(sa.String).like(f"%{suchbegriff}%"),
                User.username.cast(sa.String).like(f"%{suchbegriff}%")
            )
        )
    return db.session.execute(query).scalars().all()

def search_personenwagen(request):
    suchbegriff = request.args.get('q', '').strip()
    query = db.select(Personenwagen).order_by(Personenwagen.wagenid)
    if suchbegriff:
        query = query.where(
            or_(
                Personenwagen.kapazitaet.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.maxgewicht.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.wagenid.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.istfrei.cast(sa.String).like(f"%{suchbegriff}%")
            )
        )
    return db.session.execute(query).scalars().all()

def search_triebwagen(request):
    suchbegriff = request.args.get('q', '').strip()
    query = db.select(Triebwagen).order_by(Triebwagen.wagenid)
    if suchbegriff:
        query = query.where(
            or_(
                Triebwagen.maxzugkraft.cast(sa.String).like(f"%{suchbegriff}%"),
                Triebwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%"),
                Triebwagen.wagenid.cast(sa.String).like(f"%{suchbegriff}%"),
                Triebwagen.istfrei.cast(sa.String).like(f"%{suchbegriff}%")
            )
        )
    return db.session.execute(query).scalars().all()

def search_zuege(request):
    suchbegriff = request.args.get('q', '').strip()
    query = db.select(Zuege).order_by(Zuege.zugid)
    if suchbegriff:
        query = query.where(
            or_(
            Zuege.bezeichnung.like(f"%{suchbegriff}%"),
            Zuege.zugid.cast(sa.String).like(f"%{suchbegriff}%")
        )
    )
    return db.session.execute(query).scalars().all()

def search_freie_triebwagen(request):
    suchbegriff = request.args.get("search_tw", "").strip()

    query = db.select(Triebwagen).where(Triebwagen.istfrei == None).order_by(Triebwagen.wagenid)

    if suchbegriff:
        query = query.where(
            or_(
                Triebwagen.wagenid.cast(sa.String).like(f"%{suchbegriff}%"),
                Triebwagen.maxzugkraft.cast(sa.String).like(f"%{suchbegriff}%"),
                Triebwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%"),
            )
        )
    return db.session.execute(query).scalars().all()

def search_freie_personenwagen(request):
    suchbegriff = request.args.get("search_pw", "").strip()
    query = db.select(Personenwagen).where(Personenwagen.istfrei == None).order_by(Personenwagen.wagenid)
    if suchbegriff:
        query = query.where(
            or_(
                Personenwagen.wagenid.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.maxgewicht.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.kapazitaet.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%"),
            )
        )
    return db.session.execute(query).scalars().all()


def search_triebwagen_for_zug_bearbeiten(request, zug_id):
    suchbegriff = request.args.get("search_tw", "").strip()
    query = db.select(Triebwagen).where(
        or_(
            Triebwagen.istfrei == None,
            Triebwagen.istfrei == zug_id
        )
    ).order_by(Triebwagen.wagenid)
    if suchbegriff:
        query = query.where(
            or_(
                Triebwagen.wagenid.cast(sa.String).like(f"%{suchbegriff}%"),
                Triebwagen.maxzugkraft.cast(sa.String).like(f"%{suchbegriff}%"),
                Triebwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%"),
            )
        )

    return db.session.execute(query).scalars().all()

def search_personenwagen_for_zug_bearbeiten(request, zug_id):
    suchbegriff = request.args.get("search_pw", "").strip()
    query = db.select(Personenwagen).where(
        or_(
            Personenwagen.istfrei == None,
            Personenwagen.istfrei == zug_id
        )
    ).order_by(Personenwagen.wagenid)

    if suchbegriff:
        query = query.where(
            or_(
                Personenwagen.wagenid.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.maxgewicht.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.kapazitaet.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%"),
            )
        )
    return db.session.execute(query).scalars().all()

def search_wartungen(request, nur_aktuelle=False, svnr=None):
    suchbegriff = request.args.get("q", "").strip()
    query = (db.select(Wartungszeitraum).join(Wartung, Wartung.wartungszeitid == Wartungszeitraum.wartungszeitid)
             .join(Mitarbeiter, Mitarbeiter.svnr == Wartung.svnr)
             .join(Zuege, Zuege.zugid == Wartung.zugid).distinct())

    if svnr:
        query = query.where(Wartung.svnr == svnr)

    if suchbegriff:
        query = query.where(
            or_(
                Wartungszeitraum.wartungszeitid.cast(sa.String).like(f"%{suchbegriff}%"),
                Wartungszeitraum.datum.cast(sa.String).like(f"%{suchbegriff}%"),
                Wartungszeitraum.dauer.cast(sa.String).like(f"%{suchbegriff}%"),
                Zuege.zugid.cast(sa.String).like(f"%{suchbegriff}%"),
                Mitarbeiter.nachname.cast(sa.String).like(f"%{suchbegriff}%"),
                Wartungszeitraum.von.cast(sa.String).like(f"%{suchbegriff}%"),
                Wartungszeitraum.bis.cast(sa.String).like(f"%{suchbegriff}%"),
            )
        )
    if nur_aktuelle:
        jetzt = datetime.now()
        query = query.where(Wartungszeitraum.bis>= jetzt)
    return db.session.execute(query).scalars().all()