from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request
from app import app
from app.forms import LoginForm, RegistrationForm, BahnhofForm
from flask_login import current_user, login_user
import sqlalchemy as sa
from app import db
from app.models import User, Bahnhof
from flask_login import logout_user
from flask_login import login_required
import folium


@app.route('/abschnitt')
@login_required
def abschnitt():
    # hier renderst du die Liste der Abschnitte
    return render_template("abschnitt.html")

@app.route('/abschnitt/add')
@login_required
def abschnitt_add():
    # hier renderst du die Liste der Abschnitte
    return render_template("abschnitt_add.html")

@app.route("/abschnitt/edit", methods=["GET", "POST"])
@login_required
def abschnitt_edit():
    return render_template("abschnitt_edit.html")

@app.route("/bahnhof/add", methods=["GET", "POST"])
@login_required
def bahnhof_add():
    form = BahnhofForm()
    if form.validate_on_submit():
        # Neuer Bahnhof wird erstellt
        bahnhof = Bahnhof(name=form.name.data, adresse=form.adresse.data)

        # Optional: automatisch Latitude/Longitude setzen
        bahnhof.geocode_address()

        # In DB speichern
        db.session.add(bahnhof)
        db.session.commit()

        flash(f'Bahnhof {bahnhof.name} wurde gespeichert!', 'success')
        return redirect(url_for("bahnhof"))
    return render_template("bahnhof_add.html", form=form)

@app.route('/', methods=['GET', 'POST'])
@app.route('/bahnhof', methods=['GET', 'POST'])
@login_required
def bahnhof():
    # Alle Bahnhöfe aus der DB laden
    posts = Bahnhof.query.all()

    # Wenn es Bahnhöfe gibt → Karte bauen
    if posts:
        # fehlende Koordinaten geokodieren
        for b in posts:
            if not b.latitude or not b.longitude:
                b.geocode_address()
        db.session.commit()

        # Mittelpunkt berechnen
        center_lat = sum(b.latitude for b in posts) / len(posts)
        center_lon = sum(b.longitude for b in posts) / len(posts)

        # Folium-Karte erstellen
        m = folium.Map(location=[center_lat, center_lon], zoom_start=7)

        # Marker für jeden Bahnhof setzen
        for b in posts:
            folium.Marker(
                [b.latitude, b.longitude],
                tooltip=b.name,
                popup=f"{b.name}<br>{b.adresse}"
            ).add_to(m)

        # HTML-Code der Karte für das Template
        map_html = m._repr_html_()
    else:
        map_html = None

    # Template rendern
    return render_template(
        'bahnhof.html',
        title='Home',
        posts=posts,
        map_html=map_html,
        role=current_user.role
    )


@app.route("/bahnhof/edit/<int:bahnhof_id>", methods=["GET", "POST"])
@login_required
def edit_bahnhof(bahnhof_id):
    bahnhof = db.session.get(Bahnhof, bahnhof_id)
    if not bahnhof:
        flash("Bahnhof nicht gefunden.", "error")
        return redirect(url_for("bahnhof"))

    # WICHTIG: original_name und original_adresse setzen!
    form = BahnhofForm(
        obj=bahnhof,
        original_name=bahnhof.name,
        original_adresse=bahnhof.adresse
    )

    if form.validate_on_submit():
        form.populate_obj(bahnhof)  # Formular-Daten ins Model schreiben
        bahnhof.latitude = request.form.get("latitude")
        bahnhof.longitude = request.form.get("longitude")
        db.session.commit()
        flash(f"Bahnhof '{bahnhof.name}' wurde aktualisiert.", "success")
        return redirect(url_for("bahnhof"))

    return render_template("bahnhof_edit.html", form=form, bahnhof=bahnhof)

@app.route("/bahnhof/delete_multiple", methods=["POST"])
@login_required
def delete_multiple():
    ids = request.form.getlist("bahnhof_ids")
    if ids:
        for bid in ids:
            bahnhof = db.session.get(Bahnhof, int(bid))
            if bahnhof:
                db.session.delete(bahnhof)
        db.session.commit()
        flash(f"{len(ids)} Bahnhof/Bahnhöfe wurden gelöscht.", "success")
    else:
        flash("Keine Bahnhöfe ausgewählt.", "error")
    return redirect(url_for('bahnhof'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('bahnhof'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('bahnhof')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form, role='mitarbeiter')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('bahnhof'))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    # Zugriff nur für Admins
    if current_user.role.value != 'admin':
        flash('Nur Admins dürfen neue Benutzer registrieren!', 'warning')
        return redirect(url_for('bahnhof'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Neuen Benutzer anlegen
        user = User(username=form.username.data, email=form.email.data, role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash(f'Neuer Benutzer "{user.username}" erfolgreich registriert!', 'success')
        return redirect(url_for('bahnhof'))

    return render_template('register.html', title='Neuer Benutzer', form=form)

