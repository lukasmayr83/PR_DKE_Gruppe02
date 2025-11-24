from flask import render_template, flash, redirect, url_for, request, jsonify
from urllib.parse import urlsplit
from app import app,db
from app.forms import LoginForm, PersonenwagenForm, TriebwagenForm, ZuegeForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Role, Personenwagen, Triebwagen, Zuege, Wagen
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
    # get('q', '')  - falls "q" vorhanden → Wert nehmen - sonst leerer String
    # strip() entfernt Leerzeichen am Anfang/Ende.
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

@app.route('/personenwagen_action', methods=['POST'])
@login_required
def personenwagen_action():
    wagen_id = request.form.get("selected_wagen")
    action = request.form.get("action")

    if not wagen_id:
        flash("Bitte wählen Sie einen Personenwagen aus!")
        return redirect(url_for('uebers_personenwagen'))

    pw = db.session.get(Personenwagen, wagen_id)

    if not pw:
        flash("Personenwagen nicht gefunden.")
        return redirect(url_for('uebers_personenwagen'))
    # Personenwagen kann nicht gelöscht werden, wenn er einem Zug zugeordnet ist
    if action == "loeschen":
        if pw.istfrei is not None:
            flash("Wagen ist in einem Zug und kann nicht gelöscht werden!")
            return redirect(url_for('uebers_personenwagen'))

        db.session.delete(pw)
        db.session.commit()
        flash("Personenwagen erfolgreich gelöscht.")
        return redirect(url_for('dashboard_admin'))

    if action == "bearbeiten":
        return redirect(url_for('bearbeite_personenwagen', wagen_id=pw.wagenid))

    return redirect(url_for('dashboard_admin'))

@app.route('/bearbeite_personenwagen/<int:wagen_id>', methods=['GET', 'POST'])
@login_required
def bearbeite_personenwagen(wagen_id):

    pw = db.session.get(Personenwagen, wagen_id)

    if not pw:
        flash("Personenwagen wurde nicht gefunden.")
        return redirect(url_for('uebers_personenwagen'))

    form = PersonenwagenForm(obj=pw)  # vorbefüllen!

    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_personenwagen'))

    if form.validate_on_submit():
        # Spurweite darf NICHT geändert werden, wenn der Wagen in einem Zug ist
        if pw.istfrei is not None and pw.spurweite != form.spurweite.data:
            flash("Spurweite darf nicht geändert werden, wenn der Wagen in einem Zug ist!")
            return redirect(url_for('bearbeite_personenwagen', wagen_id=wagen_id))
        # Maximales Gewicht darf NICHT geändert werden, wenn der Wagen in einem Zug ist
        if pw.istfrei is not None and pw.maxgewicht != form.maxgewicht.data:
            flash("Maximales Gewicht darf nicht geändert werden, wenn der Wagen in einem Zug ist!")
            return redirect(url_for('bearbeite_personenwagen', wagen_id=wagen_id))

        pw.kapazitaet = form.kapazitaet.data
        pw.maxgewicht = form.maxgewicht.data
        pw.spurweite  = form.spurweite.data

        db.session.commit()
        flash("Personenwagen erfolgreich bearbeitet.")
        return redirect(url_for('dashboard_admin'))

    return render_template("bearbeiten_personenwagen.html", form=form, wagen=pw)

@app.route('/uebers_triebwagen')
@login_required
def uebers_triebwagen():
        # get('q', '')  - falls "q" vorhanden → Wert nehmen - sonst leerer String
        # strip() entfernt Leerzeichen am Anfang/Ende.
        suchbegriff = request.args.get('q', '').strip()

        query = db.select(Triebwagen).order_by(Triebwagen.wagenid)

        if suchbegriff:
            query = query.where(
                or_(
                    Triebwagen.maxzugkraft.cast(sa.String).like(f"%{suchbegriff}%"),
                    Triebwagen.spurweite.cast(sa.String).like(f"%{suchbegriff}%")
                )
            )

        triebwagen_liste = db.session.execute(query).scalars().all()
        return render_template('uebers_triebwagen.html', title='Triebwagen-Übersicht',
                               triebwagen_liste=triebwagen_liste)

