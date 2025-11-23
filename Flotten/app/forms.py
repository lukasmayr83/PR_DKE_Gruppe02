from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, IntegerField, FloatField
from wtforms.validators import DataRequired, NumberRange, InputRequired

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
    spurweite = FloatField('Spurweite',validators=[DataRequired(message="Spurweite ist erforderlich!"),
                                                   NumberRange(min=0.01, message="Spurweite muss positiv sein")])
    speichern = SubmitField('Speichern')
    abbrechen = SubmitField('Abbrechen')

class TriebwagenForm(FlaskForm):
    maxzugkraft = FloatField('Maximale Zugkraft', validators=[DataRequired(message="Maximale Zugkraft ist erforderlich!"),
                                                              NumberRange(min=0.01,message="Zugkraft muss positiv sein")])
    spurweite = FloatField('Spurweite', validators=[DataRequired(message="Spurweite ist erforderlich!"),
                                                    NumberRange(min=0.01, message="Spurweite muss positiv sein")])
    speichern = SubmitField('Speichern')
    abbrechen = SubmitField('Abbrechen')

class ZuegeForm(FlaskForm):
    bezeichnung = StringField('Bezeichnung', validators=[DataRequired(message="Bezeichnung ist erforderlich!"),])

    speichern = SubmitField('Speichern')
    abbrechen = SubmitField('Abbrechen')