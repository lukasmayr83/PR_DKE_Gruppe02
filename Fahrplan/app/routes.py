from app import app, db
from app.forms import (
    LoginForm,
    EmptyForm,
    MitarbeiterForm,
    FahrtCreateForm,
    FahrtEditForm,
    MitarbeiterEditForm,
    HalteplanCreateForm
)

from flask import render_template, flash, redirect, url_for, request, abort, jsonify
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import (
    User,
    Mitarbeiter,
    Role,
    Fahrtdurchfuehrung,
    Halteplan,
    FahrtdurchfuehrungStatus,
    Dienstzuweisung,
    Bahnhof,
    Strecke,
    Haltepunkt,
    HalteplanSegment,
    Abschnitt,
    StreckeAbschnitt
)
from urllib.parse import urlsplit
from datetime import datetime, timezone
from functools import wraps
from app.services.strecken_import import sync_from_strecken
from app.services.fahrt_refresh import refresh_fahrt_snapshot
from app.services.halteplan_pricing import compute_min_cost_map, compute_min_duration_map, to_json_keyed_map



def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapper



# Helper für Halteplan / Segment-Berechnung

def _ordered_abschnitte_for_strecke(strecke_id: int):
    return (
        db.session.query(StreckeAbschnitt.position, Abschnitt)
        .join(Abschnitt, Abschnitt.id == StreckeAbschnitt.abschnitt_id)
        .filter(StreckeAbschnitt.strecke_id == strecke_id)
        .order_by(StreckeAbschnitt.position.asc())
        .all()
    )


def _min_cost_between_bahnhoefe_on_strecke(
    strecke_id: int,
    start_bahnhof_id: int,
    end_bahnhof_id: int
) -> float:
    abschnitte = _ordered_abschnitte_for_strecke(strecke_id)

    started = False
    cost = 0.0

    for _, abschnitt in abschnitte:
        if not started:
            if abschnitt.start_bahnhof_id == start_bahnhof_id:
                started = True
            else:
                continue

        cost += float(abschnitt.nutzungsentgelt or 0.0)

        if abschnitt.end_bahnhof_id == end_bahnhof_id:
            return cost

    raise ValueError(
        "Haltepunkte sind nicht entlang der Strecke in Fahrtrichtung erreichbar."
    )


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

@app.route("/halteplaene", methods=["GET"])
@login_required
@admin_required
def halteplaene_list():
    halteplaene = Halteplan.query.order_by(Halteplan.halteplan_id.desc()).all()
    return render_template("halteplaene_list.html", title="Haltepläne", halteplaene=halteplaene)