@app.route('/hinzufuegen_triebwagen', methods=['GET', 'POST'])
@login_required
def hinzufuegen_triebwagen():
    form = TriebwagenForm()

    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_triebwagen'))

    if form.validate_on_submit():
        neuer_wagen = Triebwagen(
            maxzugkraft=form.maxzugkraft.data,
            spurweite=form.spurweite.data,
            istfrei=None
        )
        db.session.add(neuer_wagen)
        db.session.commit()
        flash("Triebwagen erfolgreich hinzugefügt.")
        return redirect(url_for('dashboard_admin'))

    return render_template('hinzufuegen_triebwagen.html',title='Neuen Triebwagen hinzufügen',form=form)

@app.route('/triebwagen_action', methods=['POST'])
@login_required
def triebwagen_action():
    wagen_id = request.form.get("selected_wagen")
    action = request.form.get("action")

    if not wagen_id:
        flash("Bitte wählen Sie einen Triebwagen aus.")
        return redirect(url_for('uebers_triebwagen'))

    tw = db.session.get(Triebwagen, wagen_id)

    if not tw:
        flash("Triebwagen nicht gefunden.")
        return redirect(url_for('uebers_triebwagen'))

# Triebwagen kann nicht gelöscht werden, wenn er einem Zug zugeordnet ist
    if action == "loeschen":
        if tw.istfrei is not None:
            flash("Wagen ist in einem Zug und kann nicht gelöscht werden!")
            return redirect(url_for('uebers_triebwagen'))

        db.session.delete(tw)
        db.session.commit()
        flash("Triebwagen erfolgreich gelöscht.")
        return redirect(url_for('dashboard_admin'))

    if action == "bearbeiten":
        return redirect(url_for('bearbeite_triebwagen', wagen_id=tw.wagenid))

    return redirect(url_for('dashboard_admin'))

@app.route('/bearbeite_triebwagen/<int:wagen_id>', methods=['GET', 'POST'])
@login_required
def bearbeite_triebwagen(wagen_id):

    tw = db.session.get(Triebwagen, wagen_id)

    if not tw:
        flash("Triebwagen wurde nicht gefunden.")
        return redirect(url_for('uebers_triebwagen'))

    form = TriebwagenForm(obj=tw)  # vorbefüllen!

    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_triebwagen'))

    if form.validate_on_submit():
        # Spurweite darf nicht geändert werden, wenn der Wagen in einem Zug ist
        if tw.istfrei is not None and tw.spurweite != form.spurweite.data:
            flash("Spurweite darf nicht geändert werden, wenn der Wagen in einem Zug ist!")
            return redirect(url_for('bearbeite_triebwagen', wagen_id=wagen_id))
        # Maximale Zugkraft darf nicht geändert werden, wenn der Wagen in einem Zug ist
        if tw.istfrei is not None and tw.maxzugkraft != form.maxzugkraft.data:
            flash("Maximale Zugkraft darf nicht geändert werden, wenn der Wagen in einem Zug ist!")
            return redirect(url_for('bearbeite_triebwagen', wagen_id=wagen_id))

        tw.maxzugkraft = form.maxzugkraft.data
        tw.spurweite  = form.spurweite.data

        db.session.commit()
        flash("Triebwagen erfolgreich bearbeitet.")
        return redirect(url_for('dashboard_admin'))

    return render_template("bearbeiten_triebwagen.html", form=form, wagen=tw)

@app.route('/uebers_zuege')
@login_required
def uebers_zuege():
    # get('q', '')  - falls "q" vorhanden → Wert nehmen - sonst leerer String
    # strip() entfernt Leerzeichen am Anfang/Ende.
    suchbegriff = request.args.get('q', '').strip()

    query = db.select(Zuege).order_by(Zuege.zugid)

    if suchbegriff:
        query = query.where(
            Zuege.bezeichnung.like(f"%{suchbegriff}%")
        )

    zuege_liste = db.session.execute(query).scalars().all()

    return render_template('uebers_zuege.html', title='Züge-Übersicht', zuege_liste=zuege_liste)

