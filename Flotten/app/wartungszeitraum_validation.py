from flask import flash, request
from app.models import Zuege, Wartung, Wartungszeitraum, Mitarbeiter
from app import db
from datetime import date, datetime
from sqlalchemy import or_, not_

    # Prüft ob der Zug existiert
def validate_zug_existiert(zugid):
    zug = db.session.get(Zuege, zugid)
    if zug is None:
        flash("Die eingegebene Zug-ID existiert nicht!")
        return False
    return True

 # Prüft ob das Datum nicht in der Vergangenheit liegt
def validate_datetime_nicht_vergangenheit(datum, von, bis):

    if datum is None or von is None or bis is None:
        flash("Bitte Datum und Uhrzeiten eingeben!")
        return False

    # Datum grob prüfen
    if datum < date.today():
        flash("Das Datum darf nicht in der Vergangenheit liegen!")
        return False

    jetzt = datetime.now()
    start_dt = datetime.combine(datum, von)
    ende_dt = datetime.combine(datum, bis)

    # Ende liegt in der Vergangenheit
    if ende_dt <= jetzt:
        flash("Der Wartungszeitraum darf nicht in der Vergangenheit liegen!")
        return False

    #  Startpunkt in der Vergangenheit - Ende aber nicht
    if start_dt < jetzt < ende_dt:
        flash("Der Startzeitpunkt liegt in der Vergangenheit!")
        return False

    return True

 #  Prüft ob VON vor BIS liegt
def validate_von_vor_bis(von, bis):
    if von is None:
        flash("Bitte geben Sie einen Anfangszeit für die Wartung ein!")
        return False
    if bis is None:
        flash("Bitte geben Sie eine Endzeit für die Wartung ein!")
        return False
    if von >= bis:
        flash("Der Anfang muss vor dem Ende liegen!")
        return False
    return True

 # Prüft ob mindestens ein Mitarbeiter ausgewählt wurde
def validate_mitarbeiter_ausgewaehlt(req):
    # Nutzt getlist für Checkboxen
    svnr = req.form.getlist('mitarbeiter_svnr')
    if not svnr:
        flash("Bitte Verfügbarkeit prüfen und dann mindestens einen Mitarbeiter auswählen!")
        return False
    return True

def validate_all(form, req):
    if not validate_mitarbeiter_ausgewaehlt(req):
        return False
    if not validate_zug_existiert(form.zugid.data):
        return False
    if not validate_datetime_nicht_vergangenheit(form.datum.data,form.von.data,form.bis.data):
        return False
    if not validate_von_vor_bis(form.von.data, form.bis.data):
        return False
    if not validate_zug_wartung_keine_ueberlappung(form.zugid.data, form.datum.data, form.von.data, form.bis.data):
        flash("Dieser Zug hat in diesem Zeitraum bereits eine Wartung!")
        return False
    return True

def validate_zug_datum_von_bis(form):
    if not validate_zug_existiert(form.zugid.data):
        return False
    if not validate_datetime_nicht_vergangenheit(form.datum.data,form.von.data,form.bis.data):
        return False
    if not validate_von_vor_bis(form.von.data, form.bis.data):
        return False
    return True

 # Gibt eine Liste aller Mitarbeiter zurück die im angegebenen Zeitraum verfügbar sind
def get_verfuegbare_mitarbeiter(datum, von, bis, ignore_wzid=None):

    # Datetime bauen
    von_dt = datetime.combine(datum, von)
    bis_dt = datetime.combine(datum, bis)

    # Subquery: Mitarbeiter, die in dieser Zeit belegt sind
    sub = (
        db.select(Wartung.svnr)
        .join(Wartungszeitraum)
        .where(
            Wartungszeitraum.von < bis_dt,
            Wartungszeitraum.bis > von_dt
        )
    )
    # Eigene Wartung bei der Prüfung ignorieren - WICHTIG BEI BEARBEITEN
    if ignore_wzid is not None:
        sub = sub.where(Wartung.wartungszeitid != int(ignore_wzid))

    # Verfügbare Mitarbeiter
    verfuegbare = db.session.execute(
        db.select(Mitarbeiter)
        .where(not_(Mitarbeiter.svnr.in_(sub)))
        .order_by(Mitarbeiter.vorname)
    ).scalars().all()

    return verfuegbare

 # Prüft ob der Zug im Zeitraum bereits eine andere Wartung hat
def validate_zug_wartung_keine_ueberlappung(zugid, datum, von, bis, ignore_wzid=None):

    von_dt = datetime.combine(datum, von)
    bis_dt = datetime.combine(datum, bis)

    query = db.select(Wartung).join(Wartungszeitraum).where(
        Wartung.zugid == zugid,
        Wartungszeitraum.von < bis_dt,
        Wartungszeitraum.bis > von_dt
    )

    if ignore_wzid is not None:
        query = query.where(Wartung.wartungszeitid != int(ignore_wzid))

    result = db.session.execute(query).scalars().all()
    if result:
        return False  # Überschneidung gefunden

    return True