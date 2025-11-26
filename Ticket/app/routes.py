from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from urllib.parse import urlparse
from app import db
from app.models import User, Aktion
from app.forms import LoginForm, AktionForm, RegisterForm


bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    return redirect(url_for("main.aktionen_uebersicht"))


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

        # Neuen User anlegen
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


@bp.route("/aktionen/<int:aktion_id>/delete", methods=["POST"])
@login_required
def aktion_delete(aktion_id):
    aktion = Aktion.query.get_or_404(aktion_id)
    db.session.delete(aktion)
    db.session.commit()
    flash("Aktion gelöscht.")
    return redirect(url_for("main.aktionen_uebersicht"))

@bp.route("/verbindungssuche")
@login_required
def verbindungssuche():
    return render_template("verbindungssuche.html", title="Verbindungssuche")


@bp.route("/meine-tickets")
@login_required
def meine_tickets():
    return render_template("meine_tickets.html", title="Meine Tickets")

