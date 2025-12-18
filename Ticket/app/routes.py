from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from urllib.parse import urlparse
from datetime import datetime

from app import db
from app.models import User, Aktion, Ticket
from app.forms import LoginForm, AktionForm, RegisterForm, VerbindungssucheForm

import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from flask import current_app
from sqlalchemy.exc import IntegrityError


bp = Blueprint("main", __name__)

################################################################

# DUMMY DATEN ZUR VERBINDUNGSUCHE - TO BE DONE - FUER DEMO
DUMMY_VERBINDUNGEN = [
    {
        "id": 1,
        "start_halt": "Linz Hbf",
        "ziel_halt": "Innsbruck Hbf",
        "abfahrt_basis": datetime(2025, 11, 26, 9, 0),
        "ankunft_basis": datetime(2025, 11, 26, 12, 30),
        "anzahl_umstiege": 0,
        "grundpreis": 49.90,
        "halteplan_id": 1,
    },
    {
        "id": 2,
        "start_halt": "Linz Hbf",
        "ziel_halt": "Innsbruck Hbf",
        "abfahrt_basis": datetime(2025, 11, 26, 10, 15),
        "ankunft_basis": datetime(2025, 11, 26, 13, 45),
        "anzahl_umstiege": 1,
        "grundpreis": 39.90,
        "halteplan_id": 1,
    },
]

##############################################
# TO BE DONE - gibt Bahnhoefe von Strecken API zurueck, anti crash
def lade_bahnhoefe():
    base = current_app.config.get("STRECKEN_API_BASE", "").rstrip("/")
    if not base:
        return []

    url = f"{base}/bahnhoefe"

    # HTTP request an Strecke
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=3) as resp:
            data = json.load(resp)
    except Exception:
        return []

    return [
        b["name"].strip()
        for b in data.get("bahnhoefe", [])
        if "name" in b and b["name"]
    ]
################################################

@bp.route("/")
@login_required
def index():
    # Admin -> Aktionsübersicht, Kunde -> Verbindungssuche
    if current_user.username == "admin":
        return redirect(url_for("main.aktionen_uebersicht"))
    else:
        return redirect(url_for("main.verbindungssuche"))


