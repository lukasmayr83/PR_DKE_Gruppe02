from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, FloatField, \
    DateField, SelectMultipleField, DateTimeField, DateTimeLocalField, validators
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Optional, NumberRange
import sqlalchemy as sa
from app import db
from app.models import User, Bahnhof, Abschnitt, Strecke, Reihenfolge

#############################################################
#####################  Login  ###############################
#############################################################

#Login-Formular
class LoginForm(FlaskForm):
    #Textfeld für den Benutzernamen mit Pflichtfeld-Validierung
    username = StringField('Benutzername', validators=[DataRequired()])
    #Passwortfeld für Passwort mit Pflichtfeld-Validierung
    password = PasswordField('Passwort', validators=[DataRequired()])
    # Checkbox zum Speichern der Login-Session
    remember_me = BooleanField('Remember Me')
    # Submit-Button "Login"
    submit = SubmitField('Login')





#############################################################
################   Registration   ###########################
#############################################################

#Regestrierungs-Formular
class RegistrationForm(FlaskForm):

    #Textfeld mit Pflichtfeld-Validierung für Benutzernamen
    username = StringField('Benutzername', validators=[DataRequired()])
    # Textfeld mit Pflichtfeld-Validierung für Email
    email = StringField('Email', validators=[DataRequired(), Email()])
    # Passwortfeld mit Pflichtfeld-Validierung
    password = PasswordField('Passwort', validators=[DataRequired()])
    # Passwort-Wiederholungsfeld mit Pflichtfeld- und Gleichheits-Validierung
    password2 = PasswordField(
        'Passwort wiederholen', validators=[DataRequired(), EqualTo('password')])
    #Dropdownfeld zur Auswahl der Rolle (Mitarbeiter oder Admin)
    role = SelectField('Rolle', choices=[('mitarbeiter', 'Mitarbeiter'), ('admin', 'Admin')], validators=[DataRequired()])
    # Submit-Button "Anlegen"
    submit = SubmitField('Anlegen')

    #username und email müssen unique sein -> schaut ob es in der DB bereits diesen BEnutzernamen bzw. Emailadresse schon gibt
    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if user is not None:
            raise ValidationError('Bitte verwenden Sie eine anderen Benutzernamen')

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(
            User.email == email.data))
        if user is not None:
            raise ValidationError('Bitte verwenden Sie eine andere E-Mail-Adresse.')





#############################################################
#################   Abschnitte   ############################
#############################################################

