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

class LoginForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired()])
    password = PasswordField('Passwort', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')





#############################################################
################   Registration   ###########################
#############################################################

class RegistrationForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Passwort', validators=[DataRequired()])
    password2 = PasswordField(
        'Passwort wiederholen', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Rolle', choices=[('mitarbeiter', 'Mitarbeiter'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Anlegen')

    #username und email müssen unique sein
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

class AbschnittForm(FlaskForm):
    startBahnhof = SelectField("Startbahnhof", coerce=int, validators=[validators.DataRequired('Bitte wählen Sie einen Endbahnhof aus.')])
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
    submit = SubmitField("Speichern")


    def __init__(self, original_start_id=None, original_end_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #ursprüngliche Bahnhofsdaten speichern
        self.original_start_id = original_start_id
        self.original_end_id = original_end_id

    def validate(self, extra_validators=None):

        if not super().validate(extra_validators=extra_validators):
            return False

        #falls spurweite 0 ist wird die Fehlermeldung angefügt
        spurweite = self.spurweite.data
        if spurweite == 0:
            self.spurweite.errors.append('Bitte wählen Sie eine gültige Spurweite aus.')
            return False

        start_id = self.startBahnhof.data
        end_id = self.endBahnhof.data

        #Start-Und Endbahnhof dürfen nicht 0 sein
        if start_id == 0:
            self.startBahnhof.errors.append('Bitte wählen Sie einen gültigen Startbahnhof aus.')
            return False

        if end_id == 0:
            self.endBahnhof.errors.append('Bitte wählen Sie einen gültigen Endbahnhof aus.')
            return False

        #müssen unterschiedlich sein
        if start_id == end_id:
            msg = 'Start- und Endbahnhof müssen unterschiedlich sein.'
            self.startBahnhof.errors.append(msg)
            self.endBahnhof.errors.append(msg)
            return False

        #falls Start- und Endbahnhof gleiche Id wie vor dem bearbeiten haben wird Query,
        #die sonst eine Fehlermeldung aufwirft nicht mehr ausgeführt
        if (start_id == self.original_start_id) and (end_id == self.original_end_id):
            return True

        #schaut ob es die Kombi aus Start- und Endbahnhof schon gibt
        query = sa.select(Abschnitt).where(
            (Abschnitt.startBahnhofId == start_id) &
            (Abschnitt.endBahnhofId == end_id)
        )

        abschnitt = db.session.scalar(query)

        if abschnitt is not None:

            msg = 'Dieser Abschnitt (gleiches Start- und Endbahnhof-Paar) existiert bereits.'
            self.startBahnhof.errors.append(msg)
            self.endBahnhof.errors.append(msg)
            return False

        return True






#############################################################
###################   Bahnhof   #############################
#############################################################

class BahnhofForm(FlaskForm):
    name = StringField('Name des Bahnhofs', validators=[DataRequired()])
    adresse = StringField('Adresse des Bahnhofs', validators=[DataRequired()])
    submit = SubmitField('Bahnhof speichern')

    def __init__(self, original_name=None, original_adresse=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name
        self.original_adresse = original_adresse

    def validate_name(self, field):
        if self.original_name is None or field.data != self.original_name: #erste neuen Bahnhof ete Bahnhof wurde schon bearbeitet
            bahnhof = db.session.scalar(
                sa.select(Bahnhof).where(Bahnhof.name == field.data)
            )
            if bahnhof is not None: #gibt bereits einenBahnhof mit dem Namen in der Datenbank?
                raise ValidationError('Dieser Bahnhofsname ist bereits vergeben.')

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

class StreckenForm(FlaskForm):
    name = StringField('Name der Strecke', validators=[DataRequired()])
    abschnitt = SelectMultipleField("Abschnitte", coerce=int)
    submit = SubmitField('Strecke speichern')

    def __init__(self, original_name=None, *args, **kwargs):
        super(StreckenForm, self).__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        # Wenn der Name gleich geblieben ist, ist das OK
        if self.original_name and name.data == self.original_name:
            return


        existing = Strecke.query.filter_by(name=name.data).first()
        if existing:
            raise ValidationError('Eine Strecke mit diesem Namen existiert bereits!')





#############################################################
###################   Warnung   #############################
#############################################################

class WarnungForm(FlaskForm):
    bezeichnung = StringField('Bezeichnung der Warnung', validators=[DataRequired()])
    beschreibung = StringField('Beschreibung der Warnung', validators=[DataRequired()])
    abschnitt = SelectMultipleField("Abschnitt", coerce=int, validators=[DataRequired()])
    startZeit = DateTimeLocalField("gültig ab", validators=[DataRequired()])
    endZeit = DateTimeLocalField("gültig bis (optional)", validators=[Optional()])
    submit = SubmitField('Warnung speichern')

    def validate(self, extra_validators=None):

        if not super().validate(extra_validators=extra_validators):
            return False

        startZeit = self.startZeit.data
        endZeit = self.endZeit.data

        if endZeit == None:
            return True

        if endZeit <= startZeit:
            msg = 'Startzeit der Warnung muss vor der Endzeit liegen.'

            self.startZeit.errors.append(msg)
            self.endZeit.errors.append(msg)

            return False

        return True



