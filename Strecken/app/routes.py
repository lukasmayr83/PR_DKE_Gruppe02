from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request, jsonify, abort
from app import app
from app.forms import LoginForm, RegistrationForm, BahnhofForm, AbschnittForm, WarnungForm, StreckenForm
from flask_login import current_user, login_user
import sqlalchemy as sa
from app import db
from app.models import User, Bahnhof, Abschnitt, Warnung, Strecke, Reihenfolge
from flask_login import logout_user
from flask_login import login_required
import folium
from sqlalchemy.orm import selectinload
import sqlalchemy.orm as so

#############################################################
#################    Abschnitt   ############################
#############################################################

#Abschnitte anzeigen
@app.route('/abschnitt')
@login_required
def abschnitt():
    # nur für DEBUGGING
    #print("--- START: Kartengenerierung für Abschnitte ---")

    posts = db.session.query(Abschnitt).join(Abschnitt.startBahnhof).order_by(Bahnhof.name).all()

    all_coords = []
    section_groups = {}


    fallback_lat, fallback_lon = 47.5162, 14.5501
    m = folium.Map(location=[fallback_lat, fallback_lon], zoom_start=7, height='100%')


    for abschnitt in posts:
        abschnitt_name = getattr(abschnitt, 'name')

        #nur für DEBUGGING
        #print("\nVerarbeite Abschnitt: {abschnitt_name}")

        startbahnhof = getattr(abschnitt, 'startBahnhof', None)
        endbahnhof = getattr(abschnitt, 'endBahnhof', None)


        bahnhoefe_zu_markieren = []
        if startbahnhof:
            bahnhoefe_zu_markieren.append(('Startbahnhof', startbahnhof)) #'blue'))
        if endbahnhof:
            bahnhoefe_zu_markieren.append(('Endbahnhof', endbahnhof)) # 'blue'))


        if not bahnhoefe_zu_markieren:
            # nur für DEBUGGING
            #print(f"WARNUNG: Abschnitt '{abschnitt_name}' hat keine gültigen Start/End-Bahnhöfe und wird übersprungen.")
            continue

        group = folium.FeatureGroup(name=abschnitt_name)
        section_groups[abschnitt_name] = group
        group.add_to(m)

        route_coords = []

        for typ, b in bahnhoefe_zu_markieren:

            if not b.latitude or not b.longitude:
                # nur für DEBUGGING
                #print(f"  --> Koordinate fehlt für {b.name}. Führe Geocoding aus...")
                b.geocode_address()

            if b.latitude and b.longitude:
                lat_lon = (b.latitude, b.longitude)
                route_coords.append(lat_lon)
                all_coords.append(lat_lon)

                #print(f"  --> ERFOLG: {b.name} ({typ}) bei {b.latitude}, {b.longitude}")

                marker = folium.Marker(
                    lat_lon,
                    tooltip=f"{typ}: {b.name}",
                    popup=f"Abschnitt: {abschnitt_name}<br>{typ}: {b.name}<br>Adresse: {b.adresse}",
                    #icon=folium.Icon(color=farbe)
                )

                marker.add_to(group)
            #else:
                #print(f"  --> FEHLER: Konnte keine Koordinaten für {b.name} finden/speichern.")

        if len(route_coords) == 2:
            folium.PolyLine(
                route_coords,
                color='blue',
                weight=4,
                opacity=0.7,
                tooltip=f"Route: {abschnitt_name}"
            ).add_to(group)
        #else:

            #print(
                #f"WARNUNG: PolyLine kann für '{abschnitt_name}' nicht gezeichnet werden (Nur {len(route_coords)} von 2 Endpunkten gefunden).")

    db.session.commit()

    if all_coords:
        center_lat = sum(lat for lat, lon in all_coords) / len(all_coords)
        center_lon = sum(lon for lat, lon in all_coords) / len(all_coords)

        m.location = [center_lat, center_lon]

    folium.LayerControl().add_to(m)

    #print("--- ENDE: Kartengenerierung erfolgreich ---")

    map_html = m._repr_html_()

    return render_template(
        'abschnitt.html',
        title='Abschnitte',
        posts=posts,
        map_html=map_html,
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




    return render_template("abschnitt_add.html", form=form,bahnhoefe=bahnhoefe)


@app.route("/abschnitt/edit/<int:abschnitt_id>", methods=["GET", "POST"])
@login_required
def edit_abschnitt(abschnitt_id):
    abschnitt = db.session.get(Abschnitt, abschnitt_id)
    form = AbschnittForm(obj=abschnitt)
    bahnhoefe = Bahnhof.query.order_by(Bahnhof.name).all()
    bahnhof_choices = [(b.bahnhofId, b.name) for b in bahnhoefe]
    form.startBahnhof.choices = bahnhof_choices
    form.endBahnhof.choices = bahnhof_choices

    #Dropdowns werden beim aufrufen der Seite mit den dazugehörigen Bahnhöfen gefüllt
    if request.method == 'GET':
        form.startBahnhof.data = abschnitt.startBahnhofId
        form.endBahnhof.data = abschnitt.endBahnhofId


    if form.validate_on_submit():
        form.populate_obj(abschnitt)
        abschnitt.startBahnhofId = form.startBahnhof.data
        abschnitt.endBahnhofId = form.endBahnhof.data

        try:
            db.session.commit()
            flash(f"Abschnitt aktualisiert", "success")
            return redirect(url_for("abschnitt"))
        except Exception:
            db.session.rollback()
            flash("Fehler beim Speichern", "danger")

    return render_template("abschnitt_edit.html", form=form, abschnitt=abschnitt)

@app.route("/abschnitt/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_abschnitt():
    ids = request.form.getlist("abschnitt_ids")
    deleted_count = 0

    if not ids:
        flash ("Keine Abschnitte ausgewählt.", "error")
        return redirect(url_for("abschnitt"))

    for id in ids:
        try:

            abschnitt = db.session.get(Abschnitt, int(id))
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
    alle_strecken = Strecke.query.order_by(Strecke.name).all()

    # Bereite die Daten für das Template vor
    strecken_daten = []
    for strecke in alle_strecken:
        # 1. Start- und Endbahnhof über die Property abrufen
        start_bhf, end_bhf = strecke.start_end_bahnhoefe

        strecken_daten.append({
            'id': strecke.streckenId,
            'name': strecke.name,

            # 2. Daten für die Anzeige berechnen
            'start_bahnhof': start_bhf.name if start_bhf else 'N/A',
            'end_bahnhof': end_bhf.name if end_bhf else 'N/A',

            # 3. Anzahl der Abschnitte zählen
            'anzahl_abschnitte': len(strecke.reihenfolge)
        })

    return render_template(
        'strecke.html',
        title='Alle definierten Strecken',
        strecken=strecken_daten,
        # Stellen Sie sicher, dass 'role' ebenfalls übergeben wird, falls es benötigt wird
        role=current_user.role
    )




@app.route("/strecke/add", methods=["GET", "POST"])
@login_required
def strecke_add():
    form = StreckenForm()

    if form.validate_on_submit():

        gewaehlte_ids_str = request.form.get('abschnitt_ids')

        gewaehlte_ids = []
        if gewaehlte_ids_str:
            try:

                gewaehlte_ids = [int(id_str) for id_str in gewaehlte_ids_str.split(',') if id_str]
            except ValueError:

                flash('Fehler: Ungültiges Format der Abschnitts-IDs.', 'danger')
                return render_template("strecke_add.html", form=form)


        if not gewaehlte_ids:
            flash('Bitte definieren Sie mindestens einen Abschnitt für die Strecke.', 'danger')
            return render_template("strecke_add.html", form=form)


        abschnitte_in_reihenfolge = []
        for abschnitt_id in gewaehlte_ids:
            abschnitt = Abschnitt.query.get(abschnitt_id)
            if abschnitt:
                abschnitte_in_reihenfolge.append(abschnitt)
            else:
                print(f"WARNUNG: Abschnitts-ID {abschnitt_id} nicht gefunden.")


        validierung_erfolgreich = True

        for i in range(1, len(abschnitte_in_reihenfolge)):
            vorheriger_abschnitt = abschnitte_in_reihenfolge[i - 1]
            aktueller_abschnitt = abschnitte_in_reihenfolge[i]

            if vorheriger_abschnitt.endBahnhofId != aktueller_abschnitt.startBahnhofId:
                flash(
                    f'Fehler: Die Abschnitte sind nicht zusammenhängend. '
                    f'Ende von "{vorheriger_abschnitt.name}" ist nicht Start von "{aktueller_abschnitt.name}".',
                    'danger'
                )
                validierung_erfolgreich = False
                break

        if not validierung_erfolgreich:
            return render_template("strecke_add.html", form=form)




        neue_strecke = Strecke(
            name=form.name.data,
        )

        db.session.add(neue_strecke)


        if abschnitte_in_reihenfolge:
            for i, abschnitt in enumerate(abschnitte_in_reihenfolge):

                reihenfolge_objekt = Reihenfolge(
                    abschnitt=abschnitt,
                    reihenfolge=i + 1
                )


                neue_strecke.reihenfolge.append(reihenfolge_objekt)


        db.session.commit()

        flash(f'Strecke "{neue_strecke.name}" wurde gespeichert!', 'success')
        return redirect(url_for("strecke"))


    return render_template(
        "strecke_add.html",
        form=form,
        api_url=url_for('api_abschnitte_daten')
    )

@app.route("/strecke/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_strecke():
    ids = request.form.getlist("strecke_ids")

    deleted_count = 0

    if not ids:
        flash("Keine Strecken ausgewählt.", "error")
        return redirect(url_for('strecke'))

    for bid in ids:
        try:

            strecke_query = (
                sa.select(Strecke)
                .where(Strecke.streckenId == int(bid))
            )
            strecke = db.session.execute(strecke_query).scalar_one_or_none()

            if strecke:
                db.session.delete(strecke)
                deleted_count += 1

        except Exception as e:
            print(f"Fehler beim Laden von Strecke {bid}: {e}")
            continue


    if deleted_count > 0:
        db.session.commit()
        flash(f"{deleted_count} Strecke/Strecken erfolgreich gelöscht.", "success")


    return redirect(url_for('strecke'))

#############################################################
#################    Warnung     ############################
#############################################################

@app.route('/', methods=['GET', 'POST'])
@app.route('/warnung', methods=['GET', 'POST'])
@login_required
def warnung():
    #Alle Warnungen aus der DB laden
    posts = Warnung.query.order_by(Warnung.bezeichnung).all()

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
        db.session.commit()

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
    warnung = db.session.get(Warnung, warnung_id) #lädt Warnung aus DB
    if not warnung:
        flash("Warnung nicht gefunden", "danger")
        return redirect(url_for("warnung"))


    form = WarnungForm(obj=warnung) #befüllt das Formular

    abschnitte_alle = Abschnitt.query.join(Abschnitt.startBahnhof).order_by(Bahnhof.name).all() #lädt alle Abschnitte
    abschnitt_choices = [(a.abschnittId, a.name) for a in abschnitte_alle]
    form.abschnitt.choices = abschnitt_choices #an Formular übergeben

    #wird aufgerufen wenn der User die Seite zum ersten Mal aufruft
    if request.method == 'GET':
        aktuelle_abschnitte_ids = [a.abschnittId for a in warnung.abschnitte] #erstellt Liste der verknüpften Abschnitte
        form.abschnitt.data = aktuelle_abschnitte_ids

    if form.validate_on_submit():

        form.populate_obj(warnung)

        warnung.abschnitte.clear() #löscht alle vorhandenen Verbindungen

        #speichert die neuen Abschnitte
        neue_abschnitt_ids = form.abschnitt.data

        for abschnitt_id in neue_abschnitt_ids:
            abschnitt_obj = db.session.get(Abschnitt, abschnitt_id)
            if abschnitt_obj:
                warnung.abschnitte.append(abschnitt_obj)

        try:
            db.session.commit()
            flash(f"Warnung {warnung.bezeichnung} aktualisiert", "success")
            return redirect(url_for("warnung"))
        except Exception as e:
            db.session.rollback()
            flash(f"Fehler beim Speichern der Warnung: {e}", "danger")


    return render_template("warnung_edit.html", form=form, warnung=warnung)



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
    posts = Bahnhof.query.order_by(Bahnhof.name).all()

    #Wenn es Bahnhöfe gibt, wird eine Karte erstellt
    if posts:
        for b in posts:
            if not b.latitude or not b.longitude: #falls es fehlt wird der Breiten -oder Längengrad noch bestimmt
                b.geocode_address() #ruft Methode im models auf
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
    bahnhof = db.session.get(Bahnhof, bahnhof_id) #Bahnhofsdaten aus der DB laden
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
    #liest den Suchbegriff aus der URL
    query_term = request.args.get('q', default='', type=str)

    stmt = sa.select(Bahnhof)

    if query_term:

        stmt = stmt.where(
            sa.or_(
                Bahnhof.name.ilike(f'%{query_term}%'),
                Bahnhof.bahnhofId == query_term
            )
        )


    bahnhoefe = db.session.scalars(stmt).all()


    items = []
    for b in bahnhoefe:
        items.append({
            "bahnhofId": b.bahnhofId,
            "name": b.name
        })
    total_count = len(bahnhoefe)

    return jsonify({"total": total_count, "items": items})


@app.route('/strecken', methods=['GET'])
def get_strecken_api():
    # liest den Suchbegriff aus der URL
    query_term = request.args.get('q', default='', type=str)

    stmt = sa.select(Strecke)

    if query_term:
        stmt = stmt.where(
            sa.or_(
                Strecke.name.ilike(f'%{query_term}%'),
                Strecke.streckenId == query_term
            )
        )

    strecken = db.session.scalars(stmt).all()

    items = []
    for s in strecken:
        startBahnhof, endBahnhof = s.start_end_bahnhoefe

        items.append({
            "streckeId": s.streckenId,
            "name": s.name,
            "startBahnhof": startBahnhof.bahnhofId,
            "endBahnhof": endBahnhof.bahnhofId
        }

        )
    total_count = len(strecken)

    return jsonify({"total": total_count, "items": items})


@app.route('/strecken/<int:streckeId>/abschnitte', methods=['GET'])
def get_strecke_abschnitte_api(streckeId):
    strecke = db.session.scalar(
        sa.select(Strecke)
        .filter_by(streckenId=streckeId)
        .options(
            so.joinedload(Strecke.reihenfolge)
            .joinedload(Reihenfolge.abschnitt)
            .joinedload(Abschnitt.startBahnhof),
            so.joinedload(Strecke.reihenfolge)
            .joinedload(Reihenfolge.abschnitt)
            .joinedload(Abschnitt.endBahnhof),
        )
    )

    if strecke is None:
        abort(404)

    items = []



    for reihenfolge_obj in strecke.reihenfolge:
        abschnitt = reihenfolge_obj.abschnitt


        start_bhf_name = abschnitt.startBahnhof.name
        end_bhf_name = abschnitt.endBahnhof.name

        items.append({
            "abschnittId": abschnitt.abschnittId,
            "reihenfolgeId": reihenfolge_obj.reihenfolge,
            "startBahnhof": start_bhf_name,
            "endBahnhof": end_bhf_name,
            "spurweite": abschnitt.spurweite,
            "nutzungsentgelt": abschnitt.nutzungsentgelt,
            "maxGeschwindigkeit": abschnitt.max_geschwindigkeit
        })

    total_count = len(items)
    return jsonify({"total": total_count, "items": items}), 200


@app.route('/warnungen', methods=['GET'])
def get_warnung_api():
    query_term = request.args.get('q', default='', type=str)

    stmt = sa.select(Warnung)

    if query_term:
        stmt = stmt.where(
            sa.or_(
                Warnung.bezeichnung.ilike(f'%{query_term}%'),
                Warnung.warnungId == query_term
            )
        )

    warnung = db.session.scalars(stmt).all()

    items = []
    for w in warnung:
        items.append({
            "warnungId": w.warnungId,
            "bezeichnung": w.bezeichnung,
            "startZeit": w.startZeit,
            "endZeit": w.endZeit
        })
    total_count = len(warnung)

    return jsonify({"total": total_count, "items": items})

#damit Javascript auf die Koordinaten der Bahnhöfe zugreifen kann; für das Anzeigen der Abschnitte beim Hinzufügen
@app.route('/api/bahnhof/<int:bahnhof_id>')
def get_bahnhof_coords(bahnhof_id):
    bahnhof = Bahnhof.query.get(bahnhof_id) #ruft die Daten für den bestimmten Bahnhof ab

    #gibt Daten zurück
    return jsonify({
        'id': bahnhof.bahnhofId,
        'latitude': bahnhof.latitude,
        'longitude': bahnhof.longitude
    })

#damit Javascript auf die Koordinaten der Bahnhöfe eines bestimmten Abschnitts zugreifen kann;
# für das Anzeigen der Abschnitte beim Hinzufügen (Warnung erstellen)
@app.route('/api/abschnitt/<int:abschnitt_id>')
def api_get_abschnitt_coords(abschnitt_id):
    abschnitt = db.session.get(Abschnitt, abschnitt_id)


    startbahnhof = abschnitt.startBahnhof
    endbahnhof = abschnitt.endBahnhof

    return jsonify({
        'id': abschnitt.abschnittId,
        'start': {
            'lat': startbahnhof.latitude,
            'lon': startbahnhof.longitude,
            'name': startbahnhof.name
        },
        'end': {
            'lat': endbahnhof.latitude,
            'lon': endbahnhof.longitude,
            'name': endbahnhof.name
        }
    })

#liefert die benötigten Daten für Strecken_add
#Alle Bahnhöfe und Abschnitte werden geliefert
@app.route("/api/abschnitte_daten", methods=["GET"])
def api_abschnitte_daten():

    from sqlalchemy.orm import joinedload
    from flask import jsonify

    abschnitte = Abschnitt.query.options(
        joinedload(Abschnitt.startBahnhof),
        joinedload(Abschnitt.endBahnhof)
    ).all()

    abschnitt_data = []
    bahnhoefe_map = {}

    for a in abschnitte:

        start_name = a.startBahnhof.name if a.startBahnhof else "Unbekannt"
        end_name = a.endBahnhof.name if a.endBahnhof else "Unbekannt"

        abschnitt_data.append({
            "abschnittId": a.abschnittId,
            "name": f"{start_name} → {end_name}",
            "startBahnhofId": a.startBahnhofId,
            "endBahnhofId": a.endBahnhofId
        })

        if a.startBahnhof:
            bahnhoefe_map[a.startBahnhof.bahnhofId] = start_name
        if a.endBahnhof:
            bahnhoefe_map[a.endBahnhof.bahnhofId] = end_name

    return jsonify({
        'abschnitte': abschnitt_data,
        'bahnhoefe': bahnhoefe_map
    })
