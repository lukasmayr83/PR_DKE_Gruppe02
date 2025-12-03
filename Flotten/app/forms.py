from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, IntegerField, FloatField,SelectField,DateField, TimeField
from wtforms.validators import DataRequired, NumberRange, InputRequired, EqualTo, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(message="Ungültiger Username")])
    password = PasswordField('Password', validators=[DataRequired(message="Ungültiges Passwort")])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class PersonenwagenForm(FlaskForm):
    kapazitaet = IntegerField('Kapazität',validators=[DataRequired(message="Kapaziät ist erforderlich!"),
                                                      NumberRange(min=1, message="Kapazität muss mindestens 1 sein!")])
    maxgewicht = FloatField('Maximales Gewicht', validators=[DataRequired(message="Maximales Gewicht ist erforderlich!"),
                            NumberRange(min=0.01, message="Gewicht muss positiv sein")])
    spurweite = SelectField('Spurweite', choices=[('1435 - Normalspur'), ('760 - Schmalspur')],validators=[DataRequired(message="Spurweite ist erforderlich!")])

    speichern = SubmitField('Speichern')
    abbrechen = SubmitField('Abbrechen')

class TriebwagenForm(FlaskForm):
    maxzugkraft = FloatField('Maximale Zugkraft', validators=[DataRequired(message="Maximale Zugkraft ist erforderlich!"),
                                                              NumberRange(min=0.01,message="Zugkraft muss positiv sein")])
    spurweite = SelectField('Spurweite',choices=[('1435 - Normalspur'),('760 - Schmalspur')], validators=[DataRequired(message="Spurweite ist erforderlich!")])

    speichern = SubmitField('Speichern')
    abbrechen = SubmitField('Abbrechen')

class ZuegeForm(FlaskForm):
    bezeichnung = StringField('Bezeichnung', validators=[DataRequired(message="Bezeichnung ist erforderlich!"),])

    speichern = SubmitField('Speichern')
    abbrechen = SubmitField('Abbrechen')


class MitarbeiterBaseForm(FlaskForm):
    vorname = StringField('Vorname', validators=[DataRequired(message="Vorname ist erforderlich!")])
    nachname = StringField('Nachname', validators=[DataRequired(message="Nachname ist erforderlich!")])
    svnr = IntegerField('Sozialversicherungsnummer',validators=[DataRequired(message="Sozialversicherungsnummer ist erforderlich!")])
    username = StringField("Benutzername", validators=[DataRequired(message="Benutzername ist erforderlich!")])

    speichern = SubmitField('Speichern')
    abbrechen = SubmitField('Abbrechen')


# Formular zum hinzufügen (Passwort ist PFLICHT)
class MitarbeiterAddForm(MitarbeiterBaseForm):
    password = PasswordField("Passwort", validators=[DataRequired(message="Passwort ist erforderlich!")])
    password2 = PasswordField("Passwort wiederholen", validators=[DataRequired(message="Wiederholung ist erforderlich!"),EqualTo('password', message="Passwörter stimmen nicht überein!")])
# Formular zum bearbeiten  (Passwort ändern OPTIONAL)
class MitarbeiterEditForm(MitarbeiterBaseForm):
    password = PasswordField("Neues Passwort (leer lassen zum Behalten)", validators=[ Optional()])
    password2 = PasswordField("Passwort wiederholen", validators=[ Optional(),EqualTo('password', message="Passwörter stimmen nicht überein!")])

class WartungszeitraumForm(FlaskForm):
    zugid = IntegerField('Zugid', validators=[DataRequired(message="Zugid ist erforderlich!"),NumberRange(min=1, message="Zugid kann nicht kleiner wie 1 sein!")])
    datum = DateField('Datum',validators=[DataRequired(message="Datum ist erforderlich!")])
    von = TimeField('Startzeit',validators=[DataRequired(message="Startzeit ist erforderlich!")], format="%H:%M")
    bis = TimeField('Endzeit',validators=[DataRequired(message="Endzeit ist erforderlich!")],format="%H:%M")

    speichern = SubmitField('Speichern')
    abbrechen = SubmitField('Abbrechen')
    verfuegbarkeit = SubmitField('Verfuegbarkeit')