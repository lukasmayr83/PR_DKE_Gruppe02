from flask import render_template, flash, redirect, url_for, request
from urllib.parse import urlsplit
from app import app,db
from app.forms import LoginForm, PersonenwagenForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Role, Personenwagen
from sqlalchemy import or_

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == Role.ADMIN:
            return redirect(url_for('dashboard_admin'))
        else:
            return redirect(url_for('dashboard_mitarbeiter'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Ungültiger username oder passwort')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        if user.role == Role.ADMIN:
            return redirect(url_for('dashboard_admin'))
        else:
            return redirect(url_for('dashboard_mitarbeiter'))

    return render_template('login.html', title='Anmeldung', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard_admin')
@login_required
def dashboard_admin():
    return render_template('dashboard.html', title='Admin Dashboard')

@app.route('/dashboard_mitarbeiter')
@login_required
def dashboard_mitarbeiter():
    return render_template('dashboard_mitarbeiter.html', title='Mitarbeiter Dashboard')

@app.route('/uebers_personenwagen')
@login_required
def uebers_personenwagen():
    suchbegriff = request.args.get('q', '').strip()

    # get('q', '')  - falls "q" vorhanden → Wert nehmen - sonst leerer String -
    # strip() entfernt Leerzeichen am Anfang/Ende.
    query = db.select(Personenwagen).order_by(Personenwagen.wagenid)

    if suchbegriff:
        query = query.where(
            or_(
                Personenwagen.kapazitaet.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.maxgewicht.cast(sa.String).like(f"%{suchbegriff}%"),
                Personenwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%")
            )
        )

    personenwagen_liste = db.session.execute(query).scalars().all()
    return render_template('uebers_personenwagen.html',title='Personenwagen-Übersicht',personenwagen_liste=personenwagen_liste)

@app.route('/hinzufuegen_personenwagen', methods=['GET', 'POST'])
@login_required
def hinzufuegen_personenwagen():
    form = PersonenwagenForm()

    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_personenwagen'))

    if form.validate_on_submit():
        neuer_wagen = Personenwagen(
            kapazitaet=form.kapazitaet.data,
            maxgewicht=form.maxgewicht.data,
            spurweite=form.spurweite.data,
            istfrei=None
        )
        db.session.add(neuer_wagen)
        db.session.commit()
        flash("Personenwagen erfolgreich hinzugefügt.")
        return redirect(url_for('dashboard_admin'))

    return render_template('hinzufuegen_personenwagen.html',title='Neuen Personenwagen hinzufügen',form=form)


@app.route('/uebers_triebwagen')
@login_required
def uebers_triebwagen():
    return render_template('uebers_triebwagen.html', title='Triebwagen-Übersicht')

@app.route('/uebers_zuege')
@login_required
def uebers_zuege():
    return render_template('uebers_zuege.html', title='Züge-Übersicht')

@app.route('/uebers_wartungen')
@login_required
def uebers_wartungen():
    return render_template('uebers_zuege.html', title='Wartungen-Übersicht')

@app.route('/uebers_mitarbeiter')
@login_required
def uebers_mitarbeiter():
    return render_template('uebers_mitarbeiter', title='Mitarbeiter-Übersicht')