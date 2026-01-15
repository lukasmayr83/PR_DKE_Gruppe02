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
from datetime import datetime, date, time, timedelta, timezone
import sqlalchemy as sa
from sqlalchemy.orm import aliased
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
    StreckeAbschnitt,
    FahrtSegment,
    FahrtHalt,
    Zug,
    ZugWartung
)
from urllib.parse import urlsplit
from functools import wraps
from sqlalchemy import func, and_
from app.services.strecken_import import sync_from_strecken
from app.services.fahrt_refresh import refresh_fahrt_snapshot
from app.services.halteplan_pricing import compute_min_cost_map, compute_min_duration_map, to_json_keyed_map
from sqlalchemy.orm import joinedload, selectinload
from app.services.fahrt_builder import rebuild_fahrt_halte_und_segmente
from app.services.sync_flotte import sync_from_flotte
from app.services.sync_wartungen import sync_wartungen_from_flotte
from app.services.wartung_check import has_wartung_overlap, find_zug_fahrt_overlap

from app.services.fahrplan_helper import (
    generate_datetimes_interval,
    compute_fahrt_window,
    auto_assign_trains,
    auto_assign_crew,
)

import requests

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

def create_fahrt_internal(
    *,
    halteplan_id: int,
    zug_id: int,
    abfahrt_dt: datetime,
    mitarbeiter_ids: list[int],
    price_factor: float,
) -> Fahrtdurchfuehrung:
    """
    Interne Create-Logik für eine Fahrtdurchführung.
    Identisch zur bisherigen fahrten_new-Logik, aber:
    - keine flash/redirect
    - Fehler via Exceptions (ValueError/RuntimeError)
    - KEIN commit (Caller entscheidet commit/rollback)
    """

    if price_factor < 1.0:
        raise ValueError("Preisfaktor muss ≥ 1.0 sein.")

    # 1) Fahrtdurchführung anlegen
    f = Fahrtdurchfuehrung(
        halteplan_id=halteplan_id,
        zug_id=zug_id,
        status=FahrtdurchfuehrungStatus.PLANMAESSIG,
        verspaetung_min=0,
        abfahrt_zeit=abfahrt_dt,
        price_factor=price_factor,
    )
    db.session.add(f)
    db.session.flush()  # f.fahrt_id verfügbar

    # 2) Dienstzuweisungen speichern
    for mid in (mitarbeiter_ids or []):
        db.session.add(Dienstzuweisung(fahrt_id=f.fahrt_id, mitarbeiter_id=mid))

    # 3) Haltepunkte + Segmente aus Halteplan holen
    hp_stops = (
        db.session.query(Haltepunkt)
        .filter(Haltepunkt.halteplan_id == f.halteplan_id)
        .order_by(Haltepunkt.position)
        .all()
    )
    if len(hp_stops) < 2:
        raise ValueError("Der ausgewählte Halteplan hat zu wenige Haltepunkte.")

    hp_segs = (
        db.session.query(HalteplanSegment)
        .filter(HalteplanSegment.halteplan_id == f.halteplan_id)
        .order_by(HalteplanSegment.position)
        .all()
    )
    if len(hp_segs) != (len(hp_stops) - 1):
        raise ValueError("Halteplan-Segmente passen nicht zur Anzahl der Haltepunkte.")

    # 4) FahrtHalt erzeugen
    fahrt_halte: list[FahrtHalt] = []
    for idx, hp_h in enumerate(hp_stops, start=1):
        fh = FahrtHalt(
            fahrt_id=f.fahrt_id,
            bahnhof_id=hp_h.bahnhof_id,
            position=idx,
            ankunft_zeit=None,
            abfahrt_zeit=None,
        )
        db.session.add(fh)
        fahrt_halte.append(fh)

    db.session.flush()  # IDs für von_halt_id / nach_halt_id

    # 5) Zeiten berechnen + FahrtSegment erzeugen
    current = f.abfahrt_zeit
    fahrt_halte[0].ankunft_zeit = current
    fahrt_halte[0].abfahrt_zeit = current

    for i, hp_seg in enumerate(hp_segs):
        from_h = fahrt_halte[i]
        to_h = fahrt_halte[i + 1]

        travel_min = int(hp_seg.duration_min or 0)
        seg_arrival = current + timedelta(minutes=travel_min)

        # next stop arrival
        to_h.ankunft_zeit = seg_arrival

        # dwell at "to" (außer letzter Halt)
        is_last_stop = (i + 1) == (len(fahrt_halte) - 1)
        if not is_last_stop:
            dwell = int(hp_stops[i + 1].halte_dauer_min or 0)
            to_h.abfahrt_zeit = seg_arrival + timedelta(minutes=dwell)
        else:
            to_h.abfahrt_zeit = None

        # Segment speichern (Preis = base_price * price_factor)
        base = float(hp_seg.base_price or 0.0)
        final_price = round(base * float(f.price_factor or 1.0), 2)

        db.session.add(
            FahrtSegment(
                fahrt_id=f.fahrt_id,
                von_halt_id=from_h.id,
                nach_halt_id=to_h.id,
                position=i + 1,
                final_price=final_price,
                duration_min=travel_min,
            )
        )

        # next loop current time = departure from "to" (oder arrival wenn letzter)
        current = to_h.abfahrt_zeit or to_h.ankunft_zeit

    fahrt_start = f.abfahrt_zeit
    fahrt_end = current  # nach Loop: letzte Ankunft

    # 6) Wartungs-Check
    zug = db.session.get(Zug, f.zug_id)
    if zug and has_wartung_overlap(zug.external_id, fahrt_start, fahrt_end):
        raise RuntimeError(
            "Konflikt: Der ausgewählte Zug hat in diesem Zeitraum eine Wartung."
        )

    # 7) Overlap-Check mit anderen Fahrtdurchführungen
    with db.session.no_autoflush:
        conflict = find_zug_fahrt_overlap(
            zug_id=f.zug_id,
            start_dt=fahrt_start,
            end_dt=fahrt_end,
            exclude_fahrt_id=f.fahrt_id,
        )

    if conflict:
        raise RuntimeError(
            f"Konflikt: Zug ist bereits in Fahrtdurchführung #{conflict.fahrt_id} "
            f"({conflict.abfahrt_zeit}) belegt."
        )

    return f





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

    # Mitarbeiter laden
    alle_mitarbeiter = Mitarbeiter.query.order_by(Mitarbeiter.name).all()
    form.mitarbeiter_ids.choices = [(m.id, m.name) for m in alle_mitarbeiter]

    # Züge laden
    form.zug_id.choices = [
        (z.id, f"{z.bezeichnung} (ext={z.external_id})")
        for z in Zug.query.order_by(Zug.bezeichnung).all()
    ]

    if form.validate_on_submit():
        # Abfahrtszeit lesen (datetime-local => "YYYY-MM-DDTHH:MM")
        abfahrt_raw = (request.form.get("abfahrt_zeit") or "").strip()
        if not abfahrt_raw:
            flash("Bitte eine Abfahrtszeit angeben.", "warning")
            return redirect(url_for("fahrten_new"))

        try:
            abfahrt_dt = datetime.fromisoformat(abfahrt_raw)  # naive datetime ok
        except ValueError:
            flash("Abfahrtszeit hat ein ungültiges Format.", "warning")
            return redirect(url_for("fahrten_new"))

        # Preisfaktor
        price_factor_raw = (request.form.get("price_factor") or "").strip()
        try:
            price_factor = float(price_factor_raw) if price_factor_raw else 1.0
        except ValueError:
            flash("Preisfaktor muss eine Zahl sein.", "warning")
            return redirect(url_for("fahrten_new"))

        if price_factor < 1.0:
            flash("Preisfaktor muss ≥ 1.0 sein.", "warning")
            return redirect(url_for("fahrten_new"))

        try:
            create_fahrt_internal(
                halteplan_id=form.halteplan_id.data,
                zug_id=form.zug_id.data,
                abfahrt_dt=abfahrt_dt,
                mitarbeiter_ids=list(form.mitarbeiter_ids.data or []),
                price_factor=price_factor,
            )
            db.session.commit()
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "warning")
            return redirect(url_for("fahrten_new"))
        except RuntimeError as e:
            db.session.rollback()
            flash(str(e), "danger")
            return redirect(url_for("fahrten_new"))
        except Exception as e:
            db.session.rollback()
            flash(f"Unerwarteter Fehler beim Anlegen: {e}", "danger")
            return redirect(url_for("fahrten_new"))

        flash("Fahrtdurchführung inkl. Personal + Halte/Segmente erfolgreich angelegt.", "success")
        return redirect(url_for("fahrten_list"))

    return render_template(
        "fahrten_new.html",
        title="Neue Fahrtdurchführung",
        form=form,
        mitarbeiter_liste=alle_mitarbeiter,
    )


