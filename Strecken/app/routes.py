from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request, jsonify
from app import app
from app.forms import LoginForm, RegistrationForm, BahnhofForm, AbschnittForm, WarnungForm
from flask_login import current_user, login_user
import sqlalchemy as sa
from app import db
from app.models import User, Bahnhof, Abschnitt, Warnung
from flask_login import logout_user
from flask_login import login_required
import folium
from sqlalchemy.orm import selectinload

#############################################################
#################    Abschnitt   ############################
#############################################################

#Abschnitte anzeigen
@app.route('/abschnitt')
@login_required
def abschnitt():
    # Alle Abschnitte aus der DB laden
    posts = Abschnitt.query.all()

    return render_template(
        'abschnitt.html',
        title='Home',
        posts=posts,
        role=current_user.role
    )

#Abschnitte hinzufügen
@app.route('/abschnitt/add', methods=['GET', 'POST'])
@login_required
def abschnitt_add():
    form = AbschnittForm()

    #Lädt alle Bahnhöfe aus der DB
    bahnhoefe = Bahnhof.query.order_by(Bahnhof.name).all()
    #Füllt die Dropdowns StartBahnhof und Endbahnhof mit Bahnhöfen
    form.startBahnhof.choices = [(b.bahnhofId, b.name) for b in bahnhoefe]
    form.endBahnhof.choices   = [(b.bahnhofId, b.name) for b in bahnhoefe]

    #Wird ausgeführt, wenn Button Speichern gedruckt wurde
    if form.validate_on_submit():
        #Neue Instanz von Abschnitt mit den Werten des Formulars erstellen
        abschnitt = Abschnitt(
            startBahnhofId=form.startBahnhof.data,
            endBahnhofId=form.endBahnhof.data,
            max_geschwindigkeit=form.max_geschwindigkeit.data,
            spurweite=form.spurweite.data,
            nutzungsentgelt=form.nutzungsentgelt.data
        )

        #Abschnitt in DB hinzufügen und speichern
        db.session.add(abschnitt)
        db.session.commit()

        #Info über erfolgreiches Speichern
        flash(f'Abschnitt wurde gespeichert!', 'success')
        #Kommt wieder zurück zur Übersichtsseite der Abschnitte
        return redirect(url_for("abschnitt"))




    return render_template("abschnitt_add.html", form=form)


@app.route("/abschnitt/edit/<int:abschnitt_id>", methods=["GET", "POST"])
@login_required
def edit_abschnitt(abschnitt_id):
    abschnitt = db.session.get(Abschnitt, abschnitt_id)
    if not abschnitt:
        flash("Abschnitt nicht gefunden.", "error")
        return redirect(url_for("abschnitt"))


    form = AbschnittForm(
        obj=abschnitt,
        original_spurweite=abschnitt.spurweite,
        original_nutzungentgelt=abschnitt.nutzungsentgelt,
        original_max_geschwindigkeit=abschnitt.max_geschwindigkeit,
        original_startBahnhof=abschnitt.startBahnhof,
        original_endBahnhof=abschnitt.endBahnhof,
    )

    if form.validate_on_submit():
        form.populate_obj(abschnitt)
        abschnitt.spurweite=request.form.get("spurweite")
        abschnitt.nutzungsentgelt = request.form.get("nutzungsentgelt")
        abschnitt.max_geschwindigkeit = request.form.get("max_geschwindigkeit")
        abschnitt.startBahnhof = request.form.get("startBahnhof")
        abschnitt.endBahnhof = request.form.get("endBahnhof")
        db.session.commit()
        flash(f"Abschnitt '{abschnitt.name}' wurde aktualisiert.", "success")
        return redirect(url_for("abschnitt"))

    return render_template("abschnitt_edit.html", form=form, abschnitt=abschnitt)

