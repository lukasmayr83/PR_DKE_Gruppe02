from flask import render_template, flash, redirect, url_for, request, jsonify
from urllib.parse import urlsplit
from app import app,db
from app.forms import LoginForm, PersonenwagenForm, TriebwagenForm, ZuegeForm, MitarbeiterAddForm, MitarbeiterEditForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Role, Personenwagen, Triebwagen, Zuege, Wagen, Mitarbeiter
from sqlalchemy import or_
from app.zug_validation import validate_zug
from app.mitarbeiter_validation import validate_unique_svnr, validate_unique_username
import app.suchhelfer as suchhelfer

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

@app.route('/personenwagen_mitarbeiter')
@login_required
def personenwagen_mitarbeiter():
    personenwagen_liste = suchhelfer.search_personenwagen(request)
    return render_template('personenwagen_mitarbeiter.html', title='Personenwagen Übersicht',personenwagen_liste=personenwagen_liste)

@app.route('/triebwagen_mitarbeiter')
@login_required
def triebwagen_mitarbeiter():
    triebwagen_liste = suchhelfer.search_triebwagen(request)
    return render_template('triebwagen_mitarbeiter.html', title='Triebwagen Übersicht', triebwagen_liste=triebwagen_liste)

@app.route('/zuege_mitarbeiter')
@login_required
def zuege_mitarbeiter():
    zuege_liste = suchhelfer.search_zuege(request)
    return render_template('zuege_mitarbeiter.html', title='Züge Übersicht', zuege_liste=zuege_liste)

@app.route('/wartungen_mitarbeiter')
@login_required
def wartungen_mitarbeiter():
    return render_template('wartungen_mitarbeiter.html', title='Wartungen Übersicht')

@app.route('/uebers_personenwagen')
@login_required
def uebers_personenwagen():
    personenwagen_liste = suchhelfer.search_personenwagen(request)
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
        triebwagen_liste = suchhelfer.search_triebwagen(request)
        return render_template('uebers_triebwagen.html', title='Triebwagen-Übersicht',triebwagen_liste=triebwagen_liste)

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

    return render_template("bearbeiten_triebwagen.html",title="Triebwagen bearbeiten", form=form, wagen=tw)

@app.route('/uebers_zuege')
@login_required
def uebers_zuege():
    zuege_liste = suchhelfer.search_zuege(request)
    return render_template('uebers_zuege.html', title='Züge-Übersicht', zuege_liste=zuege_liste)

@app.route('/hinzufuegen_zuege', methods=['GET', 'POST'])
@login_required
def hinzufuegen_zuege():
    form = ZuegeForm()
    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_zuege'))

    freie_triebwagen =suchhelfer.search_freie_triebwagen(request)
    freie_personenwagen =suchhelfer.search_freie_personenwagen(request)

    # Prüfung ob Speicherbutton gedrückt wurde
    if form.validate_on_submit() and "speichern" in request.form:
        valid,tw,pws,msg = validate_zug(request.form)
        if not valid:
            flash(msg)
        else:
                # Zug erstellen
                neuer_zug = Zuege(bezeichnung=form.bezeichnung.data, inwartung=False)
                db.session.add(neuer_zug)
                db.session.flush()
                # flush() generiert die ID für neuer_zug (ohne die Transaktoin zu beenden) - brauche ich damit diese direkt den ausgewählten Wagen zugewiesen wird

                # Wagen (Trieb- und Personenwagen) dem Zug zuweisen - Update Foreign Key
                tw.istfrei = neuer_zug.zugid
                for pw in pws:
                    pw.istfrei = neuer_zug.zugid

                db.session.commit()
                flash(f"Zug '{neuer_zug.bezeichnung}' erfolgreich erstellt!")
                return redirect(url_for("dashboard_admin"))

    return render_template("hinzufuegen_zuege.html",title="Züge hinzufügen" ,freie_triebwagen=freie_triebwagen, freie_personenwagen=freie_personenwagen, form=form)

@app.route('/zuege_action', methods=['POST'])
@login_required
def zuege_action():
        zug_id = request.form.get("selected_zug")
        action = request.form.get("action")

        if not zug_id:
            flash("Bitte wählen Sie einen Zug aus!")
            return redirect(url_for('uebers_zuege'))

        zug = db.session.get(Zuege, zug_id)

        if action == "loeschen":
            for w in zug.wagen:
                w.istfrei = None
            db.session.delete(zug)
            db.session.commit()
            flash("Zug erfolgreich gelöscht.")
            return redirect(url_for('dashboard_admin'))

        if action == "bearbeiten":
            return redirect(url_for('bearbeite_zuege', zug_id=zug.zugid))

        return redirect(url_for('dashboard_admin'))