@app.route("/fahrten/<int:fahrt_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def fahrt_edit(fahrt_id: int):
    fahrt = Fahrtdurchfuehrung.query.get_or_404(fahrt_id)
    form = FahrtEditForm()

    # Mitarbeiterliste
    alle_mitarbeiter = db.session.scalars(
        sa.select(Mitarbeiter).order_by(Mitarbeiter.name)
    ).all()

    # ZÜGE laden (für Radio-Auswahl)
    alle_zuege = db.session.scalars(
        sa.select(Zug).order_by(Zug.bezeichnung)
    ).all()

    # bestehende Zuweisungen
    bestehende_zuweisungen = db.session.scalars(
        sa.select(Dienstzuweisung).where(Dienstzuweisung.fahrt_id == fahrt_id)
    ).all()
    bestehende_ids = {dz.mitarbeiter_id for dz in bestehende_zuweisungen}

    # Berechnete Halte/Segmente laden
    halte_rows = db.session.execute(
        sa.select(
            FahrtHalt.position,
            Bahnhof.name.label("bahnhof_name"),
            FahrtHalt.ankunft_zeit,
            FahrtHalt.abfahrt_zeit,
        )
        .join(Bahnhof, Bahnhof.id == FahrtHalt.bahnhof_id)
        .where(FahrtHalt.fahrt_id == fahrt_id)
        .order_by(FahrtHalt.position)
    ).all()

    segment_rows = db.session.scalars(
        sa.select(FahrtSegment)
        .where(FahrtSegment.fahrt_id == fahrt_id)
        .order_by(FahrtSegment.position)
    ).all()

    if request.method == "GET":
        form.status.data = fahrt.status.name
        form.verspaetung_min.data = fahrt.verspaetung_min or 0

    if form.validate_on_submit():
        # 1) Status / Verspätung
        fahrt.status = FahrtdurchfuehrungStatus[form.status.data]
        fahrt.verspaetung_min = form.verspaetung_min.data if form.status.data == "VERSPAETET" else 0

        # 2) Abfahrtszeit
        abfahrt_raw = request.form.get("abfahrt_zeit", "").strip()
        if not abfahrt_raw:
            flash("Bitte eine Abfahrtszeit angeben.", "warning")
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))
        try:
            fahrt.abfahrt_zeit = datetime.strptime(abfahrt_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Ungültiges Datumsformat für Abfahrtszeit.", "warning")
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))

        # 3) Preisfaktor
        pf_raw = request.form.get("price_factor", "1.0").strip()
        try:
            pf = float(pf_raw)
        except ValueError:
            pf = 1.0
        fahrt.price_factor = max(1.0, pf)

        # 4) NEU: Zug ändern (Radio: genau 1 Wert)
        zug_id_raw = (request.form.get("zug_id") or "").strip()
        if not zug_id_raw:
            flash("Bitte einen Zug auswählen.", "warning")
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))
        try:
            new_zug_id = int(zug_id_raw)
        except ValueError:
            flash("Ungültige Zug-Auswahl.", "warning")
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))

        #  Existenz check
        zug_obj = db.session.get(Zug, new_zug_id)
        if not zug_obj:
            flash("Ausgewählter Zug existiert nicht.", "warning")
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))

        fahrt.zug_id = new_zug_id

        # 5) Mitarbeiter-Zuweisungen
        id_strings = request.form.getlist("mitarbeiter_ids")
        neue_ids = {int(x) for x in id_strings}

        for dz in bestehende_zuweisungen:
            if dz.mitarbeiter_id not in neue_ids:
                db.session.delete(dz)

        for mid in neue_ids:
            if mid not in bestehende_ids:
                db.session.add(Dienstzuweisung(fahrt_id=fahrt_id, mitarbeiter_id=mid))

        # 6) Halte + Segmente neu berechnen/speichern
        try:
            rebuild_fahrt_halte_und_segmente(fahrt)
        except Exception as e:
            db.session.rollback()
            flash(f"Fehler beim Neubauen der Fahrt-Halte/Segmente: {e}", "danger")
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))

        # 7) Zeitraum bestimmen (ohne extra Endzeit-Spalte)
        fahrt_start = fahrt.abfahrt_zeit
        with db.session.no_autoflush:
            fahrt_end = db.session.scalar(
                sa.select(sa.func.max(FahrtHalt.ankunft_zeit)).where(FahrtHalt.fahrt_id == fahrt_id)
            )
        db.session.flush()

        if not fahrt_start or not fahrt_end:
            db.session.rollback()
            flash("Konnte Start/Ende der Fahrt nicht berechnen.", "danger")
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))

        # 8) Wartungs-Check
        if zug_obj and has_wartung_overlap(zug_obj.external_id, fahrt_start, fahrt_end):
            db.session.rollback()
            flash(
                "Konflikt: Der ausgewählte Zug hat in diesem Zeitraum eine Wartung. "
                "Bitte anderen Zug oder andere Abfahrtszeit wählen.",
                "danger",
            )
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))

        # 9) Overlap-Check mit anderen Fahrten (exclude self)
        with db.session.no_autoflush:
            conflict = find_zug_fahrt_overlap(
                zug_id=fahrt.zug_id,
                start_dt=fahrt_start,
                end_dt=fahrt_end,
                exclude_fahrt_id=fahrt_id,
            )

        if conflict:
            db.session.rollback()
            flash(
                f"Konflikt: Zug ist bereits in Fahrtdurchführung #{conflict.fahrt_id} "
                f"({conflict.abfahrt_zeit}) belegt. Bitte anderen Zug oder Abfahrtszeit wählen.",
                "danger",
            )
            return redirect(url_for("fahrt_edit", fahrt_id=fahrt_id))

        db.session.commit()
        flash("Fahrtdurchführung wurde gespeichert.", "success")
        return redirect(url_for("fahrten_list"))

    return render_template(
        "fahrt_edit.html",
        title=f"Fahrt {fahrt.fahrt_id} bearbeiten",
        fahrt=fahrt,
        form=form,
        mitarbeiter_liste=alle_mitarbeiter,
        zugewiesene_ids=bestehende_ids,
        halte_rows=halte_rows,
        segment_rows=segment_rows,
        alle_zuege=alle_zuege,
    )

