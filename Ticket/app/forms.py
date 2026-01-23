from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    TextAreaField, FloatField, SelectField, TimeField
)
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange, EqualTo


# Login Formular
class LoginForm(FlaskForm):
    username = StringField("Username/ E-Mail", validators=[DataRequired()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    remember_me = BooleanField("Angemeldet bleiben")
    submit = SubmitField("Sign in")


# Registrierung
class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=64)])
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Passwort", validators=[DataRequired()])
    password2 = PasswordField(
        "Passwort wiederholen",
        validators=[DataRequired(), EqualTo("password", message="Passwörter müssen übereinstimmen.")]
    )
    accept_terms = BooleanField("Accept Terms and Conditions")
    submit = SubmitField("Register")


# Profil bearbeiten
class ProfileForm(FlaskForm):
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField("Vorname", validators=[Optional(), Length(max=64)])
    last_name = StringField("Nachname", validators=[Optional(), Length(max=64)])
    birthdate = DateField("Geburtsdatum", format="%Y-%m-%d", validators=[Optional()])

    new_password = PasswordField("Neues Passwort", validators=[Optional(), Length(min=4)])
    new_password2 = PasswordField(
        "Neues Passwort wiederholen",
        validators=[Optional(), EqualTo("new_password", message="Passwörter müssen übereinstimmen.")]
    )

    submit = SubmitField("Speichern")


# Formular für Aktionen
class AktionForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])

    beschreibung = TextAreaField("Beschreibung", validators=[Optional(), Length(max=1000)])

    startZeit = DateField("Startdatum (YYYY-MM-DD)", format="%Y-%m-%d", validators=[DataRequired()])
    endeZeit = DateField("Enddatum (YYYY-MM-DD)", format="%Y-%m-%d", validators=[DataRequired()])

    rabattWert = FloatField("Wert %", validators=[Optional(), NumberRange(min=0.0, max=100.0)])

    typ = SelectField(
        "Typ",
        choices=[("global", "GLOBAL"), ("halteplan", "HALTEPLAN")],
        validators=[DataRequired()],
    )

    halteplanId = SelectField("Halteplan", choices=[], validators=[Optional()], coerce=str)

    aktiv = BooleanField("Aktiv")
    submit = SubmitField("Speichern")


# Verbindungssuche
class VerbindungssucheForm(FlaskForm):
    startbahnhof = SelectField("Startbahnhof", choices=[], validators=[DataRequired()], coerce=str)
    zielbahnhof = SelectField("Zielbahnhof", choices=[], validators=[DataRequired()], coerce=str)
    datum = DateField("Datum", validators=[DataRequired()])
    uhrzeit = TimeField("Ab Uhrzeit optional", validators=[Optional()])
    submit = SubmitField("Suchen")
