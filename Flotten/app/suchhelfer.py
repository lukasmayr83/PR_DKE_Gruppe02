from app import db
from app.models import Mitarbeiter, Personenwagen, Triebwagen, Zuege
import sqlalchemy as sa
from sqlalchemy import or_

def search_mitarbeiter(request):
    # strip() entfernt Leerzeichen am Anfang/Ende.
    suchbegriff = request.args.get('q', '').strip()
    query = db.select(Mitarbeiter).order_by(Mitarbeiter.svnr)
    if suchbegriff:
        query = query.where(
            or_(
                Mitarbeiter.vorname.like(f"%{suchbegriff}%"),
                Mitarbeiter.nachname.like(f"%{suchbegriff}%"),
                Mitarbeiter.svnr.cast(sa.String).like(f"%{suchbegriff}%")
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
                Personenwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%")
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
                Triebwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%")
            )
        )
    return db.session.execute(query).scalars().all()

def search_zuege(request):
    suchbegriff = request.args.get('q', '').strip()
    query = db.select(Zuege).order_by(Zuege.zugid)
    if suchbegriff:
        query = query.where(
            Zuege.bezeichnung.like(f"%{suchbegriff}%")
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
