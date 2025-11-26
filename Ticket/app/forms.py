from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    TextAreaField, FloatField, SelectField
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


# Formular für Aktionen
class AktionForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(max=100)]
    )

    beschreibung = TextAreaField(
        "Beschreibung",
        validators=[Optional(), Length(max=1000)]
    )

    startZeit = DateField(
        "Startdatum (DD.MM.JJJJ)",
        format="%Y-%m-%d",
        validators=[DataRequired()],
    )

    endeZeit = DateField(
        "Enddatum (DD.MM.JJJJ)",
        format="%Y-%m-%d",
        validators=[DataRequired()],
    )

    rabattWert = FloatField(
        "Wert %",
        validators=[Optional(), NumberRange(min=0.0, max=100.0)]
    )

    typ = SelectField(
        "Typ",
        choices=[
            ("global", "GLOBAL"),
            ("halteplan", "HALTEPLAN"),
        ],
        validators=[DataRequired()],
    )

    halteplanId = SelectField(
        "Halteplan auswählen",
        choices=[
            ("", "keine"),
            ("1", "Halteplan [Linz Hbf - Innsbruck Hbf]"),
        ],
        validators=[Optional()],
    )

    aktiv = BooleanField("Aktiv")

    submit = SubmitField("Speichern")
