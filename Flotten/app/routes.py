from flask import render_template, flash, redirect, url_for, request, jsonify, session
from urllib.parse import urlsplit
from app import app,db
from app.forms import LoginForm, PersonenwagenForm, TriebwagenForm, ZuegeForm, MitarbeiterAddForm, MitarbeiterEditForm,WartungszeitraumForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Role, Personenwagen, Triebwagen, Zuege, Wagen, Mitarbeiter, Wartungszeitraum,Wartung
from sqlalchemy import or_, not_
from app.zug_validation import validate_zug
from app.mitarbeiter_validation import validate_unique_svnr, validate_unique_username
import app.suchhelfer as suchhelfer
from datetime import date, datetime
import app.wartungszeitraum_validation as wartungszeitraum_validation

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
    svnr = current_user.mitarbeiter.svnr
    nur_aktuelle = request.args.get("nur_aktuelle", 'false') == 'true'
    wartungszeitraum_liste = suchhelfer.search_wartungen(request, nur_aktuelle, svnr=svnr)
    return render_template('wartungen_mitarbeiter.html', title='Wartungen-Übersicht',wartungszeitraum_liste=wartungszeitraum_liste, nur_aktuelle=nur_aktuelle)

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

    freie_triebwagen = suchhelfer.search_freie_triebwagen(request)
    freie_personenwagen = suchhelfer.search_freie_personenwagen(request)

    # Prüfung ob Speicherbutton gedrückt wurde
    if form.validate_on_submit() and "speichern" in request.form:
        valid,tw,pws,msg = validate_zug(request.form)
        if not valid:
            flash(msg)
        else:
                # Zug erstellen
                neuer_zug = Zuege(bezeichnung=form.bezeichnung.data)
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

@app.route('/uebers_wartungszeitraum')
@login_required
def uebers_wartungszeitraum():
    nur_aktuelle = request.args.get("nur_aktuelle", 'false') == 'true'
    wartungszeitraum_liste = suchhelfer.search_wartungen(request, nur_aktuelle)
    return render_template('uebers_wartungszeitraum.html', title='Wartungen-Übersicht', wartungszeitraum_liste=wartungszeitraum_liste,nur_aktuelle=nur_aktuelle)

@app.route('/hinzufuegen_wartungszeitraum', methods=['GET', 'POST'])
@login_required
def hinzufuegen_wartungszeitraum():
    form = WartungszeitraumForm()
    # Alle Mitarbeiter holen
    mitarbeiter_liste = db.session.execute(db.select(Mitarbeiter).order_by(Mitarbeiter.vorname)).scalars().all()

    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_wartungszeitraum'))

    if request.method == "POST" and "verfuegbarkeit" in request.form:

        if not wartungszeitraum_validation.validate_zug_datum_von_bis(form):
            return render_template("hinzufuegen_wartungszeitraum.html",title="Wartung Hinzufügen",form=form,mitarbeiter_liste=[],verfuegbarkeit_geprueft=False)

        mitarbeiter_liste= wartungszeitraum_validation.get_verfuegbare_mitarbeiter(form.datum.data, form.von.data, form.bis.data)
        flash("Verfügbarkeit geprüft - Bitte Mitarbeiter auswählen!", 'success')
        return render_template("hinzufuegen_wartungszeitraum.html",title="Wartung Hinzufügen",form=form,mitarbeiter_liste=mitarbeiter_liste,verfuegbarkeit_geprueft=True)

    if form.validate_on_submit():
        if not wartungszeitraum_validation.validate_all(form, request):
            return render_template("hinzufuegen_wartungszeitraum.html",title="Wartung Hinzufügen",form=form,mitarbeiter_liste=mitarbeiter_liste,verfuegbarkeit_geprueft=False)

        verfuegbare_mitarbeiter = wartungszeitraum_validation.get_verfuegbare_mitarbeiter(form.datum.data, form.von.data, form.bis.data)
        # Holte alle Mitarbeiter aus verfuegbare_mitarbeiter und baut eine Set m.svnr
        verfuegbare_svnr = {m.svnr for m in verfuegbare_mitarbeiter}

        # Prüfen, ob ALLE ausgewählten Mitarbeiter verfügbar sind
        svnr_liste = request.form.getlist("mitarbeiter_svnr")
        # Erstellt Liste aller svnr aus svnr_liste die nicht in verfuegbare_svnr vorkommen
        nicht_verfuegbar = [sv for sv in svnr_liste if int(sv) not in verfuegbare_svnr]

        if nicht_verfuegbar:
            flash("Manche ausgewählte Mitarbeiter sind zu dieser Zeit nicht verfügbar!")

            # Mitarbeiterliste aktualisieren & Auswahl zurücksetzen
            return render_template("hinzufuegen_wartungszeitraum.html",title="Wartung Hinzufügen",form=form,mitarbeiter_liste=verfuegbare_mitarbeiter,verfuegbarkeit_geprueft=True)

        svnr_liste = request.form.getlist("mitarbeiter_svnr")

        # von und bis mit Datum versehen, da sonst der Datentyp probleme macht
        von_datetime = datetime.combine(form.datum.data, form.von.data)
        bis_datetime = datetime.combine(form.datum.data, form.bis.data)

        # Wartungszeitraum anlegen
        neuer_wartungszeitraum = Wartungszeitraum(
            datum=form.datum.data,
            von=von_datetime,
            bis=bis_datetime,
            dauer=int((bis_datetime - von_datetime).total_seconds() / 60)
        )
        db.session.add(neuer_wartungszeitraum)
        db.session.flush()  # Wartungszeitid erstellen ohne Transaktion abzubrechen
        # Wartung erstellen
        for svnr in svnr_liste:
            wartung = Wartung(
                wartungszeitid=neuer_wartungszeitraum.wartungszeitid,
                svnr=svnr,
                zugid=form.zugid.data
            )
            db.session.add(wartung)

        db.session.commit()
        flash("Wartungszeitraum erfolgreich hinzugefügt.")
        return redirect(url_for('dashboard_admin'))

    return render_template("hinzufuegen_wartungszeitraum.html",title="Wartung Hinzufügen",form=form,mitarbeiter_liste=mitarbeiter_liste, verfuegbarkeit_geprueft=False)