@app.route('/bearbeite_zuege/<int:zug_id>', methods=['GET', 'POST'])
@login_required
def bearbeite_zuege(zug_id):
    zug = db.session.get(Zuege, zug_id)
    form = ZuegeForm(obj=zug)  # vorbefüllen!
    if request.method == "POST" and request.form.get("action") == "abbrechen" :
        return redirect(url_for('uebers_zuege'))

    verfuegbare_triebwagen = suchhelfer.search_triebwagen_for_zug_bearbeiten(request,zug_id)
    verfuegbare_personenwagen = suchhelfer.search_personenwagen_for_zug_bearbeiten(request, zug_id)
    # SPEICHERN
    if form.validate_on_submit() and "speichern" in request.form:
        valid, tw, pws, msg = validate_zug(request.form)
        if not valid:
            flash(msg)
        else:
                # ALLE Wagen dieses Zuges freigeben
                for old_w in zug.wagen:
                    old_w.istfrei = None

                zug.bezeichnung = form.bezeichnung.data
                tw.istfrei = zug.zugid  # Triebwagen zuweisen

                # Personenwagen zuweisen
                for pw in pws:
                    pw.istfrei = zug.zugid

                db.session.commit()
                flash(f"Zug {zug.bezeichnung} erfolgreich aktualisiert.", "success")
                return redirect(url_for('dashboard_admin'))

    aktueller_tw_id = zug.triebwagen_id
    # Alle IDs der Personenwagen die aktuell diesem Zug zugeordnet sind
    aktuelle_pw_ids = [w.wagenid for w in zug.wagen if w.type == 'personenwagen']

    return render_template("bearbeiten_zuege.html", title="Züge bearbeiten ",form=form,zug=zug,freie_triebwagen=verfuegbare_triebwagen,
                           freie_personenwagen=verfuegbare_personenwagen,aktueller_tw_id=aktueller_tw_id,aktuelle_pw_ids=aktuelle_pw_ids)

@app.route('/uebers_mitarbeiter')
@login_required
def uebers_mitarbeiter():
        mitarbeiter_liste = suchhelfer.search_mitarbeiter(request)
        return render_template('uebers_mitarbeiter.html', title='Mitarbeiter-Übersicht', mitarbeiter_liste=mitarbeiter_liste)

@app.route('/hinzufuegen_mitarbeiter', methods=['GET', 'POST'])
@login_required
def hinzufuegen_mitarbeiter():
    form = MitarbeiterAddForm()

    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_mitarbeiter'))

    if form.validate_on_submit():
        svnr_ok, msg = validate_unique_svnr(form.svnr.data)
        if not svnr_ok:
            flash(msg)
            return render_template("hinzufuegen_mitarbeiter.html",title='Mitarbeiter hinzufügen', form=form)

        benutzername_ok, msg = validate_unique_username(form.username.data)
        if not benutzername_ok:
            flash(msg)
            return render_template("hinzufuegen_mitarbeiter.html",title='Mitarbeiter hinzufügen', form=form)
        user = User(username=form.username.data,role=Role.MITARBEITER)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # erzeugt user.id

        # 2) Mitarbeiter anlegen
        neuer_mitarbeiter = Mitarbeiter(
            vorname=form.vorname.data,
            nachname=form.nachname.data,
            svnr=form.svnr.data,
            user_id=user.id
        )
        db.session.add(neuer_mitarbeiter)
        db.session.commit()
        flash("Mitarbeiter erfolgreich hinzugefügt.")
        return redirect(url_for('dashboard_admin'))

    return render_template('hinzufuegen_mitarbeiter.html',title='Mitarbeiter hinzufügen',form=form)

@app.route('/mitarbeiter_action', methods=['POST'])
@login_required
def mitarbeiter_action():
    svnr = request.form.get("selected_mitarbeiter")
    action = request.form.get("action")

    if not svnr:
        flash("Bitte wählen Sie einen Mitarbeiter aus!")
        return redirect(url_for('uebers_mitarbeiter'))

    mitarbeiter = db.session.get(Mitarbeiter, svnr)

    if action == "loeschen":
        user_to_delete =mitarbeiter.user
        db.session.delete(mitarbeiter)
        if user_to_delete:
            db.session.delete(user_to_delete)
        db.session.commit()
        flash("Mitarbeiter Daten erfolgreich gelöscht.")
        return redirect(url_for('dashboard_admin'))

    if action == "bearbeiten":
        return redirect(url_for('bearbeite_mitarbeiter', svnr=mitarbeiter.svnr))

    return redirect(url_for('dashboard_admin'))

@app.route('/bearbeite_mitarbeiter/<int:svnr>', methods=['GET', 'POST'])
@login_required
def bearbeite_mitarbeiter(svnr):
    mitarbeiter = db.session.get(Mitarbeiter, svnr)
    form = MitarbeiterEditForm(obj=mitarbeiter) # vorbefüllen von Mitarbeiter Daten!
    if request.method == 'GET':
        form.username.data = mitarbeiter.user.username

    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_mitarbeiter'))

    if form.validate_on_submit():
        svnr_ok, msg = validate_unique_svnr(form.svnr.data, current_svnr=mitarbeiter.svnr)
        if not svnr_ok:
            flash(msg)
            return render_template("bearbeiten_mitarbeiter.html",title="Mitarbeiter Daten bearbeiten", form=form, mitarbeiter=mitarbeiter)

        benutzername_ok, msg = validate_unique_username(form.username.data, current_user_id=mitarbeiter.user.id)
        if not benutzername_ok:
            flash(msg)
            return render_template("bearbeiten_mitarbeiter.html",title="Mitarbeiter Daten bearbeiten", form=form, mitarbeiter=mitarbeiter)

        mitarbeiter.svnr = form.svnr.data
        mitarbeiter.vorname = form.vorname.data
        mitarbeiter.nachname = form.nachname.data
        mitarbeiter.user.username = form.username.data
        mitarbeiter.user.set_password(form.password.data)
        if form.password.data:
            mitarbeiter.user.set_password(form.password.data)
            flash("Mitarbeiterdaten und Passwort bearbeitet.")
        else:
            flash("Mitarbeiterdaten bearbeitet.")
        db.session.commit()
        return redirect(url_for('dashboard_admin'))

    return render_template("bearbeiten_mitarbeiter.html", title="Mitarbeiter Daten bearbeiten", form=form, mitarbeiter=mitarbeiter)

@app.route('/uebers_wartungen')
@login_required
def uebers_wartungen():
    return render_template('uebers_wartungen.html', title='Wartungen-Übersicht')

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