@app.route('/hinzufuegen_zuege', methods=['GET', 'POST'])
@login_required
def hinzufuegen_zuege():
    form = ZuegeForm()
    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_zuege'))

    suche_tw = request.args.get("search_tw", "").strip()
    suche_pw = request.args.get("search_pw", "").strip()

    # Query für freie Triebwagen (istfrei == None)
    query_tw = db.select(Triebwagen).where(Triebwagen.istfrei == None).order_by(Triebwagen.wagenid)
    if suche_tw:
        query_tw = query_tw.where(
            or_(
                Triebwagen.wagenid.cast(sa.String).like(f"%{suche_tw}%"),
                Triebwagen.maxzugkraft.cast(sa.String).like(f"%{suche_tw}%"),
                Triebwagen.spurweite.cast(sa.String).like(f"%{suche_tw}%")
            )
        )
    # Query für freie Personenwagen (istfrei == None)
    query_pw = db.select(Personenwagen).where(Personenwagen.istfrei == None).order_by(Personenwagen.wagenid)
    if suche_pw:
        query_pw = query_pw.where(
            or_(
                Personenwagen.wagenid.cast(sa.String).like(f"%{suche_pw}%"),
                Personenwagen.kapazitaet.cast(sa.String).like(f"%{suche_pw}%"),
                Personenwagen.spurweite.cast(sa.String).like(f"%{suche_pw}%")
            )
        )
    # Ausführen der Queries
    freie_triebwagen = db.session.execute(query_tw).scalars().all()
    freie_personenwagen = db.session.execute(query_pw).scalars().all()

    # Prüfung ob Speicherbutton gedrückt wurde
    if form.validate_on_submit() and "speichern" in request.form:

        # Ausgewählte Trieb- und Personenwagen IDs holen
        tw_id = request.form.get("triebwagen_id")  # Radio button (ein Wert)
        pw_ids = request.form.getlist("personenwagen_ids")  # Checkboxen (Liste von Werten)

        # Prüfung ob ein Triebwagen und mindestens ein Personenwagen ausgewählt wurde
        if not tw_id:
            flash("Bitte wählen Sie einen Triebwagen aus!")
        elif not pw_ids:
            flash("Bitte wählen Sie mindestens einen Personenwagen aus!")
        else:
            # Trieb- und Personenwagen aus der Datenbank holen
            selected_tw = db.session.get(Triebwagen, tw_id)
            selected_pws = [db.session.get(Personenwagen, pid) for pid in pw_ids]

            # Logische Prüfungen
            valid = True  # Flag, ob alles okay ist

            # Spurweite
            target_spur = selected_tw.spurweite
            for pw in selected_pws:
                if pw.spurweite != target_spur:
                    flash(f"Fehler: Spurweite stimmt nicht überein! Triebwagen hat {target_spur}, Personenwagen {pw.wagenid} hat {pw.spurweite}!")
                    valid = False
                    break  # Abbrechen

            # Zugkraft > Summe von maximalem Gewicht aller Personenwagen
            if valid:
                 total_gewicht = sum(pw.maxgewicht for pw in selected_pws)
            if selected_tw.maxzugkraft < total_gewicht:
                    flash(f"Fehler: Zu schwer! Triebwagen schafft {selected_tw.maxzugkraft}t, aber Wagen wiegen zusammen {total_gewicht}t.")
                    valid = False

            #Speichern (nur wenn valid)
            if valid:
                # Zug erstellen
                neuer_zug = Zuege(bezeichnung=form.bezeichnung.data, inwartung=False)
                db.session.add(neuer_zug)
                db.session.flush()
                # flush() generiert die ID für neuer_zug (ohne die Transaktoin zu beenden) - brauche ich damit diese direkt den ausgewählten Wagen zugewiesen wird

                # Wagen (Trieb- und Personenwagen) dem Zug zuweisen - Update Foreign Key
                selected_tw.istfrei = neuer_zug.zugid
                for pw in selected_pws:
                    pw.istfrei = neuer_zug.zugid

                db.session.commit()
                flash(f"Zug '{neuer_zug.bezeichnung}' erfolgreich erstellt!")
                return redirect(url_for("dashboard_admin"))

    return render_template("hinzufuegen_zuege.html", freie_triebwagen=freie_triebwagen, freie_personenwagen=freie_personenwagen, form=form)

