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
from sqlalchemy.orm import joinedload
from flask import jsonify

#############################################################
#################    Abschnitt   ############################
#############################################################

#Abschnittsübersicht
@app.route('/abschnitt') # Definiert die Route /abschnitt
@login_required #nur eingeloggte Benutzer können diese Seite aufrufen
def abschnitt(): # Funktion für die Abschnitt-Übersichtsseite

    #lädt alle Abschnitte aus der DB und sortiert sie nach Namen des Startbahnhofs
    posts = db.session.query(Abschnitt).join(Abschnitt.startBahnhof).order_by(Bahnhof.name).all()

    all_coords = [] #Liste für alle Koordinaten (zum Zentrieren der Map)
    section_groups = {} #Dictionary für Folium Feature Groups

    # Standartkoordinaten falls keine Bahnhöfe gibt (zentriert auf Österreich)
    fallback_lat, fallback_lon = 47.5162, 14.5501
    # Karte zentriert auf Österreich erstellen
    m = folium.Map(location=[fallback_lat, fallback_lon], zoom_start=7, height='100%')


    for abschnitt in posts: #Schleife über alle Abschnitte  aus der DB

        abschnitt_name = getattr(abschnitt, 'name') # Holt den Namen des Abschnitts
        startbahnhof = getattr(abschnitt, 'startBahnhof', None) # Holt den Startbahnhof des Abschnitts (oder None)
        endbahnhof = getattr(abschnitt, 'endBahnhof', None) # Holt den Endbahnhof des Abschnitts (oder None)


        bahnhoefe_zu_markieren = [] #Liste für Bahnhöfe die auf der Karte makiert werden sollten
        # wenn Startbahnhof existiert -> fügt Startbahnhof zu Marker-Liste hinzu
        if startbahnhof:
            bahnhoefe_zu_markieren.append(('Startbahnhof', startbahnhof)) #'blue'))
        # wenn Endbahnhof existiert -> fügt Endbahnhof zu Marker-Liste hinzu
        if endbahnhof:
            bahnhoefe_zu_markieren.append(('Endbahnhof', endbahnhof)) # 'blue'))

        #wenn es keine zu makierenden Bahnhöfe gibt -> diesen Abschnitt überspringen
        if not bahnhoefe_zu_markieren:
            continue

        #Erstellt eine Feature-Group für diesen Abschnitt
        group = folium.FeatureGroup(name=abschnitt_name)
        # Speichert die Group im Dictionary
        section_groups[abschnitt_name] = group
        # Fügt die Group zur Karte hinzu
        group.add_to(m)

        route_coords = [] # Liste für Koordinaten des Abschnitts

        for typ, b in bahnhoefe_zu_markieren: #Schleife über die zu makierenden Bahnhöfen

            #wenn es keine Koordinaten gibt -> Methode geocode_adress() (siehe Bahnhof Model in models.py) aufrufen um Adresse in Koordinaten umzuwandeln
            if not b.latitude or not b.longitude:
                b.geocode_address()

            #wenn es Koordinaten gibt -> fügt Koordinaten zur route_coord und all_coords hinzu
            if b.latitude and b.longitude:
                lat_lon = (b.latitude, b.longitude)
                route_coords.append(lat_lon)
                all_coords.append(lat_lon)

                #Erstellt die Marker für Start-und Endbahnhof
                marker = folium.Marker(
                    lat_lon,
                    tooltip=f"{typ}: {b.name}",
                    popup=f"Abschnitt: {abschnitt_name}<br>{typ}: {b.name}<br>Adresse: {b.adresse}",

                )

                marker.add_to(group) # Fügt Marker zur Feature Group hinzu

        #wenn 2 Bahnhöfe mit Koordinaten für den Abschnitt gibt -> zeichnet Verbindungslinie zwischen den beiden
        if len(route_coords) == 2:
            folium.PolyLine(
                route_coords,
                color='blue',
                weight=4,
                opacity=0.7,
                tooltip=f"Abschnitt: {abschnitt_name}"
            ).add_to(group) # Fügt die Linie zur Feature-Group hinzu


    db.session.commit() #speichert die Änderungen in der DB (vorallem die berechneten Koordinaten, falls sie noch nicht in der DB waren)

    #wenn es Koordinaten gibt
    if all_coords:

        #berechnet den Durchschnitts-Breitengrad und Durchschnittslängengrad
        center_lat = sum(lat for lat, lon in all_coords) / len(all_coords)
        center_lon = sum(lon for lat, lon in all_coords) / len(all_coords)

        m.location = [center_lat, center_lon] #Karte wird auf den Durchschnittswerten zentriert

    folium.LayerControl().add_to(m) # Fügt Layer-Control zur Karte hinzu (Checkbox zum Ein-und Ausblenden der Ebenen)


    map_html = m._repr_html_() #generiert den HTML-Code der Karte

    return render_template( # Rendert das Template
        'abschnitt.html', #Name des Templates
        title='Abschnitte', #Seitentitel
        posts=posts, #übergibt alle Abschnitte
        map_html=map_html, #übergibt den Karten-HTML-Code
        role=current_user.role #übergibt die aktuelle Benutzerrolle
    )

#Abschnitte hinzufügen
@app.route('/abschnitt/add', methods=['GET', 'POST'])
@login_required
def abschnitt_add():

    form = AbschnittForm() # Erstellt eine Instanz des Abschnitt-Formulars
    # Standard-Option für Startbahnhof-Dropdown
    standard_option_start = [(0, 'Bitte wählen Sie einen Startbahnhof aus')]
    # Standard-Option für Start-Dropdown
    standard_option_end = [(0, 'Bitte wählen Sie einen Endbahnhof aus')]
    #Lädt alle Bahnhöfe aus der DB
    bahnhoefe = Bahnhof.query.order_by(Bahnhof.name).all()
    #Füllt die Dropdowns StartBahnhof und Endbahnhof mit Bahnhöfen
    bahnhof_choices = [(b.bahnhofId, b.name) for b in bahnhoefe]
    form.startBahnhof.choices = standard_option_start + bahnhof_choices
    form.endBahnhof.choices = standard_option_end + bahnhof_choices

    #die Auswahlmöglichkeiten für die Spurweiten
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

#Abschnitte bearbeiten
@app.route("/abschnitt/edit/<int:abschnitt_id>", methods=["GET", "POST"])
@login_required
def edit_abschnitt(abschnitt_id):

    # Lädt den Abschnitt mit der angegebenen ID aus der DB
    abschnitt = db.session.get(Abschnitt, abschnitt_id)

    # Prüfung: Ist der Abschnitt in einer Strecke?
    abschnitt_in_strecke = bool(abschnitt.strecken_abschnitt_ref)

    # Erstellt Formular-Instanz
    form = AbschnittForm(
        obj=abschnitt, # Befüllt Formular mit existierenden Daten
        #um überprüfen zu können ob der USer die Bahnhöfe gändert hat -> Abschnitt breiets gibt in der DB
        original_start_id=abschnitt.startBahnhofId, #übergibt die ursprüngliche ID des Starbahnhofs
        original_end_id=abschnitt.endBahnhofId #übergibt die ursprüngliche ID des Starbahnhofs
    )

    standard_option_bahnhof = [(0, 'Bitte wählen Sie einen Bahnhof')] #Standartoption
    bahnhoefe = Bahnhof.query.order_by(Bahnhof.name).all() #ruft alle Bahnhofsnamen aus der DB
    bahnhof_choices = [(b.bahnhofId, b.name) for b in bahnhoefe] # Erstellt Dropdown-Optionen

    form.startBahnhof.choices = standard_option_bahnhof + bahnhof_choices #setzt Startbahnhof-Dropdownoptionen
    form.endBahnhof.choices = standard_option_bahnhof + bahnhof_choices #setzt Endbahnhof-Dropdownoptionen

    #Spurweiten-Dropdownoptionen
    spurweiten_optionen = [
        (0, 'Bitte wählen Sie eine Spurweite'),
        (1435, 'Normalspur (1435 mm)'),
        (1000, 'Schmalspur (1000 mm)')
    ]
    form.spurweite.choices = spurweiten_optionen #setzt Spurweiten-Dropdownop

    #setzt aktuelle Bahnhofe als ausgewählt
    form.startBahnhof.data = abschnitt.startBahnhofId
    form.endBahnhof.data = abschnitt.endBahnhofId

    if request.method == 'GET': #wenn Seite das erste Mal aufgerufen wird

        #wenn es keinen Startbahnhof gibt -> setze Dropdownauswahl auf Standardoption
        if form.startBahnhof.data is None:
            form.startBahnhof.data = 0
        # wenn es keinen Endbahnhof gibt -> setze Dropdownauswahl auf Standardoption
        if form.endBahnhof.data is None:
            form.endBahnhof.data = 0

        # wenn es keine Spurweite gibt -> setze Dropdownauswahl auf Standardoption
        if form.spurweite.data is None:
            form.spurweite.data = 0

    if form.validate_on_submit(): # Wenn Formular abgesendet und valide ist
        #aktualisiert Daten
        abschnitt.spurweite = form.spurweite.data
        abschnitt.max_geschwindigkeit = form.max_geschwindigkeit.data
        abschnitt.laenge = form.laenge.data
        abschnitt.nutzungsentgelt = form.nutzungsentgelt.data

        # Nur ändern wenn nicht in Strecke
        if not abschnitt_in_strecke:
            abschnitt.startBahnhofId = form.startBahnhof.data
            abschnitt.endBahnhofId = form.endBahnhof.data

        try: # Versuche zu speichern
            db.session.commit()
            flash(f"Abschnitt aktualisiert", "success")
            return redirect(url_for("abschnitt"))
        except Exception as e: #wenn Fehler auftreten
            db.session.rollback()
            print(f"Fehler beim Editieren: {e}") #Fehlermeldung in der Console
            flash("Fehler beim Speichern", "danger") # Fehlermeldung für Benutzer


    return render_template(
        "abschnitt_edit.html",
        form=form,
        abschnitt=abschnitt,
        abschnitt_in_strecke=abschnitt_in_strecke,
        title='Abschnitt bearbeiten'
    )

#Abschnitte löschen
@app.route("/abschnitt/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_abschnitt():
    ids = request.form.getlist("abschnitt_ids") #holt die IDs der zu löschenden Abschnitte

    deleted_count = 0 #zählt wie viele Abschnitte gelöscht werden
    blocked_names = [] #sammelt die Abschnitte, die nicht gelöscht werden können (Abschnitt in Strecke)

    if not ids: # Wenn keine IDs zum Löschen ausgewählt wurden
        flash("Keine Abschnitte ausgewählt.", "error") #Fehlermeldung
        return redirect(url_for('abschnitt')) #zurück zur Abschnittsübersicht

    for aid in ids: # Schleife durch alle ausgewählten IDs
        try:
            # Erstellt Query um Abschnitt laden
            abschnitt_query = (
                sa.select(Abschnitt)
                .where(Abschnitt.abschnittId == int(aid))
            )
            # Führt Query aus, gibt ein Objekt oder None zurück
            abschnitt = db.session.execute(abschnitt_query).scalar_one_or_none()

            if abschnitt: #wenn es Abschnitt gibt
                # Prüfen ob der Abschnitt in einer Strecke verwendet wird; zählt wie oft es vorkommt in einer Strecke
                verknuepfung_query = (
                    sa.select(sa.func.count())
                    .select_from(Reihenfolge)
                    .where(Reihenfolge.abschnittId == int(aid))
                )
                count = db.session.execute(verknuepfung_query).scalar() # Führt Query aus, gibt Anzahl zurück

                #wenn Zähler größer 0 -> dann wird es in einer STrecke verwendet und der Abschnitt zu blocked_names hinzugefügt
                if count > 0:
                    blocked_names.append(abschnitt.name)
                else:
                    # Löschen, falls keine Verknüpfung gefunden wurde
                    db.session.delete(abschnitt)
                    deleted_count += 1 #Löschcounter +1

        except Exception as e: # Wenn Fehler auftritt
            print(f"Fehler beim Laden von Abschnitt {aid}: {e}")
            continue

    if deleted_count > 0: #wenn mindestens 1 Abschnitt gelöscht wurde
        db.session.commit() # Speichert Änderungen
        flash(f"{deleted_count} Abschnitt/Abschnitte erfolgreich gelöscht.", "success") #Erfolgsmeldung

    # Wenn Abschnitte nicht gelöscht werden konnten -> gibt diese aus als Fehlermeldung
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

#Streckenübersicht
@app.route('/', methods=['GET', 'POST'])
@app.route('/strecke', methods=['GET', 'POST'])
@login_required
def strecke():
    #lädt alle STrecken aus der DB
    alle_strecken = Strecke.query.order_by(Strecke.name).all()

    strecken_daten = [] #Liste für Strecken-Daten
    all_coords = [] #Liste für die Koordinaten
    section_groups = {} # Dictionary für Feature Groups

    #erstellt eine Map mit Standard-Koordinaten (zentriert auf Österreich)
    fallback_lat, fallback_lon = 47.5162, 14.5501
    m = folium.Map(location=[fallback_lat, fallback_lon], zoom_start=7, height='100%')

    for strecke in alle_strecken: #Schleife über alle Strecken

        # Holt Start- und Endbahnhof der Strecke
        start_bhf, end_bhf = strecke.start_end_bahnhoefe

        # Fügt Strecken-Daten zur Liste hinzu
        strecken_daten.append({
            'id': strecke.streckenId,
            'name': strecke.name,
            'start_bahnhof': start_bhf.name if start_bhf else 'N/A',
            'end_bahnhof': end_bhf.name if end_bhf else 'N/A',
            'anzahl_abschnitte': len(strecke.reihenfolge)
        })

        # Karten-Visualisierung für diese Strecke
        if start_bhf or end_bhf: # Wenn mindestens ein Bahnhof vorhanden ist
            group = folium.FeatureGroup(name=strecke.name) #Feature-Group für diese Strecke erstellen
            section_groups[strecke.name] = group #speichert im Dictionary
            group.add_to(m) #fügt es zur karte hinzu

            route_coords = [] # Liste für Strecken-Koordinaten

            # Alle Abschnitte dieser Strecke durchgehen (über Reihenfolge-Objekte)
            for reihenfolge in strecke.reihenfolge:
                abschnitt = reihenfolge.abschnitt  # Holt den zugehörigen Abschnitt

                # Wenn kein Abschnitt vorhanden -> überspringe
                if not abschnitt:
                    continue

                # Startbahnhof des Abschnitts
                if abschnitt.startBahnhof:
                    #falls es Längen- oder Breitengrad des Startbahnhofs nicht gibt in der DB -> Koordinaten berechnen aus Adresse
                    if not abschnitt.startBahnhof.latitude or not abschnitt.startBahnhof.longitude:
                        abschnitt.startBahnhof.geocode_address()

                    #wenn Startbahnhof Koordinaten hat
                    if abschnitt.startBahnhof.latitude and abschnitt.startBahnhof.longitude:
                        lat_lon = (abschnitt.startBahnhof.latitude, abschnitt.startBahnhof.longitude) # Tuple mit Koordinaten

                        #wenn Tuple noch nicht in Strecken-Koordinaten ist -> Strecken-Koordinaten und alle Koordinaten Liste anfügen
                        if lat_lon not in route_coords:
                            route_coords.append(lat_lon)
                            all_coords.append(lat_lon)

                            #Marker für Startbahnhof des Abschnitts erstellen (falls Startbahnhof der Strecke in grün, sonst blau)
                            folium.Marker(
                                lat_lon,
                                tooltip=abschnitt.startBahnhof.name,
                                popup=f"Strecke: {strecke.name}<br>Bahnhof: {abschnitt.startBahnhof.name}<br>Adresse: {abschnitt.startBahnhof.adresse}",
                                icon=folium.Icon(color='green' if abschnitt.startBahnhof == start_bhf else 'blue')
                            ).add_to(group)

                # Endbahnhof des Abschnitts
                if abschnitt.endBahnhof:
                    # falls es Längen- oder Breitengrad des Endbahnhofs nicht gibt in der DB -> Koordinaten berechnen aus Adresse
                    if not abschnitt.endBahnhof.latitude or not abschnitt.endBahnhof.longitude:
                        abschnitt.endBahnhof.geocode_address()

                    # wenn Startbahnhof Koordinaten hat
                    if abschnitt.endBahnhof.latitude and abschnitt.endBahnhof.longitude:
                        lat_lon = (abschnitt.endBahnhof.latitude, abschnitt.endBahnhof.longitude) # Tuple mit Koordinaten

                        # wenn Tuple noch nicht in Strecken-Koordinaten ist -> Strecken-Koordinaten und alle Koordinaten Liste anfügen
                        if lat_lon not in route_coords:
                            route_coords.append(lat_lon)
                            all_coords.append(lat_lon)

                            # Marker für Endbahnhof des Abschnitts erstellen (falls Endbahnhof der Strecke in rot, sonst blau)
                            folium.Marker(
                                lat_lon,
                                tooltip=abschnitt.endBahnhof.name,
                                popup=f"Strecke: {strecke.name}<br>Bahnhof: {abschnitt.endBahnhof.name}<br>Adresse: {abschnitt.endBahnhof.adresse}",
                                icon=folium.Icon(color='red' if abschnitt.endBahnhof == end_bhf else 'blue')
                            ).add_to(group)

            # Polylinie (Verbindungslinie zwischen den Bahnhöfen) für die gesamte Strecke zeichnen
            if len(route_coords) >= 2:
                folium.PolyLine(
                    route_coords,
                    color='blue',
                    weight=4,
                    opacity=0.7,
                    tooltip=f"Strecke: {strecke.name}"
                ).add_to(group)

    db.session.commit() #Änderungen speichern

    # Karte zentrieren
    if all_coords:
        # Koordinatendurchscnitt berechnen
        center_lat = sum(lat for lat, lon in all_coords) / len(all_coords)
        center_lon = sum(lon for lat, lon in all_coords) / len(all_coords)
        m.location = [center_lat, center_lon] #Karte auf Koordinatendurchschnitt zentrieren

    folium.LayerControl().add_to(m) # Fügt Layer-Control hinzu
    map_html = m._repr_html_() # Generiert HTML-Code für die Map

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
    form = StreckenForm() # Erstellt Formular-Instanz

    if form.validate_on_submit(): # Wenn Formular abgesendet und valide

        gewaehlte_ids_str = request.form.get('abschnitt_ids')  # Holt Abschnitt-IDs aus dem Formular

        gewaehlte_ids = [] # Liste für IDs

        # Wenn IDs vorhanden sind
        if gewaehlte_ids_str:
            try:
                # Teilt String bei Kommas und konvertiert zu Integers
                gewaehlte_ids = [int(id_str) for id_str in gewaehlte_ids_str.split(',') if id_str]

            except ValueError: #bei auftreten eines Fehlers -> zeigt Fehlermeldung
                flash('Fehler: Ungültiges Format der Abschnitts-IDs.', 'danger')
                return render_template("strecke_add.html", form=form)

        #wenn keine Strecke ausgewählt wird -> Fehlermeldung anzeigen
        if not gewaehlte_ids:
            flash('Bitte definieren Sie mindestens einen Abschnitt für die Strecke.', 'danger')
            return render_template("strecke_add.html", form=form)

        abschnitte_in_reihenfolge = [] #Liste für Abschnitte in Reihenfolge

        for abschnitt_id in gewaehlte_ids:#Schleife über alle ausgewählten AbschnittsIDs
            abschnitt = Abschnitt.query.get(abschnitt_id) # Lädt Abschnitt aus DB
            # Wenn Abschnitt existiert -> fügt zur Liste hinzu
            if abschnitt:
                abschnitte_in_reihenfolge.append(abschnitt)
            #sonst gibt Fehlermeldung aus
            else:
                print(f"WARNUNG: Abschnitts-ID {abschnitt_id} nicht gefunden.")


        validierung_erfolgreich = True #initialisiert Variable validierung_erfolgreich mit True

        for i in range(1, len(abschnitte_in_reihenfolge)): # Schleife durch Abschnitte (ab dem zweiten)
            vorheriger_abschnitt = abschnitte_in_reihenfolge[i - 1] #vorheriger Abschnitt
            aktueller_abschnitt = abschnitte_in_reihenfolge[i] #Aktueller Abschnitt

            #Falls Endbahnhof des vorherigen Abschnitts nicht ident mit dem Startbahnhof des aktuellen Asbchnitts ist
            #-> Fehlermeldung + validierung_erfolgreich wird auf falsch gesetzt
            if vorheriger_abschnitt.endBahnhofId != aktueller_abschnitt.startBahnhofId:
                flash(
                    f'Fehler: Die Abschnitte sind nicht zusammenhängend. '
                    f'Ende von "{vorheriger_abschnitt.name}" ist nicht Start von "{aktueller_abschnitt.name}".',
                    'danger'
                )
                validierung_erfolgreich = False
                break

        #Wenn Validierung fehlgeschlagen ist -> zeigt Formular erneut
        if not validierung_erfolgreich:
            return render_template("strecke_add.html", form=form)

        # Erstellt neue Strecke
        neue_strecke = Strecke(
            name=form.name.data, #setzt Namen
        )

        db.session.add(neue_strecke) #speichert neue Strecke in der DB


        if abschnitte_in_reihenfolge: # Wenn Abschnitte vorhanden
            #Schleife über alle Abschnitte
            for i, abschnitt in enumerate(abschnitte_in_reihenfolge):
                #erstellt für jeden Abschnitt ein Reihenfolge-Objekt
                reihenfolge_objekt = Reihenfolge(
                    abschnitt=abschnitt,
                    reihenfolge=i + 1 #Position des Abschnitt in der Strecke
                )


                neue_strecke.reihenfolge.append(reihenfolge_objekt) # Fügt zur Strecke hinzu


        db.session.commit() #Änderungen speichern

        flash(f'Strecke "{neue_strecke.name}" wurde gespeichert!', 'success') #Erfolgsnachricht
        return redirect(url_for("strecke"))


    return render_template(
        "strecke_add.html",
        form=form,
        api_url=url_for('api_abschnitte_daten'),
        title='Strecke hinzufügen',
    )

#Strecke löschen
@app.route("/strecke/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_strecke():
    ids = request.form.getlist("strecke_ids") #holt Liste der IDs der zu löschenden Strecken

    deleted_count = 0 #Zähler, der zählt wie viele Strecken gelöscht wurden

    #wenn keine Ids ausgewählt wurden -> Fehlermeldung anzeigen
    if not ids:
        flash("Keine Strecken ausgewählt.", "error")
        return redirect(url_for('strecke'))

    for bid in ids: #Schleife über alle Strecken
        try:
            #Query erstellen
            strecke_query = (
                sa.select(Strecke)
                .where(Strecke.streckenId == int(bid))
            )
            strecke = db.session.execute(strecke_query).scalar_one_or_none() #Query ausführen

            #wenn Strecke gefunden wurde -> löschen + Löschzähler +1
            if strecke:
                db.session.delete(strecke)
                deleted_count += 1

        except Exception as e: #falls Fehler auftreten -> Fehlermeldung
            print(f"Fehler beim Laden von Strecke {bid}: {e}")
            continue

    # wenn mindestens 1 Strecke gelöscht wurde -> Erfolgsnachricht
    if deleted_count > 0:
        db.session.commit()
        flash(f"{deleted_count} Strecke/Strecken erfolgreich gelöscht.", "success")


    return redirect(url_for('strecke'))

#Strecke bearbeiten
@app.route('/strecke/edit/<int:strecke_id>', methods=['GET', 'POST'])
@login_required
def strecke_edit(strecke_id):

    strecke = Strecke.query.get_or_404(strecke_id) # Lädt Strecke oder 404-Fehler

    # Form mit dem originalen Namen initialisieren
    form = StreckenForm(original_name=strecke.name)

    if form.validate_on_submit(): # Wenn Formualr abgesendet und validiert

        strecke.name = form.name.data #aktualisert Namen

        abschnitt_ids = request.form.get('abschnitt_ids', '') # Holt Abschnitt-IDs
        if abschnitt_ids:
            # Wandelt den String in eine Liste von Integern um und entfernt leere Einträge
            ids = [int(x) for x in abschnitt_ids.split(',') if x]

            #Löscht alte Reihenfolge-Einträge
            Reihenfolge.query.filter_by(streckeId=strecke.streckenId).delete()

            #für jeden Abschnitt mit Position
            for position, abschnitt_id in enumerate(ids, start=1):
                #erstellt neue Reihenfolge-Objekt
                neue_reihenfolge = Reihenfolge(
                    streckeId=strecke.streckenId,
                    abschnittId=abschnitt_id,
                    reihenfolge=position
                )
                db.session.add(neue_reihenfolge) #fügt in DB hinzu

        db.session.commit() #speichert Änderungen
        flash('Strecke erfolgreich aktualisiert!', 'success') #Erfolgsmeldung
        return redirect(url_for('strecke'))

    if request.method == 'GET': # Beim ersten Aufruf
        form.name.data = strecke.name # Setzt Namen im Formular

    # Versuche Abschnitte zu laden
    try:
        existing_abschnitte = [
            r.abschnitt.abschnittId
            for r in sorted(strecke.reihenfolge, key=lambda x: x.reihenfolge)
            if r.abschnitt
        ]
    #falls Fehler auftreten -> Fehlermeldung
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

#Streckenübersichtsseite für den Mitarbeiter
@app.route('/strecke/view/<int:strecke_id>', methods=['GET'])
@login_required
def strecke_view(strecke_id):
    strecke = Strecke.query.get_or_404(strecke_id) # Lädt Strecke oder 404

    # Abschnitt-IDs der Strecke extrahieren
    existing_abschnitte = [
        r.abschnitt.abschnittId
        for r in sorted(strecke.reihenfolge, key=lambda x: x.reihenfolge)
        if r.abschnitt
    ]

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

#Warnungsübersicht
@app.route('/warnung', methods=['GET', 'POST'])
@login_required
def warnung():
    # Alle Warnungen aus der DB laden
    posts = Warnung.query.order_by(Warnung.bezeichnung).all()

    all_coords = [] #Liste für Koordinaten
    warning_groups = {} #Feature-Groups

    #erstellt Karte mit Standard-Koordinaten (zentriert auf Österreich)
    fallback_lat, fallback_lon = 47.5162, 14.5501
    m = folium.Map(location=[fallback_lat, fallback_lon], zoom_start=7, height='100%')

    for warnung in posts: #Schleife über alle Warnungen
        # Feature Group für jede Warnung erstellen + hinzufügen zu Karte
        group = folium.FeatureGroup(name=warnung.bezeichnung)
        warning_groups[warnung.bezeichnung] = group
        group.add_to(m)

        # Alle Abschnitte dieser Warnung durchgehen (M2M-Beziehung)
        for abschnitt in warnung.abschnitte:
            route_coords = [] #Koordinaten-Liste

            # Startbahnhof des Abschnitts
            if abschnitt.startBahnhof: #falls es Startbahnhof für den Abschnitt gibt
                #wenn der Starbahnhof nicht sowohl Breitengrad als auch Längegrad hat -> Koordinaten werden aus Adresse ermittelt
                if not abschnitt.startBahnhof.latitude or not abschnitt.startBahnhof.longitude:
                    abschnitt.startBahnhof.geocode_address()
                #wenn Koordinaten vorhanden -> tuple erstellen & zu Route und globaler Liste hinzufügen
                if abschnitt.startBahnhof.latitude and abschnitt.startBahnhof.longitude:
                    lat_lon = (abschnitt.startBahnhof.latitude, abschnitt.startBahnhof.longitude)
                    route_coords.append(lat_lon)
                    all_coords.append(lat_lon)
                    # orangen Marker für Startbahnhof erstellen
                    folium.Marker(
                        lat_lon,
                        tooltip=abschnitt.startBahnhof.name,
                        popup=f"Bahnhof: {abschnitt.startBahnhof.name}",
                        icon=folium.Icon(color='orange', icon='exclamation-triangle', prefix='fa')
                    ).add_to(group)

            # Endbahnhof des Abschnitts
            if abschnitt.endBahnhof: #falls es Endbahnhof für den Abschnitt gibt
                # wenn der Endbahnhof nicht sowohl Breitengrad als auch Längegrad hat -> Koordinaten werden aus Adresse ermittelt
                if not abschnitt.endBahnhof.latitude or not abschnitt.endBahnhof.longitude:
                    abschnitt.endBahnhof.geocode_address()
                # wenn Koordinaten vorhanden -> tuple erstellen & zu Route und globaler Liste hinzufügen
                if abschnitt.endBahnhof.latitude and abschnitt.endBahnhof.longitude:
                    lat_lon = (abschnitt.endBahnhof.latitude, abschnitt.endBahnhof.longitude)
                    route_coords.append(lat_lon)
                    all_coords.append(lat_lon)
                    #orangen Marker für Endbahnhof erstellen
                    folium.Marker(
                        lat_lon,
                        tooltip=abschnitt.endBahnhof.name,
                        popup=f"Bahnhof: {abschnitt.endBahnhof.name}",
                        icon=folium.Icon(color='orange', icon='exclamation-triangle', prefix='fa')
                    ).add_to(group)

            # Polylinie für jeden betroffenen Abschnitt (orange für Warnung)
            if len(route_coords) == 2:
                folium.PolyLine(
                    route_coords,
                    color='orange',
                    weight=5,
                    opacity=0.8,
                    tooltip=f"<b>Warnung:</b> {warnung.bezeichnung}<br><b>Abschnitt:</b> {abschnitt.name}"
                ).add_to(group)

    db.session.commit() #Änderungen in DB spiechern

    # Karte zentrieren
    if all_coords:
        #Durchnitt der Breiten-und Längengrade berechne -> auf den Durchschnittswert Karte zentrieren
        center_lat = sum(lat for lat, lon in all_coords) / len(all_coords)
        center_lon = sum(lon for lat, lon in all_coords) / len(all_coords)
        m.location = [center_lat, center_lon]

    folium.LayerControl().add_to(m) # Layer-Control zu Karte hinzufügen
    map_html = m._repr_html_() #HTML-Repräsentation für Karte

    return render_template(
        'warnung.html',
        posts=posts,
        map_html=map_html,
        role=current_user.role,
        title='Warnungen',
    )

@app.route("/warnung/add", methods=["GET", "POST"])
@login_required
def warnung_add():
    form = WarnungForm() #Formularinstanz erstellen
    #setzt Dropdownchoices für Abschnitte
    form.abschnitt.choices = [(a.abschnittId, a.name) for a in Abschnitt.query.all()]

    if form.validate_on_submit(): # wenn Formular abgesendet wird (auf speichern geklickt wird)

        # Neue Warnung erstellen
        warnung = Warnung(
            bezeichnung=form.bezeichnung.data,
            beschreibung=form.beschreibung.data,
            startZeit=form.startZeit.data,
            endZeit=form.endZeit.data or None
        )

        db.session.add(warnung) #Warnunng zur DB-Session hinzufügen
        db.session.commit() #Speichern

        # Ausgewählte Abschnitte laden
        gewaehlte_ids = form.abschnitt.data #hohlt ausgewählte IDs
        #wenn es keine Liste ist wird es in eine Liste umgewandelt
        if not isinstance(gewaehlte_ids, list):
            gewaehlte_ids = [gewaehlte_ids]


        if gewaehlte_ids: #wenn IDs vorhanden sind
            #Query erstellen
            abschnitte = Abschnitt.query.filter(
                Abschnitt.abschnittId.in_(gewaehlte_ids)
            ).all()

            warnung.abschnitte.clear() #alte Vernküpfungen löschen
            for abschnitt in abschnitte: #für jeden Abschnitt
                warnung.abschnitte.append(abschnitt) #Verknüpfen

        db.session.commit() #speichern

        flash(f'Warnung "{warnung.bezeichnung}" wurde gespeichert!', 'success') #Erfolgsmeldung
        return redirect(url_for("warnung"))

    return render_template("warnung_add.html", form=form, title='Warnung hinzufügen',)

#Warnungen löschen
@app.route("/warnung/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_warnung():
    ids = request.form.getlist("warnung_ids") #Ids holen

    deleted_count = 0 #Zähler, der zählt wie viele Warnungen gelöscht wurden

    #wenn keine Ids ausgewählt wurden vom User -> Fehlermeldung
    if not ids:
        flash("Keine Warnungen ausgewählt.", "error")
        return redirect(url_for('warnung'))

    for bid in ids: #Schleife über alle ausgewählten Ids

        try:
            #Query erstellen
            warnung_query = (
                sa.select(Warnung)
                .where(Warnung.warnungId == int(bid))
            )
            warnung = db.session.execute(warnung_query).scalar_one_or_none() #Query ausführen

            if warnung: #wenn es Warnung in Db gibt diese löschen + delete_count um 1 erhöhen
                db.session.delete(warnung)
                deleted_count += 1

        except Exception as e: #falls Fehler passiert -> Fehlermeldung
            print(f"Fehler beim Laden von Warnung {bid}: {e}")
            continue


    if deleted_count > 0: #wenn deleted_count größer 0 ist (also mindestens 1 Warnung gelöscht wurde -> Erfolgsnachricht
        db.session.commit() #Speicehrn
        flash(f"{deleted_count} Warnung/Warnungen erfolgreich gelöscht.", "success")


    return redirect(url_for('warnung'))

#Warnungen bearbeiten
@app.route("/warnung/edit/<int:warnung_id>", methods=["GET", "POST"])
@login_required
def edit_warnung(warnung_id):
    warnung = db.session.get(Warnung, warnung_id) #lädt Warnung aus DB

    #wenn Warnung in DB nicht gefunden wurde -> Fehlermeldung
    if not warnung:
        flash("Warnung nicht gefunden", "danger")
        return redirect(url_for("warnung"))

    form = WarnungForm(obj=warnung) #befüllt das Formular

    abschnitte_alle = Abschnitt.query.join(Abschnitt.startBahnhof).order_by(Bahnhof.name).all() #lädt alle Abschnitte
    abschnitt_choices = [(a.abschnittId, a.name) for a in abschnitte_alle] #Dropdown-Optionen
    form.abschnitt.choices = abschnitt_choices #setzt Dropdown-Optionen

    #wird aufgerufen wenn der User die Seite zum ersten Mal aufruft
    if request.method == 'GET':
        aktuelle_abschnitte_ids = [a.abschnittId for a in warnung.abschnitte] #erstellt Liste der verknüpften Abschnitte
        form.abschnitt.data = aktuelle_abschnitte_ids #Setzt als ausgewählt im Formular

    if form.validate_on_submit(): #beim Abschicken des Formulars

        form.populate_obj(warnung) #Aktualisiert Warnung mit Formular-Daten

        warnung.abschnitte.clear() #löscht alle vorhandenen Verbindungen

        #speichert die neuen Abschnitte
        neue_abschnitt_ids = form.abschnitt.data

        #für jeden ausgewählten Abschnitt -> falls vorhanden mit Warnung verknüpfen
        for abschnitt_id in neue_abschnitt_ids:
            abschnitt_obj = db.session.get(Abschnitt, abschnitt_id)
            if abschnitt_obj:
                warnung.abschnitte.append(abschnitt_obj)

        try: #versuchen die Änderungen zu Speichern -> Erfolgsnachricht
            db.session.commit()
            flash(f"Warnung {warnung.bezeichnung} aktualisiert", "success")
            return redirect(url_for("warnung"))
        except Exception as e: #falls Fehler auftreten -> Rollback + Fehlermeldung
            db.session.rollback()
            flash(f"Fehler beim Speichern der Warnung: {e}", "danger")


    return render_template("warnung_edit.html", form=form, warnung=warnung, title='Warnung bearbeiten',)



#############################################################
#################    Bahnhof     ############################
#############################################################

#Bahnhof hinzufügen
@app.route("/bahnhof/add", methods=["GET", "POST"])
@login_required
def bahnhof_add():
    form = BahnhofForm() #Erstellt Formular
    if form.validate_on_submit(): #wenn Formular abgeschickt wird
        # Neuer Bahnhof wird erstellt
        bahnhof = Bahnhof(name=form.name.data, adresse=form.adresse.data)

        #Aus Adresse Koordinaten ermitteln
        bahnhof.geocode_address()

        #Bahnhöfe in DB speichern
        db.session.add(bahnhof)
        db.session.commit()

        #Erfolgsmeldung
        flash(f'Bahnhof {bahnhof.name} wurde gespeichert!', 'success')
        return redirect(url_for("bahnhof"))
    return render_template("bahnhof_add.html", form=form, title='Bahnhof hinzufügen',)

#Bahnhofsübersicht
@app.route('/bahnhof', methods=['GET', 'POST'])
@login_required
def bahnhof():
    #Alle Bahnhöfe aus der DB laden
    posts = Bahnhof.query.order_by(Bahnhof.name).all()

    #Wenn es Bahnhöfe gibt, wird eine Karte erstellt
    if posts:
        for b in posts: #Schleife über alle Bahnhöfe aus der DB
            if not b.latitude or not b.longitude: #falls es fehlt wird der Breiten -oder Längengrad noch bestimmt
                b.geocode_address() #ruft Methode im models.py auf
        db.session.commit() #speichern

        #Mittelpunkt berechnen für die Längengrade und Breitengrade
        center_lat = sum(b.latitude for b in posts) / len(posts)
        center_lon = sum(b.longitude for b in posts) / len(posts)

        #Folium-Karte erstellen (Mittelpunkt ist der berechnete Durchschnittswert für Breiten- und Längengrad)
        m = folium.Map(location=[center_lat, center_lon], width='100%', height='100%', zoom_start=7)

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
        title='Bahnhöfe',
        posts=posts,
        map_html=map_html,
        role=current_user.role
    )

#Bahnhof bearbeiten
@app.route("/bahnhof/edit/<int:bahnhof_id>", methods=["GET", "POST"])
@login_required
def edit_bahnhof(bahnhof_id):
    bahnhof = db.session.get(Bahnhof, bahnhof_id) #Bahnhofsdaten aus der DB laden

    #falls der Bahnhof mit der Id nicht gefunden werden konnte -> Fehlermeldung
    if not bahnhof:
        flash("Bahnhof nicht gefunden.", "error")
        return redirect(url_for("bahnhof"))

    # Formular erstellen und mit den vorhandenen gespeicherten Daten füllen
    form = BahnhofForm(
        obj=bahnhof,
        original_name=bahnhof.name,
        original_adresse=bahnhof.adresse
    )

    if form.validate_on_submit(): #wenn Formular abgesendet wird
        form.populate_obj(bahnhof) #aktualisiert Bahnhof
        bahnhof.latitude = request.form.get("latitude") #setzt Breitengrad
        bahnhof.longitude = request.form.get("longitude") #setzt Längengrad
        db.session.commit() #speichern
        flash(f"Bahnhof '{bahnhof.name}' wurde aktualisiert.", "success") #Efolgsmeldung
        return redirect(url_for("bahnhof")) #wird wieder zurück zur Übersichtsseite geleitet

    return render_template("bahnhof_edit.html", form=form, bahnhof=bahnhof, title='Bahnhof bearbeiten',)

#Bahnhof löschen
@app.route("/bahnhof/delete_multiple", methods=["POST"])
@login_required
def delete_multiple_bahnhof():
    ids = request.form.getlist("bahnhof_ids") #holt IDs der zu löschenden Bahnhöfe

    deleted_count = 0 #Löschzähler, der zählt wie viele Bahnhöfe gelöscht wurden
    blocked_names = [] #Liste, die die geblockten Bahnhofsnamen speichert (Bahnhof in einem Abschnitt verwendet)

    #wenn keine Bahnhöfe ausgewählt wurden -> Fehlermeldung
    if not ids:
        flash("Keine Bahnhöfe ausgewählt.", "error")
        return redirect(url_for('bahnhof'))

    for bid in ids: #Schleife durchläuft alle ausgewählten Bahnhöfe
        try:
            #Query erstellen (lädt Bahnhof mit der Id bid und die dazugehörigen Abschnitte
            bahnhof_query = (
                sa.select(Bahnhof)
                .where(Bahnhof.bahnhofId == int(bid))
                .options(
                    selectinload(Bahnhof.start_abschnitte),
                    selectinload(Bahnhof.end_abschnitte)
                )
            )
            #Query ausführen
            bahnhof = db.session.execute(bahnhof_query).scalar_one_or_none()

        except Exception as e: #falls Fehler auftreten
            print(f"Fehler beim Laden von Bahnhof {bid}: {e}")
            continue

        if bahnhof: #wenn es Bahnhof gibt
            if bahnhof.start_abschnitte or bahnhof.end_abschnitte: #wenn Bahnhof als StartBahnhof oder Endbahnhof verwendet wird
                blocked_names.append(bahnhof.name) #zu blocked_names hinzufügen
            else: # falls Bahnhof nicht in einem Abschnitt verwendet wird
                db.session.delete(bahnhof) #Bahnhof löschen
                deleted_count += 1 #Variable deleted_count um 1 erhöhen

    #wenn deleted_count mindestens 1 -> heißt, dass mindestens 1 BAhnhof gelöscht wurde
    if deleted_count > 0:
        db.session.commit() #speichern
        flash(f"{deleted_count} Bahnhof/Bahnhöfe erfolgreich gelöscht.", "success") #Erfolgsnachricht

    #wenn Bahnhöfe in Abschnitte sind -> geblockt
    if blocked_names:
        #gibt geblcokten Bahnhofe als Erfolgsnachricht aus
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
        flash('Nur Admins dürfen neue Benutzer registrieren!', 'warning') #Warnungsmeldung
        return redirect(url_for('bahnhof'))

    form = RegistrationForm() #erstellt das Formular
    if form.validate_on_submit(): #wenn Formular abgesendet wurde
        # Neuen Benutzer anlegen
        user = User(username=form.username.data, email=form.email.data, role=form.role.data)
        user.set_password(form.password.data)
        #Neuen User speichern
        db.session.add(user)
        db.session.commit()
        flash(f'Neuer Benutzer "{user.username}" erfolgreich registriert!', 'success') #Erfolgsmeldung
        return redirect(url_for('bahnhof'))

    return render_template('register.html', title='Neuer Benutzer', form=form)

#############################################################
#####################   API   ###############################
#############################################################


###################   externe   #############################
#diese APIs wurden laut der Planung umgesetzt, jedoch verwendeten meine Kollegen andere APIs oder bauten meine APIs noch einmal um
#daher sind diese ohne Kommentare

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
            "startBahnhofName": start_bhf_name,
            "endBahnhofName": end_bhf_name,
            "startBahnhofId": abschnitt.startBahnhofId,
            "endBahnhofId": abschnitt.endBahnhofId,
            "spurweite": abschnitt.spurweite,
            "laenge": abschnitt.laenge,
            "nutzungsentgelt": abschnitt.nutzungsentgelt,
            "maxGeschwindigkeit": abschnitt.max_geschwindigkeit
        })

    total_count = len(items)
    return jsonify({"total": total_count, "streckenname": strecke.name, "items": items}), 200


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

    # Ergänzung Abschnitte 1601: Abschnitte D.S.
    stmt = stmt.options(
selectinload(Warnung.abschnitte).selectinload(Abschnitt.startBahnhof),
        selectinload(Warnung.abschnitte).selectinload(Abschnitt.endBahnhof),
    )
    # Ergänzung Abschnitte 1601

    warnung = db.session.scalars(stmt).all()

    items = []
    for w in warnung:
        # Ergänzung abschnitte 1601: Abschnitte (segment-Info) in API ausgeben
        abschnitte_items = []
        for a in (w.abschnitte or []):
            abschnitte_items.append({
                "vonName": a.startBahnhof.name if a.startBahnhof else None,
                "nachName": a.endBahnhof.name if a.endBahnhof else None,
            })
        # Ergänzung Abschnitte 1601 Daniel S

        items.append({
            "warnungId": w.warnungId,
            "bezeichnung": w.bezeichnung,
            "startZeit": w.startZeit,
            "endZeit": w.endZeit,
            # Ergänzung Abschnitte 1601 D.S für örtliche Einschränkung
            "abschnitte": abschnitte_items
            # Ergänzung Abschnitte 1601
        })
    total_count = len(warnung)

    return jsonify({"total": total_count, "items": items})



###################   interne   #############################


#damit Javascript auf die Koordinaten der Bahnhöfe zugreifen kann; für das Anzeigen der Abschnitte beim Hinzufügen
@app.route('/api/bahnhof/<int:bahnhof_id>')
def get_bahnhof_coords(bahnhof_id):

    if bahnhof_id == 0: # Wenn ID=0 (keine Auswahl)
        return jsonify({}), 200 # Leeres JSON zurück

    bahnhof = Bahnhof.query.get(bahnhof_id) #ruft die Daten für den bestimmten Bahnhof ab

    if bahnhof is None: #wenn Bahnhof nicht gefunden wurde
        return jsonify({'error': 'Bahnhof nicht gefunden'}), 404 #404-Fehler

    #gibt Daten zurück als JSON
    return jsonify({
        'id': bahnhof.bahnhofId,
        'latitude': bahnhof.latitude,
        'longitude': bahnhof.longitude
    })

#damit Javascript auf die Koordinaten der Bahnhöfe eines bestimmten Abschnitts zugreifen kann;
# für das Anzeigen der Abschnitte beim Hinzufügen (Warnung erstellen)
@app.route('/api/abschnitt/<int:abschnitt_id>')
def api_get_abschnitt_coords(abschnitt_id):

    abschnitt = db.session.get(Abschnitt, abschnitt_id) # Lädt Abschnitt

    startbahnhof = abschnitt.startBahnhof # Startbahnhof
    endbahnhof = abschnitt.endBahnhof # Endbahnhof

    # gibt Daten zurück als JSON
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

    #Query
    abschnitte = Abschnitt.query.options(
        joinedload(Abschnitt.startBahnhof), # Lädt Startbahnhof
        joinedload(Abschnitt.endBahnhof) # Lädt Endbahnhof
    ).join(
        Abschnitt.startBahnhof #Join mit Startbahnhof
    ).order_by( #sortiert nach Spurweite und Bahnhofsnamen
        Abschnitt.spurweite,
        Bahnhof.name
    ).all()

    abschnitt_data = [] #Liste für Abschnitte
    bahnhoefe_map = {} # Dictionary für Bahnhöfe

    for a in abschnitte: #Schleife über alle Abschnitte

        start_name = a.startBahnhof.name if a.startBahnhof else "Unbekannt" # Startbahnhof-Name oder "Unbekannt"
        end_name = a.endBahnhof.name if a.endBahnhof else "Unbekannt" # Endbahnhof-Name oder "Unbekannt"

        #Fügt Abschnitt hinzu
        abschnitt_data.append({
            "abschnittId": a.abschnittId,
            "name": f"{start_name} → {end_name} ({a.spurweite})",
            "startBahnhofId": a.startBahnhofId,
            "endBahnhofId": a.endBahnhofId,
            "spurweite": a.spurweite
        })

        if a.startBahnhof: # Wenn Startbahnhof existiert
            bahnhoefe_map[a.startBahnhof.bahnhofId] = start_name # Fügt zu Map hinzu
        if a.endBahnhof: # Wenn Endbahnhof existiert
            bahnhoefe_map[a.endBahnhof.bahnhofId] = end_name # Fügt zu Map hinzu


    #Json zurückgeben
    return jsonify({
        'abschnitte': abschnitt_data,
        'bahnhoefe': bahnhoefe_map
    })

#### API by Moritz (Fahrplan)
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