#Abschnitts-Formular
class AbschnittForm(FlaskForm):
    #Dropdown-Feld für Startbahnhof; wandelt Eingabewert in Integer um
    startBahnhof = SelectField("Startbahnhof", coerce=int, validators=[validators.DataRequired('Bitte wählen Sie einen Endbahnhof aus.')])
    # Dropdown-Feld für Endbahnhof; wandelt Eingabewert in Integer um
    endBahnhof = SelectField("Endbahnhof", coerce=int, validators=[validators.DataRequired('Bitte wählen Sie einen Startbahnhof aus.')])
    #Geschwindigkeit, Nutzungsentgelt, Länge müssen positiv sein
    max_geschwindigkeit = IntegerField("Max. Geschwindigkeit [km/h]", validators=[DataRequired(message="Bitte geben Sie eine gültige Geschwindigkeit ein."),
            NumberRange(min=1, message="Die Geschwindigkeit muss größer als 0 sein.")], )
    spurweite = SelectField("Spurweite", coerce=int, validators=[DataRequired()])
    laenge = FloatField(
        "Länge [km]",
        validators=[
            DataRequired(message="Bitte geben Sie eine gültige Länge ein."),
            NumberRange(min=0.01, message="Die Länge muss positiv sein.")
        ])
    nutzungsentgelt = FloatField(
        "Nutzungsentgelt [€]",
        validators=[DataRequired(message="Bitte geben Sie einen gültigen Geldbetrag ein."),
                    NumberRange(min=0.01, message="Der Betrag muss positiv sein.")])

    submit = SubmitField("Speichern") #SubmitButton -> Speichern

    # Konstruktor: initialisiert das Formular mit optionalen Original-Werten
    def __init__(self, original_start_id=None, original_end_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #ursprüngliche Bahnhofsdaten speichern, um zu überprüfen, ob die Bahnhofs_ids geändert wurden -> Abschnitt schon gibt
        self.original_start_id = original_start_id
        self.original_end_id = original_end_id

    #Validierungsmethode
    def validate(self, extra_validators=None):
        # Führt Standard-Validierungen der Elternklasse aus
        if not super().validate(extra_validators=extra_validators):
            return False

        #falls spurweite 0 ist -> wird die Fehlermeldung angefügt
        spurweite = self.spurweite.data
        if spurweite == 0:
            self.spurweite.errors.append('Bitte wählen Sie eine gültige Spurweite aus.')
            return False

        start_id = self.startBahnhof.data
        end_id = self.endBahnhof.data

        #Start-Und Endbahnhof dürfen nicht 0 sein -> 0 ist der Text der sagt, dass man einen Bahnhof auswählen soll
        if start_id == 0:
            self.startBahnhof.errors.append('Bitte wählen Sie einen gültigen Startbahnhof aus.')
            return False

        if end_id == 0:
            self.endBahnhof.errors.append('Bitte wählen Sie einen gültigen Endbahnhof aus.')
            return False

        #Start-und Endbahnhof müssen unterschiedlich sein
        if start_id == end_id:
            msg = 'Start- und Endbahnhof müssen unterschiedlich sein.'
            self.startBahnhof.errors.append(msg)
            self.endBahnhof.errors.append(msg)
            return False

        #falls Start- und Endbahnhof gleiche Id wie vor dem Bearbeiten haben -> TRUE -> okay!
        #falls sie ansonsten die gleiche Id-Kombination, wie in der Datenbank haben -> Fehlermeldung, dass der Abschnitt bereits existiert
        if (start_id == self.original_start_id) and (end_id == self.original_end_id):
            return True

        #schaut ob es die Kombi aus Start- und Endbahnhof schon gibt
        query = sa.select(Abschnitt).where(
            (Abschnitt.startBahnhofId == start_id) &
            (Abschnitt.endBahnhofId == end_id)
        )
        # Führt die Abfrage aus und holt das erste Ergebnis
        abschnitt = db.session.scalar(query)

        #falls
        if abschnitt is not None:
            msg = 'Dieser Abschnitt (gleiches Start- und Endbahnhof-Paar) existiert bereits.'
            self.startBahnhof.errors.append(msg)
            self.endBahnhof.errors.append(msg)
            return False

        return True






#############################################################
###################   Bahnhof   #############################
#############################################################

#Bahnhof-Formular
class BahnhofForm(FlaskForm):
    #Textfeld für den Namen des Bahnhofs
    name = StringField('Name des Bahnhofs', validators=[DataRequired()])
    # Textfeld für die Adresse des Bahnhofs
    adresse = StringField('Adresse des Bahnhofs', validators=[DataRequired()])
    # Submit-Button "Bahnhof speichern"
    submit = SubmitField('Bahnhof speichern')

    # Konstruktor: initialisiert das Formular mit optionalen Original-Werten
    def __init__(self, original_name=None, original_adresse=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name
        self.original_adresse = original_adresse

    #kontrolliert ob es den Namen und die Adresse nicht schon ein anderer Bahnhof hat
    def validate_name(self, field):
        if self.original_name is None or field.data != self.original_name:
            bahnhof = db.session.scalar(
                sa.select(Bahnhof).where(Bahnhof.name == field.data)
            )
            if bahnhof is not None: #gibt es bereits einen Bahnhof mit dem Namen in der Datenbank?
                raise ValidationError('Dieser Bahnhofsname ist bereits vergeben.')

    #prüft, ob es die Adresse des Bahnhofs bereits von einem anderen Bahnhof verwendet wird
    def validate_adresse(self, field):
        if self.original_adresse is None or field.data != self.original_adresse:
            bahnhof = db.session.scalar(
                sa.select(Bahnhof).where(Bahnhof.adresse == field.data)
            )
            if bahnhof is not None:
                raise ValidationError('Diese Adresse ist bereits vergeben.')





#############################################################
###################   Strecken   ############################
#############################################################

#Strecken-Formular
class StreckenForm(FlaskForm):
    #Textfeld für den Namen der Strecke mit Pflichtfeld-Validierung
    name = StringField('Name der Strecke', validators=[DataRequired()])
    # Mehrfach-Auswahl-Feld für Abschnitte, wandelt Werte zu Integern um
    abschnitt = SelectMultipleField("Abschnitte", coerce=int)
    # Submit-Button "Strecke speichern"
    submit = SubmitField('Strecke speichern')

    # Konstruktor: initialisiert das Formular mit optionalem Original-Namen
    def __init__(self, original_name=None, *args, **kwargs):
        super(StreckenForm, self).__init__(*args, **kwargs)
        self.original_name = original_name

    #prüft, ob es den Streckennamen bereits gibt
    def validate_name(self, name):
        # Wenn der Name gleich geblieben ist, ist das ok
        if self.original_name and name.data == self.original_name:
            return


        existing = Strecke.query.filter_by(name=name.data).first()
        if existing:
            raise ValidationError('Eine Strecke mit diesem Namen existiert bereits!')





#############################################################
###################   Warnung   #############################
#############################################################

#Warnung-Formular
class WarnungForm(FlaskForm):
    #Textfeld für die Bezeichnung der Warnung mit Pflichtfeld-Validierung
    bezeichnung = StringField('Bezeichnung der Warnung', validators=[DataRequired()])
    # Textfeld für die Beschreibung der Warnung mit Pflichtfeld-Validierung
    beschreibung = StringField('Beschreibung der Warnung', validators=[DataRequired()])
    # Mehrfach-Auswahl-Feld für Abschnitte mit Pflichtfeld-Validierung
    abschnitt = SelectMultipleField("Abschnitt", coerce=int, validators=[DataRequired()])
    # Datum-Zeit-Feld für den Startzeitpunkt mit Pflichtfeld-Validierung
    startZeit = DateTimeLocalField("gültig ab", validators=[DataRequired()])
    # Datum-Zeit-Feld für den Endzeitpunkt mit Pflichtfeld-Validierung
    endZeit = DateTimeLocalField("gültig bis (optional)", validators=[Optional()]) #ist optional
    # Submit-Button "Warnung speichern"
    submit = SubmitField('Warnung speichern')

    def validate(self, extra_validators=None):
        # Führt Standard-Validierungen der Elternklasse aus
        if not super().validate(extra_validators=extra_validators):
            return False

        #prüft ob Endzeit falls vorhanden später ist als Startzeit
        startZeit = self.startZeit.data
        endZeit = self.endZeit.data

        if endZeit == None: #falls es keine Endzeit gibt -> okay
            return True

        if endZeit <= startZeit: #falls Startzeit später ist als Endzeit -> Fehlermeldung
            msg = 'Startzeit der Warnung muss vor der Endzeit liegen.'
            self.startZeit.errors.append(msg)
            self.endZeit.errors.append(msg)
            return False

        return True



