from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(message="Ungültiger Username")])
    password = PasswordField('Password', validators=[DataRequired(message="Ungültiges Passwort")])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')