@app.route("/halteplaene/new", methods=["GET", "POST"])
@login_required
@admin_required
def halteplan_new():
    # 1) Strecken laden
    strecken = Strecke.query.order_by(Strecke.name).all()
    if not strecken:
        flash("Keine Strecken vorhanden. Bitte zuerst Sync ausführen.", "warning")
        return redirect(url_for("halteplaene_list"))

    # 2) selected Strecke bestimmen (QueryParam oder erste Strecke)
    selected_strecke_id = request.args.get("strecke_id", type=int) or strecken[0].id

    # 3) Bahnhof-Reihenfolge aus der Strecke ableiten (über Abschnitte)
    #    -> wir nehmen Startbahnhof des 1. Abschnitts + jeweils Endbahnhof
    abschnitte_rows = db.session.execute(
        sa.select(
            StreckeAbschnitt.position,
            Abschnitt.start_bahnhof_id,
            Abschnitt.end_bahnhof_id,
        )
        .join(Abschnitt, Abschnitt.id == StreckeAbschnitt.abschnitt_id)
        .where(StreckeAbschnitt.strecke_id == selected_strecke_id)
        .order_by(StreckeAbschnitt.position)
    ).all()

    bahnhof_ids_in_order = []
    if abschnitte_rows:
        bahnhof_ids_in_order.append(int(abschnitte_rows[0].start_bahnhof_id))
        for r in abschnitte_rows:
            bahnhof_ids_in_order.append(int(r.end_bahnhof_id))

    # Unique (falls irgendwo doppelt, safety)
    seen = set()
    bahnhof_ids_in_order = [x for x in bahnhof_ids_in_order if not (x in seen or seen.add(x))]

    bahnhof_rows = Bahnhof.query.filter(Bahnhof.id.in_(bahnhof_ids_in_order)).all()
    bahnhof_by_id = {b.id: b for b in bahnhof_rows}
    bahnhof_rows = [bahnhof_by_id[i] for i in bahnhof_ids_in_order if i in bahnhof_by_id]

    # 4) Pricing/Duration Maps berechnen + JSON-friendly machen
    min_cost_map = to_json_keyed_map(compute_min_cost_map(selected_strecke_id))
    min_duration_map = to_json_keyed_map(compute_min_duration_map(selected_strecke_id))

    # ------------------------------------------------------------
    # POST: Halteplan + Haltepunkte + Segmente speichern
    # ------------------------------------------------------------
    if request.method == "POST":
        bezeichnung = request.form.get("bezeichnung", "").strip()
        strecke_id = request.form.get("strecke_id", type=int)
        halte_ids = request.form.getlist("halte_bahnhof_ids")  # Checkboxen
        halte_ids = [int(x) for x in halte_ids]

        if not bezeichnung or not strecke_id or len(halte_ids) < 2:
            flash("Bitte Bezeichnung wählen und mindestens 2 Haltepunkte auswählen.", "warning")
            return redirect(url_for("halteplan_new", strecke_id=selected_strecke_id))

        # 1) Halteplan anlegen
        hp = Halteplan(bezeichnung=bezeichnung, strecke_id=strecke_id)
        db.session.add(hp)
        db.session.flush()  # hp.halteplan_id verfügbar

        # 2) Haltepunkte anlegen (Position = Reihenfolge im Halteplan)
        #    haltedauer_min nur für Zwischenhalte (pos 2..n-1)
        halte_dauern = request.form.getlist("halte_dauer_min[]")
        halte_dauern_int: list[int] = []
        for x in halte_dauern:
            try:
                halte_dauern_int.append(int(x))
            except:
                halte_dauern_int.append(0)

        n = len(halte_ids)

        # Erwartung bei deinem UI: pro Segment wird Haltezeit für "to" erfasst,
        # aber NICHT beim letzten Segment => Zwischenhalte = n-2 Werte
        expected = max(0, n - 2)
        if len(halte_dauern_int) != expected:
            flash(f"Haltezeiten passen nicht (erwartet {expected}, bekommen {len(halte_dauern_int)}).", "warning")
            return redirect(url_for("halteplan_new", strecke_id=selected_strecke_id))

        haltepunkt_ids_in_order = []
        dwell_idx = 0

        for pos, bahnhof_id in enumerate(halte_ids, start=1):
            if pos == 1 or pos == n:
                haltedauer_min = 0
            else:
                haltedauer_min = halte_dauern_int[dwell_idx]
                dwell_idx += 1

            hp_halt = Haltepunkt(
                halteplan_id=hp.halteplan_id,
                bahnhof_id=bahnhof_id,
                position=pos,
                halte_dauer_min=haltedauer_min,
            )
            db.session.add(hp_halt)
            db.session.flush()
            haltepunkt_ids_in_order.append(hp_halt.id)

        # 3) Segmente aus POST übernehmen (Duration/BasePrice/MinCost)
        seg_min_costs = request.form.getlist("segment_min_cost[]")
        seg_durations = request.form.getlist("segment_duration_min[]")
        seg_base_prices = request.form.getlist("segment_base_price[]")

        # Erwartung: Anzahl Segmente = len(halte_ids)-1
        for pos in range(1, len(halte_ids)):
            try:
                min_cost = float(seg_min_costs[pos - 1])
            except:
                min_cost = 0.0
            try:
                dur = int(seg_durations[pos - 1])
            except:
                dur = 0
            try:
                base_price = float(seg_base_prices[pos - 1])
            except:
                base_price = min_cost

            seg = HalteplanSegment(
                halteplan_id=hp.halteplan_id,
                von_haltepunkt_id=haltepunkt_ids_in_order[pos - 1],
                nach_haltepunkt_id=haltepunkt_ids_in_order[pos],
                position=pos,
                min_cost=min_cost,
                duration_min=dur,
                base_price=base_price,
            )
            db.session.add(seg)

        db.session.commit()
        flash("Halteplan wurde angelegt.", "success")
        return redirect(url_for("halteplaene_list"))

    # ------------------------------------------------------------
    # GET: Template rendern
    # ------------------------------------------------------------
    return render_template(
        "halteplan_new.html",
        title="Neuer Halteplan",
        strecken=strecken,
        selected_strecke_id=selected_strecke_id,
        bahnhof_rows=bahnhof_rows,
        min_cost_map=min_cost_map,
        min_duration_map=min_duration_map,
    )

