from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SubmitField,
    TextAreaField,
    IntegerField,
    SelectField, SelectMultipleField, FloatField
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    ValidationError,
    Length,
    Optional, NumberRange
)

from app.models import User


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")



class EmptyForm(FlaskForm):
    submit = SubmitField("Submit")


# ----------------------------------------------
#   NEU: Mitarbeiter anlegen (inkl. User-Daten)
# ----------------------------------------------

class MitarbeiterForm(FlaskForm):
    name = StringField(
        "Name", validators=[DataRequired(), Length(min=1, max=128)]
    )
    username = StringField(
        "Benutzername", validators=[DataRequired(), Length(min=1, max=64)]
    )
    password = PasswordField(
        "Passwort", validators=[DataRequired(), Length(min=4, max=128)]
    )
    submit = SubmitField("Speichern")

    def validate_username(self, username):
        # Verhindert doppelte Logins, wenn Admin Mitarbeiter anlegt
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError("Bitte anderen Benutzernamen verwenden.")


class MitarbeiterEditForm(FlaskForm):
    name = StringField(
        "Name", validators=[DataRequired(), Length(min=1, max=128)]
    )
    username = StringField(
        "Benutzername", validators=[DataRequired(), Length(min=1, max=64)]
    )
    password = PasswordField(
        "Neues Passwort (optional)", validators=[Length(min=0, max=128)]
    )
    submit = SubmitField("Änderungen speichern")

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user is not None:
                raise ValidationError("Bitte anderen Benutzernamen verwenden.")


class FahrtdurchfuehrungForm(FlaskForm):
    halteplan_id = SelectField(
        "Halteplan",
        coerce=int,
        validators=[DataRequired()],
    )
    zug_id = IntegerField(
        "Zug-ID",
        validators=[DataRequired()],
    )
    status = SelectField(
        "Status",
        validators=[DataRequired()],
        # choices setzen wir in der Route dynamisch
    )

    submit = SubmitField("Speichern")

class FahrtCreateForm(FlaskForm):
    halteplan_id = SelectField(
        "Halteplan",
        coerce=int,
        validators=[DataRequired()]
    )



    submit = SubmitField("Speichern")

class FahrtEditForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[
            ("PLANMAESSIG", "planmäßig"),
            ("VERSPAETET", "verspätet"),
            ("AUSGEFALLEN", "ausgefallen")
        ],
        validators=[DataRequired()]
    )
    verspaetung_min = IntegerField("Verspätung (Minuten)", default=0)
    submit = SubmitField("Speichern")

class FahrtCreateForm(FlaskForm):
    halteplan_id = SelectField("Halteplan", coerce=int, validators=[DataRequired()])
    mitarbeiter_ids = SelectMultipleField("Mitarbeiter", coerce=int)
    submit = SubmitField("Fahrtdurchführung anlegen")



class HalteplanCreateForm(FlaskForm):
    bezeichnung = StringField("Bezeichnung", validators=[DataRequired(), Length(max=128)])

    strecke_id = SelectField("Strecke", coerce=int, validators=[DataRequired()])

    # Bahnhof-IDs in Reihenfolge, z.B. "12, 5, 9"
    haltepunkte_csv = StringField(
        "Haltepunkte (Bahnhof-IDs, Reihenfolge, Komma-getrennt)",
        validators=[DataRequired(), Length(min=1, max=500)]
    )

    base_price_default = FloatField(
        "Grundtarif pro Segment (Default, EUR-Cent oder EUR – je nachdem was du nutzt)",
        validators=[DataRequired(), NumberRange(min=0)]
    )

    duration_min_default = IntegerField(
        "Dauer pro Segment (Default, Minuten)",
        validators=[DataRequired(), NumberRange(min=0)]
    )

    submit = SubmitField("Halteplan anlegen")