@app.route('/zuege_action', methods=['POST'])
@login_required
def zuege_action():

    return redirect(url_for('dashboard_admin'))

@app.route('/uebers_wartungen')
@login_required
def uebers_wartungen():
    return render_template('uebers_wartungen.html', title='Wartungen-Übersicht')

@app.route('/uebers_mitarbeiter')
@login_required
def uebers_mitarbeiter():
    return render_template('uebers_mitarbeiter.html', title='Mitarbeiter-Übersicht')

#############################################################
#####################    API    #############################
#############################################################

# Alle Züge auflisten - nach spurweite oder in Wartung filtern
@app.route('/zuege', methods=['GET'])
def get_zuege_api():

    query_term = request.args.get('q', default='', type=str)

    stmt = sa.select(Zuege)

    if query_term:
        stmt = stmt.join(Zuege.wagen).where(
            sa.or_(
                sa.cast(Zuege.inwartung, sa.String).ilike(f"%{query_term}%"),
                sa.cast(Wagen.spurweite, sa.String).like(f"%{query_term}%")
            )
        )
    zuege_result = db.session.execute(stmt).unique().scalars().all()

    items = []
    for zug in zuege_result:
        spurweite = 0
        tw_id = zug.triebwagen_id
        if tw_id:
            tw = db.session.get(Triebwagen, tw_id)
            if tw:
                spurweite = tw.spurweite

        items.append({
            "zugId": str(zug.zugid),
            "bezeichnung": zug.bezeichnung,
            "inWartung": zug.inwartung,
            "spurweite": spurweite
        })
    return jsonify(items)

# Zuge mit bestimmter id abfragen
@app.route('/zug/<int:zug_id>', methods=['GET'])
def get_zug_api(zug_id):

    zug = db.session.get(Zuege, zug_id)
    if not zug:
        return jsonify({"error": "Zug nicht gefunden"})

    spurweite = 0
    tw = db.session.get(Triebwagen, zug.triebwagen_id)
    if tw:
        spurweite = tw.spurweite

    item = {
        "zugId": str(zug.zugid),
        "bezeichnung": zug.bezeichnung,
        "inWartung": zug.inwartung,
        "spurweite": spurweite
    }
    return jsonify(item)

# Detaillierte Wagenbeschreibung eines bestimmten Zuges mit Zugid abfragen
@app.route('/flotte/kapazitaet/<int:zug_id>', methods=['GET'])
def get_zug_wagen_api(zug_id):

    zug = db.session.get(Zuege, zug_id)
    if not zug:
        return jsonify({"error": "Zug nicht gefunden"})

    zug_spurweite = 0
    triebwagen_info = None
    tw = db.session.get(Triebwagen, zug.triebwagen_id)

    if tw:
        zug_spurweite = tw.spurweite
        triebwagen_info = {
            "wagenNr": str(tw.wagenid),
            "spurweite": tw.spurweite,
            "maxZugkraft": tw.maxzugkraft
        }

    wagen_liste = []
    for wagen in zug.wagen:
        if wagen.type == 'personenwagen':
            pw = db.session.get(Personenwagen, wagen.wagenid)
            if pw:
                wagen_liste.append({
                    "wagenNr": str(pw.wagenid),
                    "spurweite": pw.spurweite,
                    "maximalgewicht": pw.maxgewicht,
                    "kapazitaet": pw.kapazitaet
                })
    items = {
        "zugNr": str(zug.zugid),
        "zugBezeichnung": zug.bezeichnung,
        "spurweite": zug_spurweite,
        "triebwagen": triebwagen_info,
        "personenwagen": wagen_liste
    }
    return jsonify(items)