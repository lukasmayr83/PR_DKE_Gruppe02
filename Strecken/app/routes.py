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
from sqlalchemy.orm import selectinload, joinedload
import sqlalchemy.orm as so
from operator import attrgetter

#Abschnitte ab Zeile 23
#Strecke ab Zeile 305
#Warnung ab Zeile 632
#Bahnhof ab Zeile 866
#Schnittstellen ab Zeile 1081


#############################################################
#################    Abschnitt   ############################
#############################################################

#Abschnitte anzeigen
@app.route('/abschnitt')
@login_required
def abschnitt():
    #lädt alle Abschnitte sortiert nach Startbahnhofname
    posts = db.session.query(Abschnitt).join(Abschnitt.startBahnhof).order_by(Bahnhof.name).all()

    all_coords = [] #Liste aller Koordinaten ->Kartenzentrum berechnen
    section_groups = {} #Dictionary zum Speichern der Folium-Gruppen je Abschnitt

    #Karte erstellen; zentriert auf Ö
    fallback_lat, fallback_lon = 47.5162, 14.5501
    m = folium.Map(location=[fallback_lat, fallback_lon], zoom_start=7, height='100%')

    #Schleife über alle Abschnitte
    for abschnitt in posts:

        #holt Namen, Start-und Endbahnhof des Abschnitts
        abschnitt_name = getattr(abschnitt, 'name')
        startbahnhof = getattr(abschnitt, 'startBahnhof', None)
        endbahnhof = getattr(abschnitt, 'endBahnhof', None)


        bahnhoefe_zu_markieren = [] #Liste mit den Bahnhöfen die markiert werden sollen
        #zu markierende Bahnhöfe anfügen
        if startbahnhof:
            bahnhoefe_zu_markieren.append(('Startbahnhof', startbahnhof)) #'blue'))
        if endbahnhof:
            bahnhoefe_zu_markieren.append(('Endbahnhof', endbahnhof)) # 'blue'))


        if not bahnhoefe_zu_markieren:
            continue

        #Folium-Gruppe für diesen Abschnitt erstellen
        group = folium.FeatureGroup(name=abschnitt_name)
        section_groups[abschnitt_name] = group
        group.add_to(m)

        route_coords = [] #speichert Koordinaten des Abschnitts

        #geht alle bahnhöfe durch des abschnitts durch
        for typ, b in bahnhoefe_zu_markieren:

            #prüft ob Koordinaten des bahnhofs vorhanden sind, notfalls generieren
            if not b.latitude or not b.longitude:
                b.geocode_address()

            if b.latitude and b.longitude:
                lat_lon = (b.latitude, b.longitude) #Tupel mit Koordinaten
                route_coords.append(lat_lon) #fügt Koordinaten an
                all_coords.append(lat_lon)  #fügt Koordinaten an

                icon_url = 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png'
                shadow_url = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png'

                custom_icon = folium.CustomIcon(
                    icon_image=icon_url,
                    shadow_image=shadow_url,
                    icon_size=(25, 41),
                    icon_anchor=(12, 41),
                    popup_anchor=(1, -34),
                    shadow_size=(41, 41)
                )


                #erstellt marker auf der Karte
                marker = folium.Marker(
                    lat_lon,
                    tooltip=f"{typ}: {b.name}", #hovern
                    popup=f"Abschnitt: {abschnitt_name}<br>{typ}: {b.name}<br>Adresse: {b.adresse}", #anklicken
                    icon=custom_icon
                )
                marker.add_to(group)

        if (abschnitt.spurweite == 1435):
            c = 'blue'
        else:
            c = 'black'


        #erstellt die verbindungslinie zwischen den beiden Bahnhöfen
        if len(route_coords) == 2:
            folium.PolyLine(
                route_coords,
                color= c,
                weight=4,
                opacity=0.7,
                tooltip=f"Abschnitt: {abschnitt_name}"
            ).add_to(group)


    db.session.commit() #Datenbank speichern

    #zentriert karte auf dne berechneten Mittelpunkt
    if all_coords:
        center_lat = sum(lat for lat, lon in all_coords) / len(all_coords)
        center_lon = sum(lon for lat, lon in all_coords) / len(all_coords)
        m.location = [center_lat, center_lon]

    folium.LayerControl().add_to(m) #um Abschnitte aus- und einblenden zu können


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
    form = AbschnittForm() #erstellt eine Instanz des Formulars

    #Standard-Optionen für Dropdowns
    standard_option_start = [(0, 'Bitte wählen Sie einen Startbahnhof aus')]
    standard_option_end = [(0, 'Bitte wählen Sie einen Endbahnhof aus')]

    #Lädt alle Bahnhöfe aus der DB
    bahnhoefe = Bahnhof.query.order_by(Bahnhof.name).all()
    #Füllt die Dropdowns StartBahnhof und Endbahnhof mit Bahnhöfen +Standard-Optionen
    bahnhof_choices = [(b.bahnhofId, b.name) for b in bahnhoefe]
    form.startBahnhof.choices = standard_option_start + bahnhof_choices
    form.endBahnhof.choices = standard_option_end + bahnhof_choices

    #Spurweite-Optionen
    spurweiten_optionen = [
        (0, 'Bitte wählen Sie eine Spurweite'),
        (1435, 'Normalspur (1435 mm)'),
        (1000, 'Schmalspur (1000 mm)')
    ]
    form.spurweite.choices = spurweiten_optionen

    #Wird ausgeführt, wenn Button Speichern gedruckt wurde
    if form.validate_on_submit():
        #Neue Instanz von Abschnitt mit den Werten des Formulars erstellen
        abschnitt = Abschnitt(
            startBahnhofId=form.startBahnhof.data,
            endBahnhofId=form.endBahnhof.data,
            max_geschwindigkeit=form.max_geschwindigkeit.data,
            spurweite=form.spurweite.data,
            laenge=form.laenge.data,
            nutzungsentgelt=form.nutzungsentgelt.data
        )

        #Abschnitt in DB hinzufügen und speichern
        db.session.add(abschnitt)
        db.session.commit()

        #Info über erfolgreiches Speichern
        flash(f'Abschnitt wurde gespeichert!', 'success')
        #Kommt wieder zurück zur Übersichtsseite der Abschnitte
        return redirect(url_for("abschnitt"))

    return render_template(
        "abschnitt_add.html",
        form=form,
        bahnhoefe=bahnhoefe,
        title='Abschnitt hinzufügen',)