@app.route('/wartungen_action', methods=['POST'])
@login_required
def wartungszeitraum_action():
    # Werte aus dem Formular
    wartungszeitid = request.form.get("selected_wartungszeitraum")
    action = request.form.get("action")

    if not wartungszeitid:
        flash("Bitte wählen Sie einen Wartungszeitraum aus!")
        return redirect(url_for('uebers_wartungszeitraum'))

    wartungszeitraum = db.session.get(Wartungszeitraum, wartungszeitid)
    now = datetime.now()
    laufend = wartungszeitraum.von <= now <= wartungszeitraum.bis
    abgeschlossen = now >= wartungszeitraum.von
    # Aktion: Löschen
    if action == "loeschen":
        if laufend:
            flash("Dise Wartung läuft gerade und kann daher nicht gelöscht werden!")
            return redirect(url_for('uebers_wartungszeitraum'))
        # Alle zugehörigen Wartung-Einträge holen und löschen
        wartungen = db.session.query(Wartung).filter_by(wartungszeitid=wartungszeitid).all()
        for w in wartungen:
            db.session.delete(w)

        db.session.delete(wartungszeitraum)
        db.session.commit()
        flash("Wartungszeitraum und zugehörige Wartungen erfolgreich gelöscht.",'success')
        return redirect(url_for('uebers_wartungszeitraum'))

    if action == "bearbeiten":
        if laufend:
            flash("Diese Wartung läuft gerade und kann daher nicht bearbeitet werden!")
            return redirect(url_for('uebers_wartungszeitraum'))
        if abgeschlossen:
            flash("Dieser Wartungszeitraum liegt in der Vergangenheit und kann daher nicht bearbeitet werden!")
            return redirect(url_for('uebers_wartungszeitraum'))
        return redirect(url_for('bearbeite_wartungszeitraum', wartungszeitid=wartungszeitid))

    return redirect(url_for('uebers_wartungszeitraum'))