@app.route("/abschnitt/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_abschnitt():
    ids = request.form.getlist("abschnitt_ids")
    deleted_count = 0

    if not ids:
        flash ("Keine Abschnitte ausgewählt.", "error")
        return redirect(url_for("abschnitt"))

    for aid in ids:
        try:

            abschnitt = db.session.get(Abschnitt, int(aid))
        except ValueError:

            continue

        if abschnitt:
            db.session.delete(abschnitt)
            deleted_count += 1


    if deleted_count > 0:
        db.session.commit()
        flash(f"{deleted_count} Abschnitt/Abschnitte erfolgreich gelöscht.", "success")
    else:

        flash("Kein Abschnitt konnte gelöscht werden.", "error")

    return redirect(url_for('abschnitt'))



#############################################################
#################    Strecke     ############################
#############################################################

@app.route('/', methods=['GET', 'POST'])
@app.route('/strecke', methods=['GET', 'POST'])
@login_required
def strecke():
    return render_template(
        'strecke.html',
        title='Home'
    )

@app.route("/strecke/add", methods=["GET", "POST"])
@login_required
def strecke_add():
    return render_template(
        'strecke_add.html',
    )

#############################################################
#################    Warnung     ############################
#############################################################

@app.route('/', methods=['GET', 'POST'])
@app.route('/warnung', methods=['GET', 'POST'])
@login_required
def warnung():
    #Alle Warnungen aus der DB laden
    posts = Warnung.query.all()

    return render_template(
        'warnung.html',
        posts=posts,
        role=current_user.role
    )

@app.route("/warnung/add", methods=["GET", "POST"])
@login_required
def warnung_add():
    form = WarnungForm()
    form.abschnitt.choices = [(a.abschnittId, a.name) for a in Abschnitt.query.all()]

    if form.validate_on_submit():

        # Neue Warnung erzeugen
        warnung = Warnung(
            bezeichnung=form.bezeichnung.data,
            beschreibung=form.beschreibung.data,
            startZeit=form.startZeit.data,
            endZeit=form.endZeit.data or None
        )

        db.session.add(warnung)
        db.session.commit()  # ID wird benötigt, bevor Beziehungen gesetzt werden

        # Ausgewählte Abschnitte laden
        gewaehlte_ids = form.abschnitt.data
        if not isinstance(gewaehlte_ids, list):
            gewaehlte_ids = [gewaehlte_ids]

        if gewaehlte_ids:
            abschnitte = Abschnitt.query.filter(
                Abschnitt.abschnittId.in_(gewaehlte_ids)
            ).all()

            warnung.abschnitte.clear()
            for abschnitt in abschnitte:
                warnung.abschnitte.append(abschnitt)

        db.session.commit()

        flash(f'Warnung "{warnung.bezeichnung}" wurde gespeichert!', 'success')
        return redirect(url_for("warnung"))

    return render_template("warnung_add.html", form=form)

@app.route("/warnung/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_warnung():
    ids = request.form.getlist("warnung_ids")

    deleted_count = 0

    if not ids:
        flash("Keine Warnungen ausgewählt.", "error")
        return redirect(url_for('warnung'))

    for bid in ids:
        try:

            warnung_query = (
                sa.select(Warnung)
                .where(Warnung.warnungId == int(bid))
            )
            warnung = db.session.execute(warnung_query).scalar_one_or_none()

            if warnung:
                db.session.delete(warnung)
                deleted_count += 1

        except Exception as e:
            print(f"Fehler beim Laden von Warnung {bid}: {e}")
            continue


    if deleted_count > 0:
        db.session.commit()
        flash(f"{deleted_count} Warnung/Warnungen erfolgreich gelöscht.", "success")


    return redirect(url_for('warnung'))

@app.route("/warnung/edit/<int:warnung_id>", methods=["GET", "POST"])
@login_required
def edit_warnung(warnung_id):
    return render_template("abschnitt_edit.html")
#############################################################
#################    Bahnhof     ############################
#############################################################

@app.route("/bahnhof/add", methods=["GET", "POST"])
@login_required
def bahnhof_add():
    form = BahnhofForm()
    if form.validate_on_submit():
        # Neuer Bahnhof wird erstellt
        bahnhof = Bahnhof(name=form.name.data, adresse=form.adresse.data)

        #Aus Adresse Koordinaten ermitteln
        bahnhof.geocode_address()

        #Bahnhöfe in DB speichern
        db.session.add(bahnhof)
        db.session.commit()

        flash(f'Bahnhof {bahnhof.name} wurde gespeichert!', 'success')
        return redirect(url_for("bahnhof"))
    return render_template("bahnhof_add.html", form=form)

@app.route('/', methods=['GET', 'POST'])
@app.route('/bahnhof', methods=['GET', 'POST'])
@login_required
def bahnhof():
    #Alle Bahnhöfe aus der DB laden
    posts = Bahnhof.query.all()

    #Wenn es Bahnhöfe gibt, wird eine Karte erstellt
    if posts:
        for b in posts:
            if not b.latitude or not b.longitude:
                b.geocode_address()
        db.session.commit()

        #Mittelpunkt berechnen
        center_lat = sum(b.latitude for b in posts) / len(posts)
        center_lon = sum(b.longitude for b in posts) / len(posts)

        #Folium-Karte erstellen
        m = folium.Map(location=[center_lat, center_lon], zoom_start=7)

        #Marker für jeden Bahnhof setzen
        for b in posts:
            folium.Marker(
                [b.latitude, b.longitude],
                tooltip=b.name,
                popup=f"{b.name}<br>{b.adresse}"
            ).add_to(m)

        #HTML-Code der Karte für das Template
        map_html = m._repr_html_()
    else:
        map_html = None

    return render_template(
        'bahnhof.html',
        title='Home',
        posts=posts,
        map_html=map_html,
        role=current_user.role
    )


@app.route("/bahnhof/edit/<int:bahnhof_id>", methods=["GET", "POST"])
@login_required
def edit_bahnhof(bahnhof_id):
    bahnhof = db.session.get(Bahnhof, bahnhof_id)
    if not bahnhof:
        flash("Bahnhof nicht gefunden.", "error")
        return redirect(url_for("bahnhof"))


    form = BahnhofForm(
        obj=bahnhof,
        original_name=bahnhof.name,
        original_adresse=bahnhof.adresse
    )

    if form.validate_on_submit():
        form.populate_obj(bahnhof)
        bahnhof.latitude = request.form.get("latitude")
        bahnhof.longitude = request.form.get("longitude")
        db.session.commit()
        flash(f"Bahnhof '{bahnhof.name}' wurde aktualisiert.", "success")
        return redirect(url_for("bahnhof"))

    return render_template("bahnhof_edit.html", form=form, bahnhof=bahnhof)


@app.route("/bahnhof/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_bahnhof():
    ids = request.form.getlist("bahnhof_ids")

    deleted_count = 0
    blocked_names = []

    if not ids:
        flash("Keine Bahnhöfe ausgewählt.", "error")
        return redirect(url_for('bahnhof'))

    for bid in ids:
        try:

            bahnhof_query = (
                sa.select(Bahnhof)
                .where(Bahnhof.bahnhofId == int(bid))
                .options(
                    selectinload(Bahnhof.start_abschnitte),
                    selectinload(Bahnhof.end_abschnitte)
                )
            )
            bahnhof = db.session.execute(bahnhof_query).scalar_one_or_none()

        except Exception as e:
            print(f"Fehler beim Laden von Bahnhof {bid}: {e}")
            continue

        if bahnhof:
            if bahnhof.start_abschnitte or bahnhof.end_abschnitte:
                blocked_names.append(bahnhof.name)
            else:
                db.session.delete(bahnhof)
                deleted_count += 1



    if deleted_count > 0:
        db.session.commit()
        flash(f"{deleted_count} Bahnhof/Bahnhöfe erfolgreich gelöscht.", "success")


    if blocked_names:
        names_str = ", ".join(blocked_names)
        flash(
            f"Folgende Bahnhöfe: [{names_str}] konnten nicht gelöscht werden, da sie in Abschnitten verwendet werden.",
            "error"
        )

    return redirect(url_for('bahnhof'))


#############################################################
#####################   User  ###############################
#############################################################

#Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    #nach erfolgreichem Login wird zu dieser Seite weitergeleitet
    if current_user.is_authenticated:
        return redirect(url_for('bahnhof'))
    #Erstellt eine Instanz des LoginForm-Objekts
    form = LoginForm()
    #Wird ausgeführt, wenn Benutzer Formular gesendet hat
    if form.validate_on_submit():
        #Sucht User mit gleichen Namen in der DB
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        #Wenn User nicht existiert in der DB oder Passwort nicht stimmt
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        #Erfolgreiche Anmeldung und Weiterleitung
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('bahnhof')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form, role='mitarbeiter')


#Logout
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('bahnhof'))

#Neue Mitarbeiter und Admins anmelden
@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    #Zugriff nur für Admins
    if current_user.role.value != 'admin':
        flash('Nur Admins dürfen neue Benutzer registrieren!', 'warning')
        return redirect(url_for('bahnhof'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Neuen Benutzer anlegen
        user = User(username=form.username.data, email=form.email.data, role=form.role.data)
        user.set_password(form.password.data)
        #Neuen User speichern
        db.session.add(user)
        db.session.commit()
        flash(f'Neuer Benutzer "{user.username}" erfolgreich registriert!', 'success')
        return redirect(url_for('bahnhof'))

    return render_template('register.html', title='Neuer Benutzer', form=form)

#############################################################
#####################   API   ###############################
#############################################################

##Bahnhof
@app.route('/bahnhoefe', methods=['GET'])


def get_bahnhoefe_api():
    """
    API-Endpunkt zum Suchen und Auflisten von Bahnhöfen.
    Unterstützt den optionalen Query-Parameter 'q' zur Volltextsuche (Name/ID).
    """


    query_term = request.args.get('q', default='', type=str)


    stmt = sa.select(Bahnhof)

    if query_term:

        stmt = stmt.where(
            sa.or_(
                Bahnhof.name.ilike(f'%{query_term}%'),
                # Optional: Suche nach ID, falls q eine Zahl ist
                Bahnhof.bahnhofId == query_term
            )
        )


    bahnhoefe = db.session.scalars(stmt).all()


    items = []
    for b in bahnhoefe:
        items.append({
            "bahnhofId": b.bahnhofId,
            "name": b.name,
        })
    total_count = len(bahnhoefe)

    return jsonify({"total": total_count, "items": items})