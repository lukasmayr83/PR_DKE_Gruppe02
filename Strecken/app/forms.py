from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
import sqlalchemy as sa
from app import db
from app.models import User, Bahnhof


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('mitarbeiter', 'Mitarbeiter'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Register')

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
        # Nur prüfen, wenn der Name geändert wurde oder beim Erstellen
        if self.original_name is None or field.data != self.original_name:
            bahnhof = db.session.scalar(
                sa.select(Bahnhof).where(Bahnhof.name == field.data)
            )
            if bahnhof is not None:
                raise ValidationError('Dieser Bahnhofsname ist bereits vergeben.')

    def validate_adresse(self, field):
        # Nur prüfen, wenn die Adresse geändert wurde oder beim Erstellen
        if self.original_adresse is None or field.data != self.original_adresse:
            bahnhof = db.session.scalar(
                sa.select(Bahnhof).where(Bahnhof.adresse == field.data)
            )
            if bahnhof is not None:
                raise ValidationError('Diese Adresse ist bereits vergeben.')