@app.route('/bearbeite_wartungszeitraum/<int:wartungszeitid>', methods=['GET', 'POST'])
@login_required
def bearbeite_wartungszeitraum(wartungszeitid):
    wartungszeitraum = db.session.get(Wartungszeitraum, wartungszeitid )

    form = WartungszeitraumForm(
        zugid=wartungszeitraum.wartungen[0].zugid if wartungszeitraum.wartungen else None,
        datum=wartungszeitraum.datum,
        von=wartungszeitraum.von.time(),
        bis=wartungszeitraum.bis.time()
    )
    # Aktuell zugewiesene Mitarbeiter
    ausgewaehlte_ma_svnr = {w.svnr for w in wartungszeitraum.wartungen}

    # Alle Mitarbeiter anzeigen (noch nicht geprüft)
    mitarbeiter_liste = db.session.execute(
        db.select(Mitarbeiter).order_by(Mitarbeiter.vorname)
    ).scalars().all()

    if request.method == "POST" and "abbrechen" in request.form:
        return redirect(url_for('uebers_wartungszeitraum'))

    if request.method == "POST" and "verfuegbarkeit" in request.form:

        if not wartungszeitraum_validation.validate_zug_datum_von_bis(form):
            return render_template("bearbeiten_wartungszeitraum.html",title="Wartung Bearbeiten",form=form,mitarbeiter_liste=[],ausgewaehlte_ma_svnr=[],verfuegbarkeit_geprueft=False)

        # Liste frisch generieren
        verfuegbare_mitarbeiter = wartungszeitraum_validation.get_verfuegbare_mitarbeiter(
            form.datum.data, form.von.data, form.bis.data, ignore_wzid=wartungszeitraum.wartungszeitid
        )
        # Holte alle Mitarbeiter aus verfuegbare_mitarbeiter und baut eine Set m.svnr
        verfuegbare_svnr = {m.svnr for m in verfuegbare_mitarbeiter}

        # Erstellt eine neue Mitarbeiterliste, die aus allen verfügbaren Mitarbeitern besteht + allen die bereits ausgewählt waren
        mitarbeiter_liste = ([m for m in verfuegbare_mitarbeiter] +
                             [m for m in mitarbeiter_liste if m.svnr in ausgewaehlte_ma_svnr and m.svnr not in verfuegbare_svnr])

        #  Doppelte entfernen
        seen = set() # erstellt leeres Set
        mitarbeiter_liste = [m for m in mitarbeiter_liste if not (m.svnr in seen or seen.add(m.svnr))]

        flash("Verfügbarkeit geprüft – bitte Mitarbeiter auswählen!", "success")
        return render_template("bearbeiten_wartungszeitraum.html",title="Wartung Bearbeiten",form=form,mitarbeiter_liste=mitarbeiter_liste,ausgewaehlte_ma_svnr=ausgewaehlte_ma_svnr,verfuegbarkeit_geprueft=True)

    if form.validate_on_submit() and "speichern" in request.form:

        if not wartungszeitraum_validation.validate_all(form, request):
            return render_template("bearbeiten_wartungszeitraum.html",title="Wartung Bearbeiten",form=form,mitarbeiter_liste=mitarbeiter_liste,ausgewaehlte_ma_svnr=ausgewaehlte_ma_svnr,verfuegbarkeit_geprueft=False)

        verfuegbare_mitarbeiter = wartungszeitraum_validation.get_verfuegbare_mitarbeiter(
            form.datum.data, form.von.data, form.bis.data,ignore_wzid=wartungszeitraum.wartungszeitid
        )

        verfuegbare_svnr = {m.svnr for m in verfuegbare_mitarbeiter}

        svnr_liste = request.form.getlist("mitarbeiter_svnr")
        # Erstellt Liste aller svnr aus svnr_liste die nicht in verfuegbare_svnr vorkommen
        nicht_verfuegbar = [sv for sv in svnr_liste if int(sv) not in verfuegbare_svnr]

        if nicht_verfuegbar:
            flash("Einige ausgewählte Mitarbeiter sind nicht verfügbar!", "error")
            return render_template("bearbeiten_wartungszeitraum.html",title="Wartung Bearbeiten",form=form,mitarbeiter_liste=verfuegbare_mitarbeiter,ausgewaehlte_ma_svnr=set(),verfuegbarkeit_geprueft=True)

        # von und bis mit Datum versehen, da sonst der Datentyp probleme macht
        von_dt = datetime.combine(form.datum.data, form.von.data)
        bis_dt = datetime.combine(form.datum.data, form.bis.data)

        wartungszeitraum.datum = form.datum.data
        wartungszeitraum.von = von_dt
        wartungszeitraum.bis = bis_dt
        wartungszeitraum.dauer = int((bis_dt - von_dt).total_seconds() / 60)

        # WARTUNGEN AKTUALISIEREN
        # Alle bestehenden Wartungs-Einträge zu diesem Wartungszeitraum löschen / alte Mitarbeiter zuweisungen entfernen
        for w in wartungszeitraum.wartungen:
            db.session.delete(w)

        # Mitarbeiter - Zugid - Wartungszeitid aktualliserien / anlegen
        for sv in svnr_liste:
            db.session.add(Wartung(
                wartungszeitid=wartungszeitraum.wartungszeitid,
                svnr=sv,
                zugid=form.zugid.data
            ))

        db.session.commit()
        flash("Wartungszeitraum erfolgreich aktualisiert.")
        return redirect(url_for('dashboard_admin'))

    return render_template("bearbeiten_wartungszeitraum.html",title="Wartung Bearbeiten",form=form,mitarbeiter_liste=mitarbeiter_liste,ausgewaehlte_ma_svnr=ausgewaehlte_ma_svnr,verfuegbarkeit_geprueft=False )