#Abschnitt bearbeiten
@app.route("/abschnitt/edit/<int:abschnitt_id>", methods=["GET", "POST"])
@login_required
def edit_abschnitt(abschnitt_id):
    #Abshcnitt aus DB laden
    abschnitt = db.session.get(Abschnitt, abschnitt_id)

    #Formular mit den vorhandenen Daten laden
    form = AbschnittForm(
        obj=abschnitt,
        original_start_id=abschnitt.startBahnhofId,
        original_end_id=abschnitt.endBahnhofId
    )

    #Dropdown-Optionen befüllen
    standard_option_start = [(0, 'Bitte wählen Sie einen Startbahnhof aus')]
    standard_option_end = [(0, 'Bitte wählen Sie einen Endbahnhof aus')]
    bahnhoefe = Bahnhof.query.order_by(Bahnhof.name).all()
    bahnhof_choices = [(b.bahnhofId, b.name) for b in bahnhoefe]
    form.startBahnhof.choices = standard_option_start + bahnhof_choices
    form.endBahnhof.choices = standard_option_end + bahnhof_choices

    spurweiten_optionen = [
        (0, 'Bitte wählen Sie eine Spurweite'),
        (1435, 'Normalspur (1435 mm)'),
        (1000, 'Schmalspur (1000 mm)')
    ]
    form.spurweite.choices = spurweiten_optionen

    #aktuellen Wert setzen
    form.startBahnhof.data = abschnitt.startBahnhofId
    form.endBahnhof.data = abschnitt.endBahnhofId

    #wird aufgerufen beim Laden der Seite -> setzt default Werte falls es die Werte in der DB noch nicht gibt
    if request.method == 'GET':
        if form.startBahnhof.data is None:
            form.startBahnhof.data = 0

        if form.endBahnhof.data is None:
            form.endBahnhof.data = 0

        if form.spurweite.data is None:
            form.spurweite.data = 0

    #wird ausgelöst beim Speichern klicken
    if form.validate_on_submit():
        abschnitt.spurweite = form.spurweite.data
        abschnitt.max_geschwindigkeit = form.max_geschwindigkeit.data
        abschnitt.laenge = form.laenge.data
        abschnitt.nutzungsentgelt = form.nutzungsentgelt.data
        abschnitt.startBahnhofId = form.startBahnhof.data
        abschnitt.endBahnhofId = form.endBahnhof.data

        try:
            db.session.commit()
            flash(f"Abschnitt aktualisiert", "success")
            return redirect(url_for("abschnitt"))
        except Exception as e:
            db.session.rollback()
            flash("Fehler beim Speichern", "danger")

    return render_template(
        "abschnitt_edit.html",
        form=form,
        abschnitt=abschnitt,
        title='Abschnitt bearbeiten',)

#Abschnitte löschen
@app.route("/abschnitt/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_abschnitt():

    ids = request.form.getlist("abschnitt_ids") #holt alle ausgewählten AbschnittIds

    deleted_count = 0 #zähler für erfolgreiches löschen
    blocked_names = [] #Liste von Abschnitte die nicht gelöscht werden konnten

    #prüft ob Abschnitte ausgewählt sind
    if not ids:
        flash("Keine Abschnitte ausgewählt.", "error")
        return redirect(url_for('abschnitt'))

    #geht jeden ausgewählten Abschnitt durch
    for aid in ids:
        try:
            # Abschnitt laden aus DB
            abschnitt_query = (
                sa.select(Abschnitt)
                .where(Abschnitt.abschnittId == int(aid))
            )
            abschnitt = db.session.execute(abschnitt_query).scalar_one_or_none()

            if abschnitt:
                # Prüfen ob der Abschnitt in einer Strecke verwendet wird
                verknuepfung_query = (
                    sa.select(sa.func.count())
                    .select_from(Reihenfolge)
                    .where(Reihenfolge.abschnittId == int(aid))
                )
                count = db.session.execute(verknuepfung_query).scalar() #zählt, wie oft der Abschnitt verwendet wird

                #löscht sie falls sie nicht verwendet werden; fügt sie sonst zu blocked_names hinzu
                if count > 0:
                    blocked_names.append(abschnitt.name)
                else:
                    # Löschen, falls keine Verknüpfung gefunden wurde
                    db.session.delete(abschnitt)
                    deleted_count += 1

        except Exception as e:
            print(f"Fehler beim Laden von Abschnitt {aid}: {e}")
            continue

    #falls Abschnitte gelöscht wurden -> erzeugt Flash-Nachricht
    if deleted_count > 0:
        db.session.commit()
        flash(f"{deleted_count} Abschnitt/Abschnitte erfolgreich gelöscht.", "success")

    #falls Abschnitte blockiert sind -> erzeugt Flash-Nachricht
    if blocked_names:
        names_str = ", ".join(blocked_names)
        flash(
            f"Folgende Abschnitte: [{names_str}] konnten nicht gelöscht werden, da sie in Strecken verwendet werden.",
            "error"
        )

    return redirect(url_for('abschnitt'))





#############################################################
#################    Strecke     ############################
#############################################################

#Strecken anzeigen
@app.route('/', methods=['GET', 'POST'])
@app.route('/strecke', methods=['GET', 'POST'])
@login_required
def strecke():

    #erstellt das Custom-Icon basierend auf der Farbe
    def get_icon(color_name):
        return folium.CustomIcon(
            icon_image=f'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-{color_name}.png',
            shadow_image='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
            icon_size=(25, 41),
            icon_anchor=(12, 41),
            popup_anchor=(1, -34),
            shadow_size=(41, 41)
        )


    #Strecken aus der DB laden
    alle_strecken = Strecke.query.order_by(Strecke.name).all()

    strecken_daten = [] #Liste für die
    all_coords = [] #sammelt alle Koordinaten
    section_groups = {} #Groups für Layer-Control

    #karte erstellen -> zentrieren auf Ö
    fallback_lat, fallback_lon = 47.5162, 14.5501
    m = folium.Map(location=[fallback_lat, fallback_lon], zoom_start=7, height='100%')

    #Schleife über alle Strecken
    for strecke in alle_strecken:
        start_bhf, end_bhf = strecke.start_end_bahnhoefe #ruft Methode aus models.py auf

        #Daten für Tabellenansicht anfügen
        strecken_daten.append({
            'id': strecke.streckenId,
            'name': strecke.name,
            'start_bahnhof': start_bhf.name if start_bhf else 'N/A',
            'end_bahnhof': end_bhf.name if end_bhf else 'N/A',
            'anzahl_abschnitte': len(strecke.reihenfolge)
        })

        # Karten-Visualisierung für diese Strecke
        if start_bhf or end_bhf:

            #Featuregroup für jede Strecke
            group = folium.FeatureGroup(name=strecke.name)
            section_groups[strecke.name] = group
            group.add_to(m)

            route_coords = [] #speichert Koordinaten der Strecke

            # Alle Abschnitte dieser Strecke durchgehen (über Reihenfolge)
            for reihenfolge in strecke.reihenfolge:
                abschnitt = reihenfolge.abschnitt

                if not abschnitt:
                    continue

                #Startbahnhof des Abschnitts
                if abschnitt.startBahnhof:
                    #falls Koordinaten noch nicht gibt -> Methode dafür aufrufen
                    if not abschnitt.startBahnhof.latitude or not abschnitt.startBahnhof.longitude:
                        abschnitt.startBahnhof.geocode_address()

                    if abschnitt.startBahnhof.latitude and abschnitt.startBahnhof.longitude:
                        lat_lon = (abschnitt.startBahnhof.latitude, abschnitt.startBahnhof.longitude) #Tupel mit Koordinaten
                        if lat_lon not in route_coords:
                            route_coords.append(lat_lon) #Tupel anfügen
                            all_coords.append(lat_lon)

                            # Startbahnhof der Strecke in Grün, normaler Startbahnhof eines Abschnitts in blau
                            color = 'green' if abschnitt.startBahnhof == start_bhf else 'blue'

                            #Marker erstellen
                            folium.Marker(
                                lat_lon,
                                tooltip=abschnitt.startBahnhof.name,
                                popup=f"Strecke: {strecke.name}<br>Bahnhof: {abschnitt.startBahnhof.name}<br>Adresse: {abschnitt.startBahnhof.adresse}",
                                icon=get_icon(color)
                            ).add_to(group)

                # Endbahnhof des Abschnitts
                if abschnitt.endBahnhof:
                    if not abschnitt.endBahnhof.latitude or not abschnitt.endBahnhof.longitude:
                        abschnitt.endBahnhof.geocode_address()

                    if abschnitt.endBahnhof.latitude and abschnitt.endBahnhof.longitude:
                        lat_lon = (abschnitt.endBahnhof.latitude, abschnitt.endBahnhof.longitude) #Tupel mit Koordinaten
                        if lat_lon not in route_coords:
                            route_coords.append(lat_lon) #Tupel anfügen
                            all_coords.append(lat_lon)

                            # Endbahnhof der Strecke in Grün, normaler Endbahnhof eines Abschnitts in blau
                            color = 'red' if abschnitt.endBahnhof == end_bhf else 'blue'

                            # Marker erstellen
                            folium.Marker(
                                lat_lon,
                                tooltip=abschnitt.endBahnhof.name,
                                popup=f"Strecke: {strecke.name}<br>Bahnhof: {abschnitt.endBahnhof.name}<br>Adresse: {abschnitt.endBahnhof.adresse}",
                                icon=get_icon(color)
                            ).add_to(group)

            if (abschnitt.spurweite==1435):
                c = 'blue'
            else:
                c = 'black'

            # Polylinie für den Abschnitt zeichnen
            if len(route_coords) >= 2:
                folium.PolyLine(
                    route_coords,
                    color=c,
                    weight=4,
                    opacity=0.7,
                    tooltip=f"Strecke: {strecke.name}"
                ).add_to(group)

    db.session.commit() #DB speichern

    # Karte zentrieren
    if all_coords:
        center_lat = sum(lat for lat, lon in all_coords) / len(all_coords)
        center_lon = sum(lon for lat, lon in all_coords) / len(all_coords)
        m.location = [center_lat, center_lon]

    folium.LayerControl().add_to(m)
    map_html = m._repr_html_()

    return render_template(
        'strecke.html',
        title='Strecken',
        strecken=strecken_daten,
        map_html=map_html,
        role=current_user.role
    )

#Strecke hinzufügen
@app.route("/strecke/add", methods=["GET", "POST"])
@login_required
def strecke_add():
    form = StreckenForm() #Form initialisieren

    #wird aufgerufen wenn speichern gedruckt wird
    if form.validate_on_submit():
        #AbshcnittsIDs holen
        gewaehlte_ids_str = request.form.get('abschnitt_ids')

        #String in Liste umwandlen
        gewaehlte_ids = []
        if gewaehlte_ids_str:
            try:
                gewaehlte_ids = [int(id_str) for id_str in gewaehlte_ids_str.split(',') if id_str]
            except ValueError:

                flash('Fehler: Ungültiges Format der Abschnitts-IDs.', 'danger')
                return render_template("strecke_add.html", form=form)

        #Streck benötigt mindestens einen Abschnitt
        if not gewaehlte_ids:
            flash('Bitte definieren Sie mindestens einen Abschnitt für die Strecke.', 'danger')
            return render_template("strecke_add.html", form=form)

        #alle Abschnittsobjekte aus DB holen
        abschnitte_in_reihenfolge = []
        for abschnitt_id in gewaehlte_ids:
            abschnitt = Abschnitt.query.get(abschnitt_id)
            if abschnitt:
                abschnitte_in_reihenfolge.append(abschnitt)
            else:
                print(f"WARNUNG: Abschnitts-ID {abschnitt_id} nicht gefunden.")

        #prüft ob Abschnitte zusammenhängend sind
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

        #Strecke erst einmal nur mit Namen erstellen
        neue_strecke = Strecke(
            name=form.name.data,
        )
        db.session.add(neue_strecke)

        #Abshcnitte mit Reihenfolge zu der Strecke hinzuspeichern
        if abschnitte_in_reihenfolge:
            for i, abschnitt in enumerate(abschnitte_in_reihenfolge):

                reihenfolge_objekt = Reihenfolge(
                    abschnitt=abschnitt,
                    reihenfolge=i + 1
                )
                neue_strecke.reihenfolge.append(reihenfolge_objekt)

        db.session.commit() #DB speichern

        #Flash-Nachricht bei Erfolg
        flash(f'Strecke "{neue_strecke.name}" wurde gespeichert!', 'success')
        return redirect(url_for("strecke"))


    return render_template(
        "strecke_add.html",
        form=form,
        api_url=url_for('api_abschnitte_daten'),
        title='Strecke hinzufügen',
    )

#Strecke bearbeiten
@app.route('/strecke/edit/<int:strecke_id>', methods=['GET', 'POST'])
@login_required
def strecke_edit(strecke_id):
    strecke = Strecke.query.get_or_404(strecke_id)

    # Form mit dem originalen Namen initialisieren
    form = StreckenForm(original_name=strecke.name)

    #wird ausgelöst beim Speichern
    if form.validate_on_submit():

        # Streckenname und Abschnitte holen
        strecke.name = form.name.data
        abschnitt_ids = request.form.get('abschnitt_ids', '')

        if abschnitt_ids:
            #String in Liste umwandeln
            ids = [int(x) for x in abschnitt_ids.split(',') if x]

            #alle alten Reihenfolge-Einträge löschen für diese Strecke
            Reihenfolge.query.filter_by(streckeId=strecke.streckenId).delete()

            #erstellt die neuen Einträge
            for position, abschnitt_id in enumerate(ids, start=1):
                neue_reihenfolge = Reihenfolge(
                    streckeId=strecke.streckenId,
                    abschnittId=abschnitt_id,
                    reihenfolge=position
                )
                db.session.add(neue_reihenfolge)

        db.session.commit()
        flash('Strecke erfolgreich aktualisiert!', 'success')
        return redirect(url_for('strecke'))

    if request.method == 'GET':
        form.name.data = strecke.name #Name ins Eingabefeld schreiben

    # die bereits verknüpften abschnitte sortiert laden für das Frontend
    try:
        existing_abschnitte = [
            r.abschnitt.abschnittId
            for r in sorted(strecke.reihenfolge, key=lambda x: x.reihenfolge)
            if r.abschnitt
        ]
    except Exception as e:
        print(f"Fehler: {e}")
        existing_abschnitte = []

    return render_template(
        'strecke_edit.html',
        form=form,
        strecke=strecke,
        existing_abschnitte=existing_abschnitte,
        api_url=url_for('api_abschnitte_daten'),
        title='Strecke bearbeiten',
        role=current_user.role
    )

#Strecken löschen
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

#Streckendetails anzeigen für MA
@app.route('/strecke/view/<int:strecke_id>', methods=['GET'])
@login_required
def strecke_view(strecke_id):
    #STrecke aus DB laden
    strecke = Strecke.query.get_or_404(strecke_id)

    #Abschnitte sortiert nach Reihenfolge in Liste geben
    sortierte_eintraege = sorted(strecke.reihenfolge, key=attrgetter('reihenfolge'))
    existing_abschnitte = []
    for r in sortierte_eintraege:
        if r.abschnitt:
            existing_abschnitte.append(r.abschnitt.abschnittId)

    return render_template(
        'strecke_view.html',
        strecke=strecke,
        existing_abschnitte=existing_abschnitte,
        api_url=url_for('api_abschnitte_daten'),
        title='Strecke Details',
        role=current_user.role
    )





#############################################################
#################    Warnung     ############################
#############################################################

#Warnungen anzeigen
@app.route('/warnung', methods=['GET', 'POST'])
@login_required
def warnung():
    # Alle Warnungen aus der DB laden
    posts = Warnung.query.order_by(Warnung.bezeichnung).all()

    return render_template(
        'warnung.html',
        posts=posts,
        role=current_user.role,
        title='Warnungen',
    )

@app.route("/warnung/add", methods=["GET", "POST"])
@login_required
def warnung_add():
    form = WarnungForm() #Form initialisieren

    #Choices = alle Abschnitte
    form.abschnitt.choices = [(a.abschnittId, a.name) for a in Abschnitt.query.all()]

    #wird ausgeführt beim Speichern
    if form.validate_on_submit():

        # Neue Warnung erzeugen
        warnung = Warnung(
            bezeichnung=form.bezeichnung.data,
            beschreibung=form.beschreibung.data,
            startZeit=form.startZeit.data,
            endZeit=form.endZeit.data or None
        )

        #neue Warnung ohne dazugehörigen Abschnitten in der DB speichern
        db.session.add(warnung)
        db.session.commit()

        # Ausgewählte AbschnittIds laden und als Liste speichern
        gewaehlte_ids = form.abschnitt.data
        if not isinstance(gewaehlte_ids, list):
            gewaehlte_ids = [gewaehlte_ids]

        #Abschnitte laden
        if gewaehlte_ids:
            abschnitte = Abschnitt.query.filter(
                Abschnitt.abschnittId.in_(gewaehlte_ids)
            ).all()
            #Abschnitte mit Warnung verknüpfen
            warnung.abschnitte.clear()
            for abschnitt in abschnitte:
                warnung.abschnitte.append(abschnitt)

        db.session.commit() #DB commit

        flash(f'Warnung "{warnung.bezeichnung}" wurde gespeichert!', 'success')
        return redirect(url_for("warnung"))

    return render_template("warnung_add.html", form=form, title='Warnung hinzufügen',)

#Warnungen löschen
@app.route("/warnung/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_warnung():

    #holt zu löschenden Warnungen aus dem Frontend
    ids = request.form.getlist("warnung_ids")

    deleted_count = 0 #zählt wie viele Warnungen gelöscht werden

    #keine Warnungen ausgewählt -> Fehlermeldung
    if not ids:
        flash("Keine Warnungen ausgewählt.", "error")
        return redirect(url_for('warnung'))

    #Schleife über alle Warnungen
    for bid in ids:
        try:
            #schaut ob es die Warnung in der DB gibt
            warnung_query = (
                sa.select(Warnung)
                .where(Warnung.warnungId == int(bid))
            )
            warnung = db.session.execute(warnung_query).scalar_one_or_none()

            #es gibt Warnung -> löschen
            if warnung:
                db.session.delete(warnung)
                deleted_count += 1

        except Exception as e:
            print(f"Fehler beim Laden von Warnung {bid}: {e}")
            continue

    #zeigt die gelöschten Warnungen an
    if deleted_count > 0:
        db.session.commit()
        flash(f"{deleted_count} Warnung/Warnungen erfolgreich gelöscht.", "success")


    return redirect(url_for('warnung'))


#Warnungen bearbeiten
@app.route("/warnung/edit/<int:warnung_id>", methods=["GET", "POST"])
@login_required
def edit_warnung(warnung_id):
    warnung = db.session.get(Warnung, warnung_id) #lädt Warnung aus DB

    #Warnung wurde nicht gefunden -> Fehlermeldung
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

    #wird ausgeführt wenn user auf speichern drückt
    if form.validate_on_submit():

        form.populate_obj(warnung)

        warnung.abschnitte.clear() #löscht alle vorhandenen Verbindungen zwischen der Warnung un den Abshcnitten

        #speichert die neuen Abschnitte
        neue_abschnitt_ids = form.abschnitt.data

        #Abschnitte mit Warnung verknüpfen
        for abschnitt_id in neue_abschnitt_ids:
            abschnitt_obj = db.session.get(Abschnitt, abschnitt_id)
            if abschnitt_obj:
                warnung.abschnitte.append(abschnitt_obj)

        try:
            #bei erfolgreichen Speichern -> Erfolgsmeldung
            db.session.commit()
            flash(f"Warnung {warnung.bezeichnung} aktualisiert", "success")
            return redirect(url_for("warnung"))
        except Exception as e:
            db.session.rollback()
            flash(f"Fehler beim Speichern der Warnung: {e}", "danger")


    return render_template("warnung_edit.html", form=form, warnung=warnung, title='Warnung bearbeiten',)



#############################################################
#################    Bahnhof     ############################
#############################################################

#Bahnhöfe anzeigen
@app.route('/bahnhof', methods=['GET', 'POST'])
@login_required
def bahnhof():
    # Alle Bahnhöfe aus der DB laden
    posts = Bahnhof.query.order_by(Bahnhof.name).all()

    # Wenn es Bahnhöfe gibt, wird eine Karte erstellt
    if posts:
        for b in posts:
            if not b.latitude or not b.longitude:  # falls es fehlt wird der Breiten -oder Längengrad noch bestimmt
                b.geocode_address()  # ruft Methode im models.py auf

        db.session.commit()  # speichert Änderungen in der DB

        # Mittelpunkt berechnen um Karte dementsprechend zu zentrieren
        center_lat = sum(b.latitude for b in posts) / len(posts)
        center_lon = sum(b.longitude for b in posts) / len(posts)

        # Folium-Karte erstellen
        m = folium.Map(location=[center_lat, center_lon], width='100%', height='100%', zoom_start=7)

        # Marker für jeden Bahnhof setzen
        for b in posts:
            folium.Marker(
                [b.latitude, b.longitude],
                tooltip=b.name,
                popup=f"{b.name}<br>{b.adresse}"
            ).add_to(m)

        # HTML-Code der Karte für das Template
        map_html = m._repr_html_()
    else:
        map_html = None

    return render_template(
        'bahnhof.html',
        title='Bahnhöfe',
        posts=posts,
        map_html=map_html,
        role=current_user.role
    )

#Bahnhöfe hinzufügen
@app.route("/bahnhof/add", methods=["GET", "POST"])
@login_required
def bahnhof_add():

    form = BahnhofForm() #Form initialisieren

    # wird ausgeführt wenn auf Button speichern gedrückt wird
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
    return render_template("bahnhof_add.html", form=form, title='Bahnhof hinzufügen',)

#Bahnhof bearbeiten
@app.route("/bahnhof/edit/<int:bahnhof_id>", methods=["GET", "POST"])
@login_required
def edit_bahnhof(bahnhof_id):

    bahnhof = db.session.get(Bahnhof, bahnhof_id) #Bahnhofsdaten aus der DB laden

    #falls Bahnhof nicht gefunden wurde -> Fehlermeldung
    if not bahnhof:
        flash("Bahnhof nicht gefunden.", "error")
        return redirect(url_for("bahnhof"))

    #füllt Formular mit dne Daten aus der DB
    form = BahnhofForm(
        obj=bahnhof,
        original_name=bahnhof.name,
        original_adresse=bahnhof.adresse
    )

    #wird ausgelöst beim speichern
    if form.validate_on_submit():
        form.populate_obj(bahnhof)
        bahnhof.latitude = request.form.get("latitude")
        bahnhof.longitude = request.form.get("longitude")
        db.session.commit()
        flash(f"Bahnhof '{bahnhof.name}' wurde aktualisiert.", "success")
        return redirect(url_for("bahnhof"))

    return render_template("bahnhof_edit.html", form=form, bahnhof=bahnhof, title='Bahnhof bearbeiten',)

#Bahnhöfe löschen
@app.route("/bahnhof/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_bahnhof():

    ids = request.form.getlist("bahnhof_ids") #holt zu löschende BahnhofsIDs

    deleted_count = 0 #zählt, wie viele bahnhöfe gelöscht wurden
    blocked_names = [] #sammelt alle Bahnhöfe die nicht gelöscht werden konnten

    #wirft Fehlermeldung wenn keine Ids ausgewählt wurden
    if not ids:
        flash("Keine Bahnhöfe ausgewählt.", "error")
        return redirect(url_for('bahnhof'))

    #Schleife über alle ausgewählten Bahnhöfe
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

        #prüft ob Bahnhof in Abschnitten verwendet wird -> falls der Fall nicht löschbar -> blocked_names
        if bahnhof:
            if bahnhof.start_abschnitte or bahnhof.end_abschnitte:
                blocked_names.append(bahnhof.name)
            else:
                db.session.delete(bahnhof)
                deleted_count += 1


    #gibt Bahnhöfe die erfolgeich gelöscht wurden -> Erfolgsnachricht
    if deleted_count > 0:
        db.session.commit()
        flash(f"{deleted_count} Bahnhof/Bahnhöfe erfolgreich gelöscht.", "success")

    #gibt die Namen der Bahnhöfe retour die in einem bashcnitt verwendet werden
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
        return redirect(url_for('strecke'))
    #Erstellt eine Instanz des LoginForm-Objekts
    form = LoginForm()
    #Wird ausgeführt, wenn Benutzer Formular gesendet hat
    if form.validate_on_submit():
        #Sucht User mit gleichen Namen in der DB
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        #Wenn User nicht existiert in der DB oder Passwort nicht stimmt
        if user is None or not user.check_password(form.password.data):
            flash('Falscher Benutzername oder Passwort')
            return redirect(url_for('login'))
        #Erfolgreiche Anmeldung und Weiterleitung
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('strecke')
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


###################   externe   #############################

##Bahnhof
@app.route('/bahnhoefe', methods=['GET'])
def get_bahnhoefe_api():
    #liest den Suchbegriff aus der URL
    query_term = request.args.get('q', default='', type=str)

    #DB-Abfrage vorbereiten

    stmt = sa.select(Bahnhof) #falls es keine query_term gibt werden alle Bahnhöfe zurückgegeben

    #falls es query-Term gibt wird der Bahnhof zurückgegeben mit dem Namen oder der Id
    if query_term:
        stmt = stmt.where(
            sa.or_(
                Bahnhof.name.ilike(f'%{query_term}%'),
                Bahnhof.bahnhofId == query_term
            )
        )

    #DB-Abfrage ausführen
    bahnhoefe = db.session.scalars(stmt).all()

    #über alle Bahnhöfe iterieren und in items speichern JSON vorbereiten
    items = []
    for b in bahnhoefe:
        items.append({
            "bahnhofId": b.bahnhofId,
            "name": b.name
        })
    total_count = len(bahnhoefe) #Anzahl der bahnhöfe berechnen

    return jsonify({"total": total_count, "items": items}) #JSON zurückgeben

#Strecken
@app.route('/strecken', methods=['GET'])
def get_strecken_api():
    # liest den Suchbegriff aus der URL
    query_term = request.args.get('q', default='', type=str)

    stmt = sa.select(Strecke) #alle Strecken; keinen Suchbegriff

    #Query falls es einen Suchbegriff gibt
    if query_term:
        stmt = stmt.where(
            sa.or_(
                Strecke.name.ilike(f'%{query_term}%'),
                Strecke.streckenId == query_term
            )
        )

    strecken = db.session.scalars(stmt).all() #DB-Abfrage ausführen

    #JSON vorbereiten; über alle Strecken iterieren
    items = []
    for s in strecken:
        startBahnhof, endBahnhof = s.start_end_bahnhoefe
        items.append({
            "streckeId": s.streckenId,
            "name": s.name,
            "startBahnhof": startBahnhof.bahnhofId,
            "endBahnhof": endBahnhof.bahnhofId
        })

    total_count = len(strecken) #Anzahl der Strecken bestimmen

    return jsonify({"total": total_count, "items": items}) #JSON zurückgeben

#Abschnitte einer bestimmten Strecke
@app.route('/strecken/<int:streckeId>/abschnitte', methods=['GET'])
def get_strecke_abschnitte_api(streckeId):
    #Strecke + alle dazugehörigen Daten laden
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
        abort(404) #404 Not Found

    #JSON vorbereiten -> Abschnitte in JSON-Format bringen
    items = []
    for reihenfolge_obj in strecke.reihenfolge:
        abschnitt = reihenfolge_obj.abschnitt
        start_bhf_name = abschnitt.startBahnhof.name
        end_bhf_name = abschnitt.endBahnhof.name

        items.append({
            "abschnittId": abschnitt.abschnittId,
            "reihenfolgeId": reihenfolge_obj.reihenfolge,
            "startBahnhofName": start_bhf_name,
            "endBahnhofName": end_bhf_name,
            "startBahnhofId": abschnitt.startBahnhofId,
            "endBahnhofId": abschnitt.endBahnhofId,
            "spurweite": abschnitt.spurweite,
            "laenge": abschnitt.laenge,
            "nutzungsentgelt": abschnitt.nutzungsentgelt,
            "maxGeschwindigkeit": abschnitt.max_geschwindigkeit
        })

    total_count = len(items) #Anzahl der abshcnitte bestimmen
    return jsonify({"total": total_count, "streckenname": strecke.name, "items": items}), 200 #JSON zurückgeben

#Warnungen
@app.route('/warnungen', methods=['GET'])
def get_warnung_api():
    query_term = request.args.get('q', default='', type=str)

    stmt = sa.select(Warnung) #alle Warnungen, falls es keine Suchoperator gibt

    #falls es Suchoperator gibt; nur diese Warnung zurückgeben
    if query_term:
        stmt = stmt.where(
            sa.or_(
                Warnung.bezeichnung.ilike(f'%{query_term}%'),
                Warnung.warnungId == query_term
            )
        )

    warnung = db.session.scalars(stmt).all() #Db-Abfrage durchführen

    #Warnungen in JSON-Format bringen
    items = []
    for w in warnung:
        items.append({
            "warnungId": w.warnungId,
            "bezeichnung": w.bezeichnung,
            "startZeit": w.startZeit,
            "endZeit": w.endZeit
        })
    total_count = len(warnung) #Anzahl der Warnungen bestimmen

    return jsonify({"total": total_count, "items": items}) #JSON zurückgeben



###################   interne   #############################

#damit Javascript auf die Koordinaten der Bahnhöfe zugreifen kann; für das Anzeigen der Abschnitte beim Hinzufügen
@app.route('/api/bahnhof/<int:bahnhof_id>')
def get_bahnhof_coords(bahnhof_id):
    #Speziallfall 0 ("Bitte bahnhof wählen) -> leeres JSOn zurückgeben
    if bahnhof_id == 0:
        return jsonify({}), 200

    bahnhof = Bahnhof.query.get(bahnhof_id) #ruft die Daten für den bestimmten Bahnhof ab

    #prüft, ob Bahnhof mit der Id in der DB gibt
    if bahnhof is None:
        return jsonify({'error': 'Bahnhof nicht gefunden'}), 404

    #gibt Daten zurück
    return jsonify({
        'id': bahnhof.bahnhofId,
        'latitude': bahnhof.latitude,
        'longitude': bahnhof.longitude
    })

#damit Javascript auf die Koordinaten der Bahnhöfe eines bestimmten Abschnitts zugreifen kann;
#für das Anzeigen der Abschnitte beim Hinzufügen (Warnung erstellen)
@app.route('/api/abschnitt/<int:abschnitt_id>')
def api_get_abschnitt_coords(abschnitt_id):
    #Abschnitt mit der ID aus der DB laden
    abschnitt = db.session.get(Abschnitt, abschnitt_id)

    #Start-und Endbahnhof
    startbahnhof = abschnitt.startBahnhof
    endbahnhof = abschnitt.endBahnhof

    #JSON erstellen und ans Frontend übergeben
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

#liefert die benötigten Daten für Strecken_add, Strecke_edit und Strecke_view
#Alle Bahnhöfe und Abschnitte werden geliefert
@app.route("/api/abschnitte_daten", methods=["GET"])
def api_abschnitte_daten():

    #Datenbankabfrage
    abschnitte = Abschnitt.query.options(
        joinedload(Abschnitt.startBahnhof),
        joinedload(Abschnitt.endBahnhof)
    ).join(
        Abschnitt.startBahnhof
    ).order_by(
        Abschnitt.spurweite,
        Bahnhof.name
    ).all()

    abschnitt_data = [] #Liste mit Abschnittsdaten
    bahnhoefe_map = {}  #Dictionary mit BahnhofId -> Name

    #Schleife über alle Abschnitte
    for a in abschnitte:
        start_name = a.startBahnhof.name if a.startBahnhof else "Unbekannt"
        end_name = a.endBahnhof.name if a.endBahnhof else "Unbekannt"

        abschnitt_data.append({
            "abschnittId": a.abschnittId,
            "name": f"{start_name} → {end_name} ({a.spurweite})",
            "startBahnhofId": a.startBahnhofId,
            "endBahnhofId": a.endBahnhofId,
            "spurweite": a.spurweite
        })

        #Directory füllen
        if a.startBahnhof:
            bahnhoefe_map[a.startBahnhof.bahnhofId] = start_name
        if a.endBahnhof:
            bahnhoefe_map[a.endBahnhof.bahnhofId] = end_name

    # JSON erstellen und ans Frontend übergeben
    return jsonify({
        'abschnitte': abschnitt_data,
        'bahnhoefe': bahnhoefe_map
    })

#### api by Moritz (fahrplan)

@app.route("/api/strecken-export", methods=["GET"])
def api_strecken_export():

    bahnhoefe = db.session.scalars(
        sa.select(Bahnhof)
    ).all()

    bahnhof_items = [
        {
            "id": b.bahnhofId,
            "name": b.name
        }
        for b in bahnhoefe
    ]

    abschnitte = db.session.scalars(
        sa.select(Abschnitt)
    ).all()

    abschnitt_items = [
        {
            "id": a.abschnittId,
            "startBahnhofId": a.startBahnhofId,
            "endBahnhofId": a.endBahnhofId,
            "spurweite": a.spurweite,
            "laenge": a.laenge,
            "nutzungsentgelt": a.nutzungsentgelt,
            "maxGeschwindigkeit": a.max_geschwindigkeit,
            "laenge": a.laenge,
        }
        for a in abschnitte
    ]

    strecken = db.session.scalars(
        sa.select(Strecke).options(
            selectinload(Strecke.reihenfolge)
        )
    ).all()

    strecken_items = []
    for s in strecken:
        strecken_items.append({
            "id": s.streckenId,
            "name": s.name,
            "abschnittIds": [
                r.abschnittId
                for r in sorted(s.reihenfolge, key=lambda x: x.reihenfolge)
            ]
        })

    return jsonify({
        "bahnhoefe": bahnhof_items,
        "abschnitte": abschnitt_items,
        "strecken": strecken_items
    }), 200