@app.route("/halteplaene/<int:halteplan_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def halteplan_edit(halteplan_id: int):
    hp = Halteplan.query.get_or_404(halteplan_id)

    # Strecke fix vom Halteplan (nicht änderbar)
    selected_strecke_id = hp.strecke_id
    strecken = Strecke.query.order_by(Strecke.name).all()

    # Bahnhof-Reihenfolge aus Strecke (für Anzeige links)
    abschnitte_rows = db.session.execute(
        sa.select(
            StreckeAbschnitt.position,
            Abschnitt.start_bahnhof_id,
            Abschnitt.end_bahnhof_id,
        )
        .join(Abschnitt, Abschnitt.id == StreckeAbschnitt.abschnitt_id)
        .where(StreckeAbschnitt.strecke_id == selected_strecke_id)
        .order_by(StreckeAbschnitt.position)
    ).all()

    bahnhof_ids_in_order = []
    if abschnitte_rows:
        bahnhof_ids_in_order.append(int(abschnitte_rows[0].start_bahnhof_id))
        for r in abschnitte_rows:
            bahnhof_ids_in_order.append(int(r.end_bahnhof_id))

    seen = set()
    bahnhof_ids_in_order = [x for x in bahnhof_ids_in_order if not (x in seen or seen.add(x))]

    bahnhof_rows = Bahnhof.query.filter(Bahnhof.id.in_(bahnhof_ids_in_order)).all()
    bahnhof_by_id = {b.id: b for b in bahnhof_rows}
    bahnhof_rows = [bahnhof_by_id[i] for i in bahnhof_ids_in_order if i in bahnhof_by_id]

    # Maps für Mindesttarif / Mindestdauer (für Segment-Info)
    min_cost_map = to_json_keyed_map(compute_min_cost_map(selected_strecke_id))
    min_duration_map = to_json_keyed_map(compute_min_duration_map(selected_strecke_id))

    # Bestehende Haltepunkte (die sind fix, werden nur angezeigt)
    existing_stops = (
        db.session.query(Haltepunkt)
        .filter(Haltepunkt.halteplan_id == halteplan_id)
        .order_by(Haltepunkt.position)
        .all()
    )
    halte_ids = [h.bahnhof_id for h in existing_stops]

    # Haltezeiten pro Zwischenhalt (Index: Stop 2..n-1)
    existing_dwell_by_index = []
    if len(existing_stops) >= 3:
        for h in existing_stops[1:-1]:
            existing_dwell_by_index.append(int(h.halte_dauer_min or 0))

    # bestehende Segmente (Index: pos-1)
    existing_segments = (
        db.session.query(HalteplanSegment)
        .filter(HalteplanSegment.halteplan_id == halteplan_id)
        .order_by(HalteplanSegment.position)
        .all()
    )
    existing_seg_durations = [int(s.duration_min or 0) for s in existing_segments]
    existing_seg_prices = [float(s.base_price or 0.0) for s in existing_segments]

    if request.method == "POST":
        # nur Bezeichnung + Werte speichern, NICHT Strecke/Stops ändern
        bezeichnung = request.form.get("bezeichnung", "").strip()
        if not bezeichnung:
            flash("Bitte eine Bezeichnung eingeben.", "warning")
            return redirect(url_for("halteplan_edit", halteplan_id=halteplan_id))

        seg_durations = request.form.getlist("segment_duration_min[]")
        seg_base_prices = request.form.getlist("segment_base_price[]")
        halte_dauern = request.form.getlist("halte_dauer_min[]")

        n = len(halte_ids)
        if n < 2:
            flash("Halteplan hat zu wenige Haltepunkte.", "warning")
            return redirect(url_for("halteplaene_list"))

        if len(seg_durations) != n - 1 or len(seg_base_prices) != n - 1:
            flash("Segmentdaten unvollständig.", "warning")
            return redirect(url_for("halteplan_edit", halteplan_id=halteplan_id))

        if len(halte_dauern) != max(0, n - 2):
            flash("Haltezeiten unvollständig.", "warning")
            return redirect(url_for("halteplan_edit", halteplan_id=halteplan_id))

        # Halteplan updaten
        hp.bezeichnung = bezeichnung

        # wir löschen Segmente und schreiben neu (Stops bleiben, aber wir setzen Haltezeiten neu)
        # 1) Haltezeiten in vorhandenen Haltepunkten updaten
        #    Regel: erster + letzter = 0, dazwischen aus halte_dauern[]
        for idx, h in enumerate(existing_stops):
            if idx == 0 or idx == (n - 1):
                h.halte_dauer_min = 0
            else:
                try:
                    h.halte_dauer_min = int(halte_dauern[idx - 1])
                except:
                    h.halte_dauer_min = 0

        # 2) Segmente löschen + neu anlegen
        HalteplanSegment.query.filter_by(halteplan_id=halteplan_id).delete(synchronize_session=False)
        db.session.flush()

        # min_cost/min_dur neu berechnen anhand Strecke + halte_ids
        # (für Sicherheit: min_cost aus Map holen, duration min steht im Formular sowieso)
        for pos in range(1, n):
            from_b = halte_ids[pos - 1]
            to_b = halte_ids[pos]
            k = f"{from_b}-{to_b}"

            try:
                min_cost = float(min_cost_map.get(k, 0.0))
            except:
                min_cost = 0.0

            try:
                dur = int(seg_durations[pos - 1])
            except:
                dur = 0

            try:
                base_price = float(seg_base_prices[pos - 1])
            except:
                base_price = min_cost

            db.session.add(
                HalteplanSegment(
                    halteplan_id=halteplan_id,
                    von_haltepunkt_id=existing_stops[pos - 1].id,
                    nach_haltepunkt_id=existing_stops[pos].id,
                    position=pos,
                    min_cost=min_cost,
                    duration_min=dur,
                    base_price=base_price,
                )
            )

        db.session.commit()
        flash("Halteplan wurde aktualisiert.", "success")
        return redirect(url_for("halteplaene_list"))

    return render_template(
        "halteplan_edit.html",
        title=f"Halteplan bearbeiten",
        hp=hp,
        strecken=strecken,
        selected_strecke_id=selected_strecke_id,
        bahnhof_rows=bahnhof_rows,
        existing_bahnhof_ids=halte_ids,
        min_cost_map=min_cost_map,
        min_duration_map=min_duration_map,
        existing_seg_durations=existing_seg_durations,
        existing_seg_prices=existing_seg_prices,
        existing_dwell_by_index=existing_dwell_by_index,
    )



@app.route("/api/fahrten/<int:fart_id>/refresh", methods=["POST"])
def api_refresh_fahrt(fart_id):
    result = refresh_fahrt_snapshot(fart_id)
    return jsonify(result), 200

####fürs synchen script aufrufen/damit alles auf den richtigen ports läuft


@app.route("/api/sync/strecken", methods=["POST"])
def api_sync_strecken():
    from app.services.strecken_import import sync_from_strecken
    result = sync_from_strecken("http://127.0.0.1:5001")
    return jsonify(result)