#############################################################
#####################    API    #############################
#############################################################

# Hilfsfunktion für die API um die Wartungen darzustellen
def get_wartungszeit_details_for_zug(zug, wartungszeitid):

    wartungszeitid_int = int(wartungszeitid)
    wz = db.session.get(Wartungszeitraum, wartungszeitid_int)
    if not wz:
        return None

    # Suche alle Wartung-Einträge für diesen Zug und diese Wartungszeit
    wartungen_for_this = [w for w in zug.wartungen if w.wartungszeitid == wartungszeitid_int]

    mitarbeiter_list = []
    seen_svnr = set()
    for w in wartungen_for_this:
        m = w.mitarbeiter
        if m and m.svnr not in seen_svnr:
            seen_svnr.add(m.svnr)
            mitarbeiter_list.append({
                "svnr": m.svnr,
                "vorname": m.vorname,
                "nachname": m.nachname
            })

    # Format: datum als YYYY-MM-DD, von/bis nur als Uhrzeit
    datum_str = wz.datum.isoformat() if wz.datum else None
    von_str = wz.von.time().isoformat() if wz.von else None
    bis_str = wz.bis.time().isoformat() if wz.bis else None

    return {
        "wartungszeitid": str(wz.wartungszeitid),
        "datum": datum_str,
        "von": von_str,
        "bis": bis_str,
        "dauer": wz.dauer,
        "mitarbeiter": mitarbeiter_list
    }

# Alle Züge auflisten - nach spurweite oder in Wartung filtern
@app.route('/zuege', methods=['GET'])
def get_zuege_api():

    query_term = request.args.get('q', default='', type=str)
    filter_wartung = request.args.get('in_wartung', default=None, type=str)

    stmt = sa.select(Zuege)

    if query_term:
        stmt = stmt.join(Zuege.wagen).where(
            sa.or_(
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

        in_wartung_status = zug.aktuelle_wartungs_anzeige
        is_in_wartung = in_wartung_status != "FALSE"

    # Filter nach Wartungsstatus (optional)
        if filter_wartung is not None:
            if filter_wartung.lower() == 'true' and not is_in_wartung:
                continue
            if filter_wartung.lower() == 'false' and is_in_wartung:
                continue

        # Wenn in Wartung: lade Details
        wartungszeit_details = None
        if is_in_wartung:
            wartungszeit_details = get_wartungszeit_details_for_zug(zug, in_wartung_status)

        items.append({
            "zugId": str(zug.zugid),
            "bezeichnung": zug.bezeichnung,
            "inWartung": is_in_wartung,
            "wartungszeit": wartungszeit_details,
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

    in_wartung_status = zug.aktuelle_wartungs_anzeige
    is_in_wartung = in_wartung_status != "FALSE"

    # Wenn in Wartung: lade Details
    wartungszeit_details = None
    if is_in_wartung:
        wartungszeit_details = get_wartungszeit_details_for_zug(zug, in_wartung_status)

    item = {
        "zugId": str(zug.zugid),
        "bezeichnung": zug.bezeichnung,
        "inWartung": is_in_wartung,
        "wartungszeit": wartungszeit_details,
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