# Login

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.aktionen_uebersicht"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash("Ungültiger Benutzername oder Passwort")
            return redirect(url_for("main.login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")

        if not next_page or urlparse(next_page).netloc != "":
            if user.username == "admin":
                next_page = url_for("main.aktionen_uebersicht")
            else:
                next_page = url_for("main.verbindungssuche")

        return redirect(next_page)

    return render_template("login.html", title="Sign in", form=form)

# Register

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.aktionen_uebersicht"))

    form = RegisterForm()

    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Username bereits vergeben.")
            return redirect(url_for("main.register"))

        if User.query.filter_by(email=form.email.data).first():
            flash("E-Mail bereits registriert.")
            return redirect(url_for("main.register"))

        # neuen User anlegen
        user = User(
            username=form.username.data,
            email=form.email.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Registrierung erfolgreich. Bitte jetzt einloggen.")
        return redirect(url_for("main.login"))

    return render_template("register.html", title="Registrierung", form=form)

# Logout

@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.login"))


# Aktionsübersicht

@bp.route("/aktionen")
@login_required
def aktionen_uebersicht():
    aktionen = Aktion.query.order_by(Aktion.id.asc()).all()
    return render_template("aktionen_uebersicht.html", title="Aktionsübersicht", aktionen=aktionen)


# Globale-Aktion anlegen

@bp.route("/aktionen/global/new", methods=["GET", "POST"])
@login_required
def aktion_global_new():
    form = AktionForm()
    form.typ.data = "global"
    form.halteplanId.data = ""

    if request.method == "POST":
        if form.name.data and form.startZeit.data and form.endeZeit.data:
            aktion = Aktion(
                name=form.name.data,
                beschreibung=form.beschreibung.data,
                startZeit=form.startZeit.data,
                endeZeit=form.endeZeit.data,
                aktiv=form.aktiv.data,
                rabattWert=form.rabattWert.data or 0.0,
                typ="global",
                halteplanId=None,
            )
            db.session.add(aktion)
            db.session.commit()
            flash("Globale Aktion angelegt.")
            return redirect(url_for("main.aktionen_uebersicht"))
        else:
            flash("Bitte alle Pflichtfelder ausfüllen.")

    return render_template("aktion_global_new.html", title="Globale-Aktion anlegen", form=form)

# Fahrplan-Aktion anlegen

@bp.route("/aktionen/fahrplan/new", methods=["GET", "POST"])
@login_required
def aktion_fahrplan_new():
    form = AktionForm()
    form.typ.data = "halteplan"

    if request.method == "POST":
        if form.name.data and form.startZeit.data and form.endeZeit.data:
            halteplan_id = int(form.halteplanId.data) if form.halteplanId.data else None
            aktion = Aktion(
                name=form.name.data,
                beschreibung=form.beschreibung.data,
                startZeit=form.startZeit.data,
                endeZeit=form.endeZeit.data,
                aktiv=form.aktiv.data,
                rabattWert=form.rabattWert.data or 0.0,
                typ="halteplan",
                halteplanId=halteplan_id,
            )
            db.session.add(aktion)
            db.session.commit()
            flash("Fahrplan-Aktion angelegt.")
            return redirect(url_for("main.aktionen_uebersicht"))
        else:
            flash("Bitte alle Pflichtfelder ausfüllen.")

    return render_template("aktion_fahrplan_new.html", title="Fahrplan-Aktion anlegen", form=form)

# Bearbeiten, Löschen

@bp.route("/aktionen/<int:aktion_id>/edit", methods=["GET", "POST"])
@login_required
def aktion_edit(aktion_id):
    aktion = Aktion.query.get_or_404(aktion_id)

    # Formular mit bestehenden Werten vorbelegen
    form = AktionForm(
        name=aktion.name,
        beschreibung=aktion.beschreibung,
        startZeit=aktion.startZeit,
        endeZeit=aktion.endeZeit,
        aktiv=aktion.aktiv,
        rabattWert=aktion.rabattWert,
        typ=aktion.typ,
        halteplanId=str(aktion.halteplanId) if aktion.halteplanId else "",
    )

    if form.validate_on_submit():
        aktion.name = form.name.data
        aktion.beschreibung = form.beschreibung.data
        aktion.startZeit = form.startZeit.data
        aktion.endeZeit = form.endeZeit.data
        aktion.aktiv = form.aktiv.data
        aktion.rabattWert = form.rabattWert.data or 0.0

        # Typ NICHT änderbar-bleibt wie er war
        if aktion.typ == "global":
            aktion.typ = "global"
            aktion.halteplanId = None
        else:
            aktion.typ = "halteplan"
            aktion.halteplanId = int(form.halteplanId.data) if form.halteplanId.data else None

        db.session.commit()
        flash("Aktion aktualisiert.")
        return redirect(url_for("main.aktionen_uebersicht"))

    return render_template("aktion_edit.html", title="Aktion bearbeiten", form=form, aktion=aktion)

# Aktion löschen

@bp.route("/aktionen/<int:aktion_id>/delete", methods=["POST"])
@login_required
def aktion_delete(aktion_id):
    aktion = Aktion.query.get_or_404(aktion_id)

    # Tickets die  Aktion verwenden entkoppeln
    Ticket.query.filter(Ticket.aktion_id == aktion.id).update({Ticket.aktion_id: None})

    # Aktion löschen
    try:
        db.session.delete(aktion)
        db.session.commit()
        flash("Aktion gelöscht")
    except IntegrityError:
        db.session.rollback()
        flash("Aktion konnte nicht gelöscht werden (FK-Problem).")

    return redirect(url_for("main.aktionen_uebersicht"))

# finde passende aktive Aktion

def ermittle_aktion(verbindungs_datum: datetime, halteplan_id: int):
    aktive = Aktion.query.filter_by(aktiv=True).all()
    for a in aktive:
        if a.startZeit.date() <= verbindungs_datum.date() <= a.endeZeit.date():
            if a.typ == "global":
                return a
            if a.typ == "halteplan" and a.halteplanId == halteplan_id:
                return a
    return None

#  Verbindungssuche

@bp.route("/verbindungssuche", methods=["GET", "POST"])
@login_required
def verbindungssuche():
    form = VerbindungssucheForm()
    verbindungen = []

    if form.validate_on_submit():
        start = form.startbahnhof.data.strip().lower()
        ziel = form.zielbahnhof.data.strip().lower()
        # Bahnhoefe von Strecken Schnittstelle laden (wenn Liste nicht leer)
        bahnhoefe = lade_bahnhoefe()
        if bahnhoefe:
            set_bh = set(b.lower() for b in bahnhoefe)
            if start not in set_bh or ziel not in set_bh:
                flash("Start- oder Zielbahnhof existiert nicht ")
                return render_template(
                    "verbindungssuche.html",
                    title="Verbindungssuche",
                    form=form,
                    verbindungen=[],
                )

        datum = form.datum.data
        sitzplatz = form.sitzplatz.data

        for v in DUMMY_VERBINDUNGEN:
            # passt Verbindung zur Suche
            if start in v["start_halt"].lower() and ziel in v["ziel_halt"].lower():
                item = dict(v)   # Kopie anlegen

                # DEMO Datum aus dem Formular +Zeit aus dem "Fahrplan"
                item["abfahrt"] = datetime.combine(datum, v["abfahrt_basis"].time())
                item["ankunft"] = datetime.combine(datum, v["ankunft_basis"].time())

                # Grundpreis (+evtl Sitzplatzaufschlag)
                preis = v["grundpreis"] + (5.0 if sitzplatz else 0.0)

                aktion = ermittle_aktion(item["abfahrt"], v["halteplan_id"])
                if aktion:
                    preis = round(preis * (1 - aktion.rabattWert / 100.0), 2)
                    item["aktion_name"] = aktion.name
                    item["aktion_rabatt"] = aktion.rabattWert
                    item["aktion_id"] = aktion.id
                else:
                    item["aktion_name"] = None
                    item["aktion_rabatt"] = 0
                    item["aktion_id"] = None

                item["preis"] = preis
                item["abfahrt_display"] = item["abfahrt"].strftime("%d.%m.%Y %H:%M")
                item["ankunft_display"] = item["ankunft"].strftime("%d.%m.%Y %H:%M")
                item["abfahrt_iso"] = item["abfahrt"].isoformat()
                item["ankunft_iso"] = item["ankunft"].isoformat()
                item["sitzplatz"] = sitzplatz

                verbindungen.append(item)

        if not verbindungen:
            flash("Keine passende Verbindung gefunden.")

    return render_template(
        "verbindungssuche.html",
        title="Verbindungssuche",
        form=form,
        verbindungen=verbindungen,
    )

# Ticket buchen

@bp.route("/tickets/buchen/<int:fahrt_id>", methods=["POST"])
@login_required
def ticket_buchen(fahrt_id):
    # Daten aus dem Formular
    start_halt = request.form.get("start_halt")
    ziel_halt = request.form.get("ziel_halt")
    abfahrt_str = request.form.get("abfahrt")
    ankunft_str = request.form.get("ankunft")
    umstiege = int(request.form.get("umstiege", 0))
    halteplan_id = request.form.get("halteplan_id")
    preis = float(request.form.get("preis"))
    sitzplatz = request.form.get("sitzplatz") == "1"
    aktion_id = request.form.get("aktion_id")

    # ISO Zeitstring in date time Obj
    try:
        abfahrt = datetime.fromisoformat(abfahrt_str)
        ankunft = datetime.fromisoformat(ankunft_str)
    except (TypeError, ValueError):
        flash("Verbindungsdaten ungültig.")
        return redirect(url_for("main.verbindungssuche"))

#   Ticket für User anlegen
    ticket = Ticket(
        user_id=current_user.id,
        status="aktiv",
        start_halt=start_halt,
        ziel_halt=ziel_halt,
        anzahl_umstiege=umstiege,

        abfahrt=abfahrt,
        ankunft=ankunft,

        fahrt_id=fahrt_id,
        halteplan_id=int(halteplan_id) if halteplan_id else None,
        gesamtPreis=preis,
        sitzplatzReservierung=sitzplatz,
        aktion_id=int(aktion_id) if aktion_id else None,
    )

    db.session.add(ticket)
    db.session.commit()
    flash("Ticket erfolgreich gebucht.")
    return redirect(url_for("main.meine_tickets"))


#  zeige nur MEINE Tickets (Filter)
@bp.route("/meine-tickets")
@login_required
def meine_tickets():
    tickets = Ticket.query.filter_by(user_id=current_user.id).order_by(Ticket.erstelltAm.desc()).all()
    return render_template("meine_tickets.html", title="Meine Tickets", tickets=tickets)

#  Storno über Status
@bp.route("/tickets/<int:ticket_id>/storno", methods=["POST"])
@login_required
def ticket_storno(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=current_user.id).first_or_404()

    if ticket.status == "storniert":
        flash("Ticket ist bereits storniert.")
    else:
        ticket.status = "storniert"
        db.session.commit()
        flash("Ticket wurde storniert.")

    return redirect(url_for("main.meine_tickets"))
