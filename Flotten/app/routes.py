from flask import render_template, flash, redirect, url_for, request
from urllib.parse import urlsplit
from app import app,db
from app.forms import LoginForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Role

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:#
        if current_user.role == Role.ADMIN:
            return redirect(url_for('dashboard_admin'))
        else:
            return redirect(url_for('dashboard_mitarbeiter'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Ungültiger username oder passwort')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        if user.role == Role.ADMIN:
            return redirect(url_for('dashboard_admin'))
        else:
            return redirect(url_for('dashboard_mitarbeiter'))

    return render_template('login.html', title='Anmeldung', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard_admin')
@login_required
def dashboard_admin():
    return render_template('dashboard.html', title='Admin Dashboard')

@app.route('/dashboard_mitarbeiter')
@login_required
def dashboard_mitarbeiter():
    return render_template('dashboard_mitarbeiter.html', title='Mitarbeiter Dashboard')

@app.route('/uebers_personenwagen')
@login_required
def uebers_personenwagen():
    user = {'username': 'Marcus'}
    return render_template('uebers_personenwagen.html', title='Home', user=user)

@app.route('/uebers_triebwagen')
@login_required
def uebers_triebwagen():
    user = {'username': 'Marcus'}
    return render_template('uebers_triebwagen.html', title='Home', user=user)