@app.route("/fahrten/bulk", methods=["GET"])
@login_required
@admin_required
def fahrten_bulk_form():
    halteplaene = Halteplan.query.order_by(Halteplan.bezeichnung).all()
    mitarbeiter = Mitarbeiter.query.order_by(Mitarbeiter.name).all()
    return render_template(
        "fahrten_bulk_form.html",
        title="Fahrten im Intervall anlegen",
        halteplaene=halteplaene,
        mitarbeiter=mitarbeiter,
    )

@app.route("/fahrten/bulk/preview", methods=["POST"])
@login_required
@admin_required
def fahrten_bulk_preview():
    halteplan_id = int(request.form["halteplan_id"])

    start_date = date.fromisoformat(request.form["start_date"])
    end_date = date.fromisoformat(request.form["end_date"])
    start_time = time.fromisoformat(request.form["start_time"])
    interval_minutes = int(request.form["interval_minutes"])
    trips_per_day = int(request.form["trips_per_day"])
    weekdays = {int(x) for x in request.form.getlist("weekdays")}

    crew_size = int(request.form.get("crew_size") or 0)

    pf_raw = (request.form.get("price_factor") or "1.0").strip()
    try:
        price_factor = float(pf_raw)
    except ValueError:
        price_factor = 1.0
    if price_factor < 1.0:
        price_factor = 1.0

    datetimes = generate_datetimes_interval(
        start_date=start_date,
        end_date=end_date,
        first_departure_time=start_time,
        interval_minutes=interval_minutes,
        trips_per_day=trips_per_day,
        weekdays=weekdays,
    )

    windows = [compute_fahrt_window(halteplan_id, dt) for dt in datetimes]

    zuege = Zug.query.order_by(Zug.bezeichnung).all()
    suggested_zug_ids = auto_assign_trains(windows, zuege)

    mitarbeiter_ids = [m.id for m in Mitarbeiter.query.order_by(Mitarbeiter.name).all()]
    crew_assignments = auto_assign_crew(
        mitarbeiter_ids=mitarbeiter_ids,
        crew_size=crew_size,
        num_fahrten=len(windows),
        seed=42,
    )

    preview_rows = []
    for idx, (start_dt, end_dt) in enumerate(windows):
        zug_id = suggested_zug_ids[idx]
        errors = []

        if zug_id is None:
            errors.append("Kein Zug verfügbar")

        preview_rows.append({
            "index": idx,
            "start": start_dt,
            "end": end_dt,
            "zug_id": zug_id,
            "crew_ids": crew_assignments[idx],
            "errors": errors,
            "is_valid": len(errors) == 0,
        })

    return render_template(
        "fahrten_bulk_preview.html",
        title="Preview: Fahrten im Intervall",
        halteplan_id=halteplan_id,
        zuege=zuege,
        preview_rows=preview_rows,
        crew_size=crew_size,
        price_factor=price_factor,
    )



@app.route("/fahrten/bulk/create", methods=["POST"])
@login_required
@admin_required
def fahrten_bulk_create():
    halteplan_id = int(request.form["halteplan_id"])

    # Preisfaktor
    pf_raw = (request.form.get("price_factor") or "1.0").strip()
    try:
        price_factor = float(pf_raw)
    except ValueError:
        price_factor = 1.0
    if price_factor < 1.0:
        price_factor = 1.0

    created = 0

    try:
        i = 0
        while True:
            start_key = f"start_{i}"
            zug_key = f"zug_{i}"
            if start_key not in request.form:
                break

            start_dt = datetime.fromisoformat(request.form[start_key])

            zug_id_raw = (request.form.get(zug_key) or "").strip()
            if not zug_id_raw:
                raise ValueError(f"Bei Fahrt #{i+1} wurde kein Zug ausgewählt.")

            zug_id = int(zug_id_raw)

            crew_ids = [int(x) for x in request.form.getlist(f"crew_{i}")]

            create_fahrt_internal(
                halteplan_id=halteplan_id,
                zug_id=zug_id,
                abfahrt_dt=start_dt,
                mitarbeiter_ids=crew_ids,
                price_factor=price_factor,
            )

            created += 1
            i += 1

        if created == 0:
            raise ValueError("Keine Fahrten zum Anlegen übergeben.")

        db.session.commit()
        flash(f"{created} Fahrten wurden angelegt.", "success")
        return redirect(url_for("fahrten_list"))

    except Exception as e:
        db.session.rollback()
        flash(f"Abbruch: Es wurde nichts gespeichert. Grund: {e}", "danger")
        return redirect(url_for("fahrten_bulk_form"))



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

        # 1) nichtselectierte löschen
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
    if not current_user.mitarbeiter:
        flash("Für dieses Benutzerkonto ist kein Mitarbeiter hinterlegt.", "warning")
        return redirect(url_for("index"))

    ma = current_user.mitarbeiter

    fahrten = (
        db.session.query(Fahrtdurchfuehrung)
        .join(Dienstzuweisung, Dienstzuweisung.fahrt_id == Fahrtdurchfuehrung.fahrt_id)
        .filter(Dienstzuweisung.mitarbeiter_id == ma.id)
        .order_by(Fahrtdurchfuehrung.abfahrt_zeit.asc())
        .all()
    )

    fahrt_ids = [f.fahrt_id for f in fahrten]
    start_info = {}
    end_info = {}

    if fahrt_ids:
        # START: position == 1
        start_rows = (
            db.session.query(
                FahrtHalt.fahrt_id,
                Bahnhof.name,
                FahrtHalt.abfahrt_zeit,
                FahrtHalt.ankunft_zeit,
            )
            .join(Bahnhof, Bahnhof.id == FahrtHalt.bahnhof_id)
            .filter(FahrtHalt.fahrt_id.in_(fahrt_ids))
            .filter(FahrtHalt.position == 1)
            .all()
        )

        for fid, bname, abf, ank in start_rows:
            start_info[fid] = {
                "bahnhof": bname,
                "zeit": abf or ank,  # fallback falls abfahrt_zeit NULL wäre
            }

        # ENDE: max(position) pro fahrt
        subq = (
            db.session.query(
                FahrtHalt.fahrt_id.label("fahrt_id"),
                func.max(FahrtHalt.position).label("max_pos"),
            )
            .filter(FahrtHalt.fahrt_id.in_(fahrt_ids))
            .group_by(FahrtHalt.fahrt_id)
            .subquery()
        )

        end_rows = (
            db.session.query(
                FahrtHalt.fahrt_id,
                Bahnhof.name,
                FahrtHalt.ankunft_zeit,
            )
            .join(subq, and_(
                FahrtHalt.fahrt_id == subq.c.fahrt_id,
                FahrtHalt.position == subq.c.max_pos
            ))
            .join(Bahnhof, Bahnhof.id == FahrtHalt.bahnhof_id)
            .all()
        )

        for fid, bname, ank in end_rows:
            end_info[fid] = {
                "bahnhof": bname,
                "zeit": ank,
            }

    return render_template(
        "meine_fahrten.html",
        title="Meine Fahrten",
        fahrten=fahrten,
        mitarbeiter=ma,
        start_info=start_info,
        end_info=end_info,
    )


@app.route("/fahrten/alle")
@login_required
def fahrten_alle():
    if not current_user.mitarbeiter:
        abort(403)

    mitarbeiter = current_user.mitarbeiter

    #1) Basis: alle Fahrten
    fahrten = (
        db.session.query(Fahrtdurchfuehrung)
        .order_by(Fahrtdurchfuehrung.fahrt_id)
        .all()
    )

    #2) Zuweisungen des Mitarbeiters
    zugewiesene_fahrten_ids = {
        dz.fahrt_id
        for dz in Dienstzuweisung.query.filter_by(mitarbeiter_id=mitarbeiter.id).all()
    }

    # 3) Start-/Endhalt pro Fahrt
    FH_start = aliased(FahrtHalt)
    FH_end = aliased(FahrtHalt)
    B_start = aliased(Bahnhof)
    B_end = aliased(Bahnhof)

    # min/max Position je fahrt_id
    pos_subq = (
        db.session.query(
            FahrtHalt.fahrt_id.label("fahrt_id"),
            sa.func.min(FahrtHalt.position).label("min_pos"),
            sa.func.max(FahrtHalt.position).label("max_pos"),
        )
        .group_by(FahrtHalt.fahrt_id)
        .subquery()
    )

    rows = (
        db.session.query(
            Fahrtdurchfuehrung.fahrt_id.label("fahrt_id"),

            # Start
            B_start.name.label("start_bahnhof"),
            FH_start.abfahrt_zeit.label("start_abfahrt_zeit"),

            # Ende
            B_end.name.label("end_bahnhof"),
            FH_end.ankunft_zeit.label("end_ankunft_zeit"),
        )
        .join(pos_subq, pos_subq.c.fahrt_id == Fahrtdurchfuehrung.fahrt_id)

        # Start-Halt (Position = min_pos)
        .join(
            FH_start,
            sa.and_(
                FH_start.fahrt_id == Fahrtdurchfuehrung.fahrt_id,
                FH_start.position == pos_subq.c.min_pos,
            ),
        )
        .join(B_start, B_start.id == FH_start.bahnhof_id)

        # End-Halt (Position = max_pos)
        .join(
            FH_end,
            sa.and_(
                FH_end.fahrt_id == Fahrtdurchfuehrung.fahrt_id,
                FH_end.position == pos_subq.c.max_pos,
            ),
        )
        .join(B_end, B_end.id == FH_end.bahnhof_id)

        .all()
    )

    # Map: fahrt_id -> start/end infos
    start_end_map = {
        r.fahrt_id: {
            "start_bahnhof": r.start_bahnhof,
            "start_abfahrt_zeit": r.start_abfahrt_zeit,
            "end_bahnhof": r.end_bahnhof,
            "end_ankunft_zeit": r.end_ankunft_zeit,
        }
        for r in rows
    }

    return render_template(
        "fahrten_alle.html",
        title="Alle Fahrten",
        fahrten=fahrten,
        mitarbeiter=mitarbeiter,
        zugewiesene_fahrten_ids=zugewiesene_fahrten_ids,
        start_end_map=start_end_map,
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



@app.route("/halteplaene")
@login_required
@admin_required
def halteplaene_list():
    # daten laden
    halteplaene = db.session.scalars(
    sa.select(Halteplan)
    .options(
        selectinload(Halteplan.strecke),
        selectinload(Halteplan.haltepunkte),
        selectinload(Halteplan.segmente),
    )
    .order_by(Halteplan.halteplan_id.desc())
    ).all()

    rows = []
    for hp in halteplaene:
        haltepunkte = list(hp.haltepunkte or [])
        segmente = list(hp.segmente or [])

        start_name = "-"
        end_name = "-"

        if haltepunkte:
            start_bahnhof = db.session.get(Bahnhof, haltepunkte[0].bahnhof_id)
            end_bahnhof = db.session.get(Bahnhof, haltepunkte[-1].bahnhof_id)
            start_name = start_bahnhof.name if start_bahnhof else "-"
            end_name = end_bahnhof.name if end_bahnhof else "-"

        halte_count = len(haltepunkte)

        # Gesamtpreis: Summe Grundtarife (base_price)
        total_price = sum(float(s.base_price or 0.0) for s in segmente)

        # Gesamtdauer: Summe Segmentdauer + Summe Haltezeiten (letzter Halt sollte 0 sein)
        total_duration = sum(int(s.duration_min or 0) for s in segmente) + \
                         sum(int(h.halte_dauer_min or 0) for h in haltepunkte)

        rows.append({
            "id": hp.halteplan_id,
            "bezeichnung": hp.bezeichnung,
            "strecke_name": hp.strecke.name if hp.strecke else "-",
            "von": start_name,
            "bis": end_name,
            "halte_count": halte_count,
            "total_price": total_price,
            "total_duration": total_duration,
        })

    return render_template(
        "halteplaene_list.html",
        title="Haltepläne",
        rows=rows,
    )

@app.route("/halteplaene/new", methods=["GET", "POST"])
@login_required
@admin_required
def halteplan_new():
    # 1) Strecken laden
    strecken = Strecke.query.order_by(Strecke.name).all()
    if not strecken:
        flash("Keine Strecken vorhanden. Bitte zuerst Sync ausführen.", "warning")
        return redirect(url_for("halteplaene_list"))

    # 2) selected Strecke bestimmen
    selected_strecke_id = request.args.get("strecke_id", type=int) or strecken[0].id

    # 3) Bahnhof-Reihenfolge
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

    # unique
    seen = set()
    bahnhof_ids_in_order = [x for x in bahnhof_ids_in_order if not (x in seen or seen.add(x))]

    bahnhof_rows = Bahnhof.query.filter(Bahnhof.id.in_(bahnhof_ids_in_order)).all()
    bahnhof_by_id = {b.id: b for b in bahnhof_rows}
    bahnhof_rows = [bahnhof_by_id[i] for i in bahnhof_ids_in_order if i in bahnhof_by_id]

    # 4) Pricing/Duration Maps berechnen
    min_cost_map = to_json_keyed_map(compute_min_cost_map(selected_strecke_id))
    min_duration_map = to_json_keyed_map(compute_min_duration_map(selected_strecke_id))

    # POST: Halteplan + Haltepunkte + Segmente speichern
    if request.method == "POST":
        bezeichnung = request.form.get("bezeichnung", "").strip()
        strecke_id = request.form.get("strecke_id", type=int)
        halte_ids = request.form.getlist("halte_bahnhof_ids")
        halte_ids = [int(x) for x in halte_ids]

        if not bezeichnung or not strecke_id or len(halte_ids) < 2:
            flash("Bitte Bezeichnung wählen und mindestens 2 Haltepunkte auswählen.", "warning")
            return redirect(url_for("halteplan_new", strecke_id=selected_strecke_id))

        # 1) Halteplan anlegen
        hp = Halteplan(bezeichnung=bezeichnung, strecke_id=strecke_id)
        db.session.add(hp)
        db.session.flush()  # hp.halteplan_id verfügbar

        # 2) Haltepunkte anlegen
        halte_dauern = request.form.getlist("halte_dauer_min[]")
        halte_dauern_int: list[int] = []
        for x in halte_dauern:
            try:
                halte_dauern_int.append(int(x))
            except:
                halte_dauern_int.append(0)

        n = len(halte_ids)

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

        # 3) Segmente aus POST übernehmen
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

    # GET: Template rendern
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

    # Strecke fix
    selected_strecke_id = hp.strecke_id
    strecken = Strecke.query.order_by(Strecke.name).all()

    # Bahnhof-Reihenfolge
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

    # Maps für Mindesttarif / Mindestdauer
    min_cost_map = to_json_keyed_map(compute_min_cost_map(selected_strecke_id))
    min_duration_map = to_json_keyed_map(compute_min_duration_map(selected_strecke_id))

    # Bestehende Haltepunkte
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

    # bestehende Segmente
    existing_segments = (
        db.session.query(HalteplanSegment)
        .filter(HalteplanSegment.halteplan_id == halteplan_id)
        .order_by(HalteplanSegment.position)
        .all()
    )
    existing_seg_durations = [int(s.duration_min or 0) for s in existing_segments]
    existing_seg_prices = [float(s.base_price or 0.0) for s in existing_segments]

    if request.method == "POST":
        #  Bezeichnung + Werte speichern
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

        hp.bezeichnung = bezeichnung

        # 1) Haltezeiten in vorhandenen Haltepunkten updaten
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

@app.route("/halteplaene/<int:halteplan_id>/delete", methods=["GET"])
@login_required
@admin_required
def halteplan_delete_confirm(halteplan_id: int):
    hp = Halteplan.query.get_or_404(halteplan_id)

    fahrten = (
        Fahrtdurchfuehrung.query
        .filter_by(halteplan_id=halteplan_id)
        .order_by(Fahrtdurchfuehrung.fahrt_id)
        .all()
    )

    counts = {
        "fahrten": len(fahrten),
        "haltepunkte": len(hp.haltepunkte),
        "segmente": len(hp.segmente),
    }

    return render_template(
        "halteplan_delete_confirm.html",
        title="Halteplan löschen",
        hp=hp,
        fahrten=fahrten,
        counts=counts,
    )



@app.route("/halteplaene/<int:halteplan_id>/delete", methods=["GET", "POST"])
@login_required
@admin_required
def halteplan_delete(halteplan_id: int):
    hp = Halteplan.query.get_or_404(halteplan_id)

    # GET: Warnseite anzeigen
    if request.method == "GET":
        fahrten_count = len(hp.fahrten)
        haltepunkte_count = len(hp.haltepunkte)
        segmente_count = len(hp.segmente)
        return render_template(
            "halteplan_delete_confirm.html",
            title="Halteplan löschen",
            hp=hp,
            fahrten_count=fahrten_count,
            haltepunkte_count=haltepunkte_count,
            segmente_count=segmente_count,
        )

    db.session.delete(hp)
    db.session.commit()
    flash("Halteplan wurde gelöscht (inkl. Haltepunkte, Segmente, Fahrten).", "success")
    return redirect(url_for("halteplaene_list"))




@app.route("/api/fahrten/<int:fart_id>/refresh", methods=["POST"])
def api_refresh_fahrt(fart_id):
    result = refresh_fahrt_snapshot(fart_id)
    return jsonify(result), 200

#fürs synchen script aufrufen/damit alles auf den richtigen ports läuft

@app.route("/api/sync/strecken", methods=["POST"])
def api_sync_strecken():
    try:
        result = sync_from_strecken("http://127.0.0.1:5001")
        if not result.get("ok", True):
            return jsonify(result), 502
        return jsonify(result), 200
    except requests.RequestException as e:
        return jsonify({"ok": False, "error": str(e)}), 503
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/sync/flotte", methods=["POST"])
def api_sync_flotte():
    try:
        result = sync_from_flotte("http://127.0.0.1:5003")
        if not result.get("ok", True):
            return jsonify(result), 502
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@app.route("/api/sync/wartungen", methods=["POST"])
def api_sync_wartungen():
    try:
        result = sync_wartungen_from_flotte("http://127.0.0.1:5003")
        if not result.get("ok", True):
            return jsonify(result), 502
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503



# API by Daniel

@app.route("/api/fahrtdurchfuehrungen/snapshot", methods=["GET"])
def api_fahrtdurchfuehrungen_snapshot():
    def dt(v):
        return v.isoformat() if v else None

    # alle Fahrten laden
    fahrten = db.session.scalars(
        sa.select(Fahrtdurchfuehrung).order_by(Fahrtdurchfuehrung.fahrt_id.asc())
    ).all()

    items = []

    for f in fahrten:
        # Halte (mit Bahnhofnamen)
        halte_rows = db.session.execute(
            sa.select(
                FahrtHalt.id.label("halt_id"),
                FahrtHalt.bahnhof_id.label("bahnhof_id"),
                FahrtHalt.position.label("pos"),
                Bahnhof.name.label("bahnhof_name"),
                FahrtHalt.ankunft_zeit.label("ankunft"),
                FahrtHalt.abfahrt_zeit.label("abfahrt"),
            )
            .join(Bahnhof, Bahnhof.id == FahrtHalt.bahnhof_id)
            .where(FahrtHalt.fahrt_id == f.fahrt_id)
            .order_by(FahrtHalt.position.asc())
        ).all()

        # Segmente (Preis je Segment), map: nach_halt_id -> final_price
        seg_rows = db.session.execute(
            sa.select(
                FahrtSegment.nach_halt_id,
                FahrtSegment.final_price,
                FahrtSegment.position,
            )
            .where(FahrtSegment.fahrt_id == f.fahrt_id)
            .order_by(FahrtSegment.position.asc())
        ).all()

        price_by_nach_halt = {int(r.nach_halt_id): float(r.final_price or 0.0) for r in seg_rows}

        haltepunkte = []
        for r in halte_rows:
            halt_id = int(r.halt_id)
            pos = int(r.pos)

            haltepunkte.append({
                "haltId": halt_id,
                "order": pos,
                "bahnhofId": int(r.bahnhof_id),
                "bahnhofName": r.bahnhof_name,
                "planAnkunft": dt(r.ankunft),
                "planAbfahrt": dt(r.abfahrt),
                "tarif": 0.0 if pos == 1 else float(price_by_nach_halt.get(halt_id, 0.0)),
            })

        items.append({
            "fahrtdurchfuehrungId": int(f.fahrt_id),
            "halteplanId": int(f.halteplan_id),
            "zugId": int(f.zug_id or 0),
            "haltepunkte": haltepunkte,
        })

    return jsonify({"total": len(items), "items": items}), 200

# API by Daniel Aktion Halteplan

@app.route("/api/halteplaene", methods=["GET"])
def api_halteplaene():
    q = (request.args.get("q") or "").strip().lower()

    halteplaene = db.session.scalars(
        sa.select(Halteplan)
        .options(
            selectinload(Halteplan.strecke),
            selectinload(Halteplan.haltepunkte),
        )
        .order_by(Halteplan.halteplan_id.asc())
    ).all()

    # Bahnhofnamen einmal laden
    bahnhof_ids = set()
    for hp in halteplaene:
        for h in (hp.haltepunkte or []):
            bahnhof_ids.add(int(h.bahnhof_id))

    bahnhoefe = Bahnhof.query.filter(Bahnhof.id.in_(list(bahnhof_ids))).all() if bahnhof_ids else []
    bahnhof_name = {int(b.id): b.name for b in bahnhoefe}

    items = []
    for hp in halteplaene:
        bezeichnung = (hp.bezeichnung or "").strip()
        strecke_name = hp.strecke.name if hp.strecke else ""

        stops = sorted(list(hp.haltepunkte or []), key=lambda x: x.position or 0)
        von = "-"
        bis = "-"
        if stops:
            von = bahnhof_name.get(int(stops[0].bahnhof_id), "-")
            bis = bahnhof_name.get(int(stops[-1].bahnhof_id), "-")

        hay = " ".join([bezeichnung, strecke_name, von, bis]).lower()
        if q and q not in hay:
            continue

        items.append({
            "halteplanId": int(hp.halteplan_id),
            "bezeichnung": bezeichnung,
            "streckeId": int(hp.strecke_id) if hp.strecke_id else None,
            "streckeName": strecke_name or None,
            "von": von,
            "bis": bis,
            "halteCount": len(stops),
        })

    return jsonify({"total": len(items), "items": items}), 200