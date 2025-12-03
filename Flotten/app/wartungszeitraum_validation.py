from flask import flash, request
from app.models import Zuege, Wartung, Wartungszeitraum, Mitarbeiter
from app import db
from datetime import date
from sqlalchemy import or_, not_

    # Prüft ob der Zug existiert
def validate_zug_existiert(zugid):
    zug = db.session.get(Zuege, zugid)
    if zug is None:
        flash("Die eingegebene Zug-ID existiert nicht!")
        return False
    return True

 # Prüft ob das Datum nicht in der Vergangenheit liegt
def validate_datum_nicht_vergangenheit(datum):
    if datum is None:
        flash("Bitte geben Sie ein Datum ein!")
        return False
    if datum < date.today():
        flash("Das Datum darf nicht in der Vergangenheit liegen!")
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
    if not validate_datum_nicht_vergangenheit(form.datum.data):
        return False
    if not validate_von_vor_bis(form.von.data, form.bis.data):
        return False
    return True

def validate_zug_datum_von_bis(form):
    if not validate_zug_existiert(form.zugid.data):
        return False
    if not validate_datum_nicht_vergangenheit(form.datum.data):
        return False
    if not validate_von_vor_bis(form.von.data, form.bis.data):
        return False
    return True



