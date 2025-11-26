from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, FloatField, \
    DateField, SelectMultipleField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Optional
import sqlalchemy as sa
from app import db
from app.models import User, Bahnhof, Abschnitt


class LoginForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired()])
    password = PasswordField('Passwort', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Passwort', validators=[DataRequired()])
    password2 = PasswordField(
        'Passwort wiederholen', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Rolle', choices=[('mitarbeiter', 'Mitarbeiter'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Anlegen')

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

class BahnhofForm(FlaskForm):
    name = StringField('Name des Bahnhofs', validators=[DataRequired()])
    adresse = StringField('Adresse des Bahnhofs', validators=[DataRequired()])
    submit = SubmitField('Bahnhof speichern')

    def __init__(self, original_name=None, original_adresse=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name
        self.original_adresse = original_adresse

    def validate_name(self, field):
        if self.original_name is None or field.data != self.original_name:
            bahnhof = db.session.scalar(
                sa.select(Bahnhof).where(Bahnhof.name == field.data)
            )
            if bahnhof is not None:
                raise ValidationError('Dieser Bahnhofsname ist bereits vergeben.')

    def validate_adresse(self, field):
        if self.original_adresse is None or field.data != self.original_adresse:
            bahnhof = db.session.scalar(
                sa.select(Bahnhof).where(Bahnhof.adresse == field.data)
            )
            if bahnhof is not None:
                raise ValidationError('Diese Adresse ist bereits vergeben.')

class AbschnittForm(FlaskForm):
    startBahnhof = SelectField("Startbahnhof", coerce=int, validators=[DataRequired()])
    endBahnhof = SelectField("Endbahnhof", coerce=int, validators=[DataRequired()])
    max_geschwindigkeit = IntegerField("Max. Geschwindigkeit", validators=[DataRequired()])
    spurweite = IntegerField("Spurweite", validators=[DataRequired()])
    nutzungsentgelt = FloatField("Nutzungsentgelt", validators=[DataRequired()])
    submit = SubmitField("Speichern")

    def validate(self, extra_validators=None):

        if not super().validate(extra_validators=extra_validators):
            return False

        start_id = self.startBahnhof.data
        end_id = self.endBahnhof.data

        if start_id == end_id:
            msg = 'Start- und Endbahnhof müssen unterschiedlich sein.'
            self.startBahnhof.errors.append(msg)
            self.endBahnhof.errors.append(msg)
            return False

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

class WarnungForm(FlaskForm):
    bezeichnung = StringField('Bezeichnung der Warnung', validators=[DataRequired()])
    beschreibung = StringField('Beschreibung der Warnung', validators=[DataRequired()])
    abschnitt =  SelectMultipleField("Abschnitt", coerce=int, validators=[DataRequired()])
    startZeit = DateField("gültig ab", validators=[DataRequired()])
    endZeit = DateField("gültig bis (optional)", validators=[Optional()])
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

