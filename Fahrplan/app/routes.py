from app import app, db
from app.forms import (
    LoginForm,
    EmptyForm,
    MitarbeiterForm,
    FahrtCreateForm,
    FahrtEditForm,
    MitarbeiterEditForm
)

from flask import render_template, flash, redirect, url_for, request, abort
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import (
    User,
    Mitarbeiter,
    Role,
    Fahrtdurchfuehrung,
    Halteplan,
    FahrtdurchfuehrungStatus,
    Dienstzuweisung
)
from urllib.parse import urlsplit
from datetime import datetime, timezone
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapper

@app.route('/')
@app.route('/index')
@login_required
def index():
    # Admin-Dashboard
    if current_user.is_admin:
        return render_template('admin_index.html', title='Admin Dashboard')

    # Mitarbeiter-Dashboard
    if current_user.mitarbeiter:
        return render_template('mitarbeiter_index.html', title='Mein Dienstplan')




@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()

    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))

        login_user(user, remember=form.remember_me.data)

        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')

        return redirect(next_page)

    return render_template('login.html', title='Sign In', form=form)
    
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))
    

@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))

    
    
@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
        

@app.route('/mitarbeiter')
@login_required
@admin_required
def mitarbeiter_list():
    mitarbeiter = Mitarbeiter.query.order_by(Mitarbeiter.name).all()
    return render_template(
        'mitarbeiter_list.html',
        title='Mitarbeiter',
        mitarbeiter=mitarbeiter
    )


@app.route('/mitarbeiter/new', methods=['GET', 'POST'])
@login_required
@admin_required
def mitarbeiter_new():
    form = MitarbeiterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, role=Role.MITARBEITER)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # user.id verfügbar

        # 2) Mitarbeiter-Datensatz
        m = Mitarbeiter(name=form.name.data, user_id=user.id)
        db.session.add(m)
        db.session.commit()

        flash('Mitarbeiter und Benutzerkonto wurden angelegt.')
        return redirect(url_for('mitarbeiter_list'))

    return render_template(
        'mitarbeiter_form.html',
        title='Neuer Mitarbeiter',
        form=form
    )
@app.route('/mitarbeiter/<int:mitarbeiter_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def mitarbeiter_edit(mitarbeiter_id):
    mitarbeiter = Mitarbeiter.query.get_or_404(mitarbeiter_id)

    form = MitarbeiterEditForm(original_username=mitarbeiter.user.username)

    if request.method == "GET":
        # Bestehende Werte ins Formular laden
        form.name.data = mitarbeiter.name
        form.username.data = mitarbeiter.user.username

    if form.validate_on_submit():
        # Name & Benutzername aktualisieren
        mitarbeiter.name = form.name.data
        mitarbeiter.user.username = form.username.data

        # Passwort nur ändern, wenn etwas eingegeben wurde
        if form.password.data:
            mitarbeiter.user.set_password(form.password.data)

        db.session.commit()
        flash("Mitarbeiter wurde aktualisiert.", "success")
        return redirect(url_for("mitarbeiter_list"))

    return render_template(
        "mitarbeiter_edit.html",
        title="Mitarbeiter bearbeiten",
        mitarbeiter=mitarbeiter,
        form=form,
    )


@app.route('/mitarbeiter/<int:mitarbeiter_id>/delete', methods=['GET', 'POST'])
@login_required
@admin_required
def mitarbeiter_delete(mitarbeiter_id):
    mitarbeiter = Mitarbeiter.query.get_or_404(mitarbeiter_id)

    if request.method == "POST":
        # Zugehörigen User mitlöschen (1:1 Beziehung)
        user = mitarbeiter.user

        db.session.delete(mitarbeiter)
        if user:
            db.session.delete(user)

        db.session.commit()
        flash("Mitarbeiter wurde gelöscht.", "success")
        return redirect(url_for('mitarbeiter_list'))

    return render_template(
        'mitarbeiter_delete.html',
        title='Mitarbeiter löschen',
        mitarbeiter=mitarbeiter
    )





@app.route("/fahrten")
@login_required
@admin_required
def fahrten_list():
    fahrten = Fahrtdurchfuehrung.query.all()

    mitarbeiter_counts = {
        f.fahrt_id: len(f.dienstzuweisungen)
        for f in fahrten
    }

    return render_template(
        "fahrten_list.html",
        fahrten=fahrten,
        mitarbeiter_counts=mitarbeiter_counts,
        title="Fahrtdurchführungen"
    )




@app.route("/fahrten/new", methods=["GET", "POST"])
@login_required
@admin_required
def fahrten_new():
    form = FahrtCreateForm()

    # Haltepläne für Dropdown
    form.halteplan_id.choices = [
        (hp.halteplan_id, hp.bezeichnung)
        for hp in Halteplan.query.order_by(Halteplan.bezeichnung).all()
    ]

    # Alle Mitarbeiter laden (für WTForms-Validation UND für die Anzeige im Template)
    alle_mitarbeiter = Mitarbeiter.query.order_by(Mitarbeiter.name).all()

    # Choices für das WTForms-Feld (damit validate_on_submit sauber funktioniert)
    form.mitarbeiter_ids.choices = [
        (m.id, m.name) for m in alle_mitarbeiter
    ]

    if form.validate_on_submit():
        # Neue Fahrtdurchführung anlegen
        f = Fahrtdurchfuehrung(
            halteplan_id=form.halteplan_id.data,
            zug_id=0,  # wird später gepflegt
            status=FahrtdurchfuehrungStatus.PLANMAESSIG,
            verspaetung_min=0,
        )
        db.session.add(f)
        db.session.flush()  # f.fahrt_id now set

        # Save dienstzuweisung
        for mit_id in form.mitarbeiter_ids.data:
            dz = Dienstzuweisung(
                fahrt_id=f.fahrt_id,
                mitarbeiter_id=mit_id,
            )
            db.session.add(dz)

        db.session.commit()

        flash("Fahrtdurchführung inkl. Personal erfolgreich angelegt.", "success")
        return redirect(url_for("fahrten_list"))


    return render_template(
        "fahrten_new.html",
        title="Neue Fahrtdurchführung",
        form=form,
        mitarbeiter_liste=alle_mitarbeiter,  # für die Checkbox-Liste im Template
    )


@app.route("/fahrten/<int:fahrt_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def fahrt_edit(fahrt_id):
    fahrt = Fahrtdurchfuehrung.query.get_or_404(fahrt_id)
    form = FahrtEditForm()

    #mitarbeiter for checkbox loading
    alle_mitarbeiter = db.session.scalars(
        sa.select(Mitarbeiter).order_by(Mitarbeiter.name)
    ).all()

    # load dienstzuwißungen
    bestehende_zuweisungen = db.session.scalars(
        sa.select(Dienstzuweisung).where(Dienstzuweisung.fahrt_id == fahrt_id)
    ).all()
    bestehende_ids = {dz.mitarbeiter_id for dz in bestehende_zuweisungen}

    # formular mit bestehenden Werten vorbelegen
    if request.method == "GET":
        form.status.data = fahrt.status.name
        form.verspaetung_min.data = fahrt.verspaetung_min or 0

    # POST: Status / Verspätung + Mitarbeiter speichern
    if form.validate_on_submit():
        #  Status und Verspätung
        fahrt.status = FahrtdurchfuehrungStatus[form.status.data]

        if form.status.data == "VERSPAETET":
            fahrt.verspaetung_min = form.verspaetung_min.data
        else:
            fahrt.verspaetung_min = 0

        #  Mitarbeiter-Zuweisungen
        id_strings = request.form.getlist("mitarbeiter_ids")
        neue_ids = {int(x) for x in id_strings}

        # deleting disselectet Mitarbeiter
        for dz in bestehende_zuweisungen:
            if dz.mitarbeiter_id not in neue_ids:
                db.session.delete(dz)

        # 2) saveing newly selectet mitarbeiter
        for mid in neue_ids:
            if mid not in bestehende_ids:
                db.session.add(
                    Dienstzuweisung(fahrt_id=fahrt_id, mitarbeiter_id=mid)
                )

        db.session.commit()
        flash("Fahrtdurchführung und Personalzuweisungen wurden gespeichert.", "success")
        return redirect(url_for("fahrten_list"))

    #Checkboxen:
    zugewiesene_ids = bestehende_ids

    return render_template(
        "fahrt_edit.html",
        title=f"Fahrt {fahrt.fahrt_id} bearbeiten",
        fahrt=fahrt,
        form=form,
        mitarbeiter_liste=alle_mitarbeiter,
        zugewiesene_ids=zugewiesene_ids,
    )


@app.route("/fahrten/<int:fahrt_id>/delete", methods=["GET", "POST"])
@admin_required
def fahrt_delete(fahrt_id):
    fahrt = Fahrtdurchfuehrung.query.get_or_404(fahrt_id)

    if request.method == "POST":
        db.session.delete(fahrt)
        db.session.commit()
        flash("Fahrtdurchführung erfolgreich gelöscht.")
        return redirect(url_for("fahrten_list"))

    return render_template(
        "fahrt_delete.html",
        title="Fahrtdurchführung löschen",
        fahrt=fahrt
    )





@app.route('/fahrten/<int:fahrt_id>/mitarbeiter', methods=['GET', 'POST'])
@login_required
def fahrt_mitarbeiter(fahrt_id):
    # admin only:
    if not current_user.is_admin:
        abort(403)

    # get fahrtd.
    fahrt = db.session.get(Fahrtdurchfuehrung, fahrt_id)
    if fahrt is None:
        abort(404)


    form = EmptyForm()

    # get Mitarbeiter
    alle_mitarbeiter = db.session.scalars(
        sa.select(Mitarbeiter).order_by(Mitarbeiter.name)
    ).all()

    # get Dienste
    bestehende_zuweisungen = db.session.scalars(
        sa.select(Dienstzuweisung).where(Dienstzuweisung.fahrt_id == fahrt_id)
    ).all()
    bestehende_ids = {dz.mitarbeiter_id for dz in bestehende_zuweisungen}

    # post zuweißung changes
    if form.validate_on_submit():
        # Liste der ausgewählten MA
        id_strings = request.form.getlist("mitarbeiter_ids")
        neue_ids = {int(x) for x in id_strings}

        # 1) jetzt nichtselectierte löschen
        for dz in bestehende_zuweisungen:
            if dz.mitarbeiter_id not in neue_ids:
                db.session.delete(dz)

        # 2) neue welche vorher da waren nicht hinzufügen
        for mid in neue_ids:
            if mid not in bestehende_ids:
                neue_zuweisung = Dienstzuweisung(
                    fahrt_id=fahrt_id,
                    mitarbeiter_id=mid,
                )
                db.session.add(neue_zuweisung)

        db.session.commit()
        flash("Personalzuweisungen wurden gespeichert.")
        return redirect(url_for("fahrten_list"))

    # GET: Seite anzeigen
    zugewiesene_ids = bestehende_ids

    return render_template(
        "fahrt_mitarbeiter.html",
        title=f"Personal für Fahrt {fahrt_id}",
        fahrt=fahrt,
        mitarbeiter_liste=alle_mitarbeiter,
        zugewiesene_ids=zugewiesene_ids,
        form=form,
    )

@app.route("/meine_fahrten")
@login_required
def meine_fahrten():
    # Nur sinnvoll, wenn der User ein Mitarbeiter-Objekt hat
    if not current_user.mitarbeiter:
        flash("Für dieses Benutzerkonto ist kein Mitarbeiter hinterlegt.", "warning")
        return redirect(url_for("index"))

    ma = current_user.mitarbeiter

    # Alle Fahrten, denen dieser Mitarbeiter zugewiesen ist
    fahrten = (
        db.session.query(Fahrtdurchfuehrung)
        .join(Dienstzuweisung, Dienstzuweisung.fahrt_id == Fahrtdurchfuehrung.fahrt_id)
        .filter(Dienstzuweisung.mitarbeiter_id == ma.id)
        .order_by(Fahrtdurchfuehrung.fahrt_id)
        .all()
    )

    return render_template(
        "meine_fahrten.html",
        title="Meine Fahrten",
        fahrten=fahrten,
        mitarbeiter=ma,
    )

@app.route("/fahrten/alle")
@login_required
def fahrten_alle():
    # Nur sinnvoll für Mitarbeiter; Admin ohne Mitarbeiter-Objekt bekommt 403
    if not current_user.mitarbeiter:
        abort(403)

    mitarbeiter = current_user.mitarbeiter

    # Alle Fahrten laden
    fahrten = Fahrtdurchfuehrung.query.all()

    # Alle Zuweisungen dieses Mitarbeiters holen
    zugewiesene_fahrten_ids = {
        dz.fahrt_id
        for dz in Dienstzuweisung.query.filter_by(mitarbeiter_id=mitarbeiter.id).all()
    }

    return render_template(
        "fahrten_alle.html",
        title="Alle Fahrten",
        fahrten=fahrten,
        mitarbeiter=mitarbeiter,
        zugewiesene_fahrten_ids=zugewiesene_fahrten_ids,
    )




@app.route("/api/mitarbeiter", methods=["GET"])
def api_mitarbeiter():
    mitarbeiter = Mitarbeiter.query.all()

    data = []
    for m in mitarbeiter:
        data.append({
            "id": m.id,
            "name": m.name,
            "username": m.user.username
        })

    return {"mitarbeiter": data}


@app.route("/api/fahrten", methods=["GET"])
def api_fahrten():
    fahrten = Fahrtdurchfuehrung.query.all()

    data = []
    for f in fahrten:
        data.append({
            "fahrt_id": f.fahrt_id,
            "halteplan": f.halteplan.bezeichnung,
            "zug_id": f.zug_id,
            "status": f.status.value,
            "verspaetung": f.verspaetung_min,
            "mitarbeiter": [dz.mitarbeiter_id for dz in f.dienstzuweisungen]
        })

    return {"fahrten": data}


@app.route("/api/dienstzuweisung", methods=["GET"])
def api_dienstzuweisung():
    dienstzuweisungen = Dienstzuweisung.query.all()

    data = []
    for d in dienstzuweisungen:
        data.append({
            "dienst_id": d.dienst_id,
            "fahrt_id": d.fahrt_id,
            "mitarbeiter_id": d.mitarbeiter_id
        })

    return {"Dienstzuweisungen": data}