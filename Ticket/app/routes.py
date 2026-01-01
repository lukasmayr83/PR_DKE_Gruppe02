from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_user, logout_user, login_required
from urllib.parse import urlparse
from datetime import datetime, date, time as dtime, timezone

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import User, Aktion, Ticket
from app.forms import LoginForm, AktionForm, RegisterForm, VerbindungssucheForm, ProfileForm

from app.services.verbindungen import suche_verbindungen  # die Logik bleibt in service
from app.services.external_clients import (
    strecken_bahnhoefe,
    strecken_warnungen,
    flotte_kapazitaet,
    fahrplan_halteplaene,
    fahrplan_snapshot,
    parse_gmt_dt,
)

bp = Blueprint("main", __name__)

# Hilfsfunktionen

def _as_date(x) -> date | None:
    """macht aus datetime/date "date" (oder None)"""
    if x is None:
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return None


def _now_utc() -> datetime:
    """
    "jetzt" als UTC datetime
    Verwendung in mehreren Stellen, weil abfahrt/ankunft datetimes sind
    """
    return datetime.utcnow()


def _aktion_is_running(a: Aktion, now: datetime) -> bool:
    """
    check ob die Aktion grad läuft (aktiv=true und Datum ist in range)
    """
    if not a.aktiv:
        return False
    sd = _as_date(a.startZeit)
    ed = _as_date(a.endeZeit)
    if not sd or not ed:
        return False
    return sd <= now.date() <= ed


def lade_bahnhoefe() -> list[str]:
    """Lädt Bahnhofs-Namen für Autocomplete (datalist)"""
    try:
        data = strecken_bahnhoefe()
    except Exception:
        return []

    return [
        (b.get("name") or "").strip()
        for b in (data.get("items") or [])
        if (b.get("name") or "").strip()
    ]


def ermittle_beste_aktion(verbindungs_datum: datetime, halteplan_id: int | None):
    """
    beste Aktion = maximaler Rabatt
    Wenn gleich- bevorzuge HALTEPLAN vor GLOBAL
    """
    aktive = Aktion.query.filter_by(aktiv=True).all()
    kandidaten: list[Aktion] = []

    for a in aktive:
        sd = _as_date(a.startZeit)
        ed = _as_date(a.endeZeit)
        if not sd or not ed:
            continue

        if sd <= verbindungs_datum.date() <= ed:
            if a.typ == "global":
                kandidaten.append(a)
            elif a.typ == "halteplan" and halteplan_id is not None and a.halteplanId == halteplan_id:
                kandidaten.append(a)

    if not kandidaten:
        return None

    # max by (rabatt, halteplanBonus)
    return max(
        kandidaten,
        key=lambda a: (
            float(a.rabattWert or 0.0),
            1 if a.typ == "halteplan" else 0
        )
    )


def _build_snapshot_map() -> dict[int, list[str]]:
    """
    map fahrt_id -> [BahnhofName in Reihenfolge]
    (kommt aus Fahrplan-Snapshot, für Warnungs-Mapping auf Abschnitte)
    """
    try:
        snap = fahrplan_snapshot()
    except Exception:
        return {}

    out: dict[int, list[str]] = {}
    for it in (snap.get("items") or []):
        fid = int(it.get("fahrtdurchfuehrungId") or 0)
        hps = list(it.get("haltepunkte") or [])
        hps.sort(key=lambda x: int(x.get("order") or 0))

        names = [hp.get("bahnhofName") for hp in hps if hp.get("bahnhofName")]
        if fid and names:
            out[fid] = names
    return out


def _slice_between(names: list[str], start_name: str, end_name: str) -> list[str]:
    """
    Sucht "kleinste" Teilsequenz start..end innerhalb names
    (falls Bahnhof mehrfach vorkommt, nimmt er die kürzeste passende Strecke)
    """
    starts = [i for i, n in enumerate(names) if n == start_name]
    ends = [j for j, n in enumerate(names) if n == end_name]
    best = None

    for i in starts:
        for j in ends:
            if j > i:
                if best is None or (j - i) < (best[1] - best[0]):
                    best = (i, j)

    if not best:
        return []
    i, j = best
    return names[i:j + 1]


def _pairs_for_leg(snapshot_map: dict[int, list[str]], fahrt_id: int, start_name: str, end_name: str) -> set[tuple[str, str]]:
    """
    baut Segment-Paare (von->nach) für genau den Teil (Start..End) einer Fahrt
    Beispiel: [Linz, Wels, Attnang] => {(Linz,Wels),(Wels,Attnang)}
    """
    names = snapshot_map.get(int(fahrt_id) or 0) or []
    if not names:
        return set()

    seq = _slice_between(names, start_name, end_name)
    if len(seq) < 2:
        return set()

    return {(seq[i], seq[i + 1]) for i in range(len(seq) - 1)}


def _warnung_matches_time(w: dict, travel_start: datetime, travel_end: datetime) -> bool:
    """
    check ob Warnung zeitlich überlappt mit der Reise
    Warnungen kommen als GMT-String (RFC format), parse_gmt_dt macht daraus UTC aware
    jedoch Vergleich "naiv" (ohne tzinfo) => normalize auf naive UTC
    """
    ws = parse_gmt_dt(w.get("startZeit"))
    we = parse_gmt_dt(w.get("endZeit"))

    def norm(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    ws_n = norm(ws)
    we_n = norm(we) or datetime.max

    if ws_n is None:
        return False

    # overlap check
    return ws_n <= travel_end and travel_start <= we_n


def _warnung_matches_segments(w: dict, seg_pairs: set[tuple[str, str]]) -> bool:
    """
    check ob Warnung zu irgendeinem Abschnitt (Segment) passt, den die Verbindung wirklich fährt
    abschnitte kommen jetzt im Strecken-API mit: vonName/nachName, etc.
    """
    abschnitte = w.get("abschnitte") or []
    if not abschnitte:
        return True

    if not seg_pairs:
        return False

    for a in abschnitte:
        von = a.get("vonName")
        nach = a.get("nachName")
        if not von or not nach:
            continue

        # akzeptieren beider Richtungen
        if (von, nach) in seg_pairs or (nach, von) in seg_pairs:
            return True

    return False


def warnungen_fuer_verbindung(
    warn_items: list[dict],
    snapshot_map: dict[int, list[str]],
    v: dict
) -> list[dict]:
    """
    filtert Warnungen für eine Verbindung:
      1) Zeit passt
      2) Abschnitt passt (über Segment-Mapping)
    """
    travel_start: datetime = v["abfahrt"]
    travel_end: datetime = v["ankunft"]

    # Segmente der Route bestimmen
    seg_pairs: set[tuple[str, str]] = set()

    # mit Umstieg => 2 legs
    if v.get("anzahl_umstiege") == 1 and v.get("umstieg_bahnhof"):
        seg_pairs |= _pairs_for_leg(snapshot_map, int(v["fahrt_id"]), v["start_halt"], v["umstieg_bahnhof"])
        if v.get("fahrt_id2"):
            seg_pairs |= _pairs_for_leg(snapshot_map, int(v["fahrt_id2"]), v["umstieg_bahnhof"], v["ziel_halt"])
    else:
        seg_pairs |= _pairs_for_leg(snapshot_map, int(v["fahrt_id"]), v["start_halt"], v["ziel_halt"])

    hits: list[dict] = []
    for w in warn_items:
        if not _warnung_matches_time(w, travel_start, travel_end):
            continue
        if not _warnung_matches_segments(w, seg_pairs):
            continue
        hits.append(w)

    return hits


# -----------------------------
# Routes
# -----------------------------

@bp.route("/")
@login_required
def index():
    # Admin landet in Aktionen, Kunde in Verbindungssuche
    if current_user.username == "admin":
        return redirect(url_for("main.aktionen_uebersicht"))
    return redirect(url_for("main.verbindungssuche"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    # wenn schon logged in, gleich weiter
    if current_user.is_authenticated:
        return redirect(url_for("main.aktionen_uebersicht" if current_user.username == "admin" else "main.verbindungssuche"))

    form = LoginForm()
    if form.validate_on_submit():
        # login per username ODER email
        user = User.query.filter(
            (User.username == form.username.data) | (User.email == form.username.data)
        ).first()

        if user is None or not user.check_password(form.password.data):
            flash("Ungültiger Benutzername oder Passwort")
            return redirect(url_for("main.login"))

        login_user(user, remember=form.remember_me.data)

        next_page = request.args.get("next")
        if not next_page or urlparse(next_page).netloc != "":
            next_page = url_for("main.aktionen_uebersicht" if user.username == "admin" else "main.verbindungssuche")

        return redirect(next_page)

    return render_template("login.html", title="Sign in", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    # nur wenn nicht eingeloggt
    if current_user.is_authenticated:
        return redirect(url_for("main.aktionen_uebersicht" if current_user.username == "admin" else "main.verbindungssuche"))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Username bereits vergeben.")
            return redirect(url_for("main.register"))
        if User.query.filter_by(email=form.email.data).first():
            flash("E-Mail bereits registriert.")
            return redirect(url_for("main.register"))

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash("Registrierung erfolgreich. Bitte jetzt einloggen.")
        return redirect(url_for("main.login"))

    return render_template("register.html", title="Registrierung", form=form)


@bp.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    """
    Kunden können hier ihre Daten ändern
    """
    form = ProfileForm()

    if request.method == "GET":
        # Werte reinladen fürs Formular
        form.email.data = current_user.email
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.birthdate.data = current_user.birthdate

    if form.validate_on_submit():
        new_email = (form.email.data or "").strip()

        # Email unique check
        existing = User.query.filter(User.email == new_email, User.id != current_user.id).first()
        if existing:
            flash("Diese E-Mail ist bereits vergeben.", "warning")
            return redirect(url_for("main.profil"))

        # speichern
        current_user.email = new_email
        current_user.first_name = (form.first_name.data or "").strip() or None
        current_user.last_name = (form.last_name.data or "").strip() or None
        current_user.birthdate = form.birthdate.data or None

        # Passwort  ändern
        if form.new_password.data:
            current_user.set_password(form.new_password.data)

        try:
            db.session.commit()
            flash("Profil gespeichert.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Profil konnte nicht gespeichert werden (Constraint).", "danger")

        return redirect(url_for("main.profil"))

    return render_template("profil.html", title="Profil", form=form)


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.login"))


# -----------------------------
# Aktionen (Admin)
# -----------------------------

@bp.route("/aktionen")
@login_required
def aktionen_uebersicht():
    """
    Übersichtsliste now wird ans Template gegeben (für Anzeige)
    """
    aktionen = Aktion.query.order_by(Aktion.id.asc()).all()
    now = datetime.now()
    return render_template("aktionen_uebersicht.html", title="Aktionsübersicht", aktionen=aktionen, now=now)


@bp.route("/aktionen/global/new", methods=["GET", "POST"])
@login_required
def aktion_global_new():
    form = AktionForm()
    form.typ.data = "global"
    form.halteplanId.data = ""

    if request.method == "POST":
        if form.name.data and form.startZeit.data and form.endeZeit.data:
            aktion = Aktion(
                name=form.name.data,
                beschreibung=form.beschreibung.data,
                startZeit=form.startZeit.data,
                endeZeit=form.endeZeit.data,
                aktiv=form.aktiv.data,
                rabattWert=form.rabattWert.data or 0.0,
                typ="global",
                halteplanId=None,
            )
            db.session.add(aktion)
            db.session.commit()
            flash("Globale Aktion angelegt.")
            return redirect(url_for("main.aktionen_uebersicht"))
        flash("Bitte alle Pflichtfelder ausfüllen.")

    return render_template("aktion_global_new.html", title="Globale-Aktion anlegen", form=form)


@bp.route("/aktionen/fahrplan/new", methods=["GET", "POST"])
@login_required
def aktion_fahrplan_new():
    form = AktionForm()

    # Haltepläne laden für Dropdown
    try:
        hp_data = fahrplan_halteplaene()
        hp_items = hp_data.get("items") or []
    except Exception:
        hp_items = []

    form.halteplanId.choices = [("", "-- bitte wählen --")] + [
        (str(x["halteplanId"]), x.get("bezeichnung") or x.get("label") or f"Halteplan {x['halteplanId']}")
        for x in hp_items
    ]

    form.typ.data = "halteplan"

    if request.method == "POST":
        if form.name.data and form.startZeit.data and form.endeZeit.data:
            halteplan_id = int(form.halteplanId.data) if form.halteplanId.data else None
            aktion = Aktion(
                name=form.name.data,
                beschreibung=form.beschreibung.data,
                startZeit=form.startZeit.data,
                endeZeit=form.endeZeit.data,
                aktiv=form.aktiv.data,
                rabattWert=form.rabattWert.data or 0.0,
                typ="halteplan",
                halteplanId=halteplan_id,
            )
            db.session.add(aktion)
            db.session.commit()
            flash("Fahrplan-Aktion angelegt.")
            return redirect(url_for("main.aktionen_uebersicht"))
        flash("Bitte alle Pflichtfelder ausfüllen.")

    return render_template("aktion_fahrplan_new.html", title="Fahrplan-Aktion anlegen", form=form)


@bp.route("/aktionen/<int:aktion_id>/stop", methods=["POST"])
@login_required
def aktion_stop(aktion_id: int):
    """
    aktive Aktionen dürfen nicht bearbeitet werden, nur gestoppt/ beendet
    """
    aktion = Aktion.query.get_or_404(aktion_id)
    now = _now_utc()

    if _aktion_is_running(aktion, now):
        aktion.aktiv = False
        aktion.endeZeit = now.date()  # "jetzt" beenden
        db.session.commit()
        flash("Aktion wurde beendet.", "success")
    else:
        flash("Aktion ist nicht aktiv – nichts zu beenden.", "info")

    return redirect(url_for("main.aktionen_uebersicht"))


@bp.route("/aktionen/<int:aktion_id>/edit", methods=["GET", "POST"])
@login_required
def aktion_edit(aktion_id):
    """
    Bearbeiten ist nur erlaubt wenn Aktion NICHT gerade läuft
    """
    aktion = Aktion.query.get_or_404(aktion_id)
    now = _now_utc()
    is_running = _aktion_is_running(aktion, now)

    form = AktionForm(
        name=aktion.name,
        beschreibung=aktion.beschreibung,
        startZeit=_as_date(aktion.startZeit),
        endeZeit=_as_date(aktion.endeZeit),
        aktiv=aktion.aktiv,
        rabattWert=aktion.rabattWert,
        typ=aktion.typ,
        halteplanId=str(aktion.halteplanId) if aktion.halteplanId else "",
    )

    # Halteplan-Dropdown auch beim Edit füllen
    try:
        hp_data = fahrplan_halteplaene()
        hp_items = hp_data.get("items") or []
    except Exception:
        hp_items = []
    form.halteplanId.choices = [("", "-- bitte wählen --")] + [
        (str(x["halteplanId"]), x.get("bezeichnung") or x.get("label") or f"Halteplan {x['halteplanId']}")
        for x in hp_items
    ]

    if request.method == "POST":
        if is_running:
            flash("Aktive Aktionen können nicht bearbeitet werden – nur beendet werden.", "warning")
            return redirect(url_for("main.aktion_edit", aktion_id=aktion.id))

        if form.validate_on_submit():
            aktion.name = form.name.data
            aktion.beschreibung = form.beschreibung.data
            aktion.startZeit = form.startZeit.data
            aktion.endeZeit = form.endeZeit.data
            aktion.aktiv = form.aktiv.data
            aktion.rabattWert = form.rabattWert.data or 0.0

            if aktion.typ == "global":
                aktion.typ = "global"
                aktion.halteplanId = None
            else:
                aktion.typ = "halteplan"
                aktion.halteplanId = int(form.halteplanId.data) if form.halteplanId.data else None

            db.session.commit()
            flash("Aktion aktualisiert.")
            return redirect(url_for("main.aktionen_uebersicht"))

    return render_template("aktion_edit.html", title="Aktion bearbeiten", form=form, aktion=aktion, is_running=is_running)


@bp.route("/aktionen/<int:aktion_id>/delete", methods=["POST"])
@login_required
def aktion_delete(aktion_id):
    """
    Löschen, Tickets verlieren dabei die Aktion FK
    """
    aktion = Aktion.query.get_or_404(aktion_id)

    Ticket.query.filter(Ticket.aktion_id == aktion.id).update({Ticket.aktion_id: None})

    try:
        db.session.delete(aktion)
        db.session.commit()
        flash("Aktion gelöscht")
    except IntegrityError:
        db.session.rollback()
        flash("Aktion konnte nicht gelöscht werden (FK-Problem).")

    return redirect(url_for("main.aktionen_uebersicht"))


# -----------------------------
# Verbindungssuche + Buchen
# -----------------------------

@bp.route("/verbindungssuche", methods=["GET", "POST"])
@login_required
def verbindungssuche():
    form = VerbindungssucheForm()
    bahnhoefe = lade_bahnhoefe()
    verbindungen: list[dict] = []
    warnungen_global: list[dict] = []

    if form.validate_on_submit():
        start = (form.startbahnhof.data or "").strip()
        ziel = (form.zielbahnhof.data or "").strip()
        datum = form.datum.data

        # Uhrzeit robust (string oder time)
        ab_zeit_val = None
        raw = (form.uhrzeit.data or "").strip()
        if raw:
            try:
                hh, mm = raw.split(":")
                ab_zeit_val = dtime(int(hh), int(mm))
            except Exception:
                ab_zeit_val = None

        hits = suche_verbindungen(start, ziel, datum, ab_zeit=ab_zeit_val)

        # nur zukünftige Verbindungen behalten
        now = _now_utc()
        hits = [h for h in hits if getattr(h, "abfahrt", None) and h.abfahrt > now]

        # Warnungen laden
        try:
            warn_items = (strecken_warnungen().get("items") or [])
        except Exception:
            warn_items = []

        # Snapshot laden (für Abschnitt-Mapping)
        snapshot_map = _build_snapshot_map()

        # wenn nach Filter nichts mehr da ist => Info
        if not hits:
            flash("Keine zukünftigen Verbindungen gefunden.")
            return render_template(
                "verbindungssuche.html",
                title="Verbindungssuche",
                form=form,
                verbindungen=[],
                warnungen=[],
                bahnhoefe=bahnhoefe,
            )

        for h in hits:
            # Basispreis
            preis = h.preis

            # beste Aktion finden
            aktion = ermittle_beste_aktion(h.abfahrt, h.halteplan_id)
            if aktion:
                preis = round(preis * (1 - float(aktion.rabattWert or 0.0) / 100.0), 2)
                aktion_name = aktion.name
                aktion_rabatt = float(aktion.rabattWert or 0.0)
                aktion_id = aktion.id
            else:
                aktion_name = None
                aktion_rabatt = 0.0
                aktion_id = None

            umstieg_ank_iso = h.umstieg_ankunft.isoformat() if h.umstieg_ankunft else ""
            umstieg_ab_iso = h.umstieg_abfahrt.isoformat() if h.umstieg_abfahrt else ""

            v = {
                # 1. Leg
                "fahrt_id": h.fahrtdurchfuehrung_id,
                "halteplan_id": h.halteplan_id,
                "zug_id": h.zug_id,

                # 2. Leg (optional)
                "fahrt_id2": h.fahrtdurchfuehrung_id2,
                "halteplan_id2": h.halteplan_id2,
                "zug_id2": h.zug_id2,

                # Anzeige
                "start_halt": h.start_name,
                "ziel_halt": h.ziel_name,
                "abfahrt": h.abfahrt,
                "ankunft": h.ankunft,
                "abfahrt_display": h.abfahrt.strftime("%d.%m.%Y %H:%M"),
                "ankunft_display": h.ankunft.strftime("%d.%m.%Y %H:%M"),
                "abfahrt_iso": h.abfahrt.isoformat(),
                "ankunft_iso": h.ankunft.isoformat(),

                "anzahl_umstiege": h.umstiege,
                "preis": preis,

                # Umstieg
                "umstieg_bahnhof": h.umstieg_bahnhof,
                "umstieg_ankunft_display": h.umstieg_ankunft.strftime("%d.%m.%Y %H:%M") if h.umstieg_ankunft else "",
                "umstieg_abfahrt_display": h.umstieg_abfahrt.strftime("%d.%m.%Y %H:%M") if h.umstieg_abfahrt else "",
                "umstieg_ankunft_iso": umstieg_ank_iso,
                "umstieg_abfahrt_iso": umstieg_ab_iso,

                # Aktion
                "aktion_name": aktion_name,
                "aktion_rabatt": aktion_rabatt,
                "aktion_id": aktion_id,

                # Warnungen (pro Verbindung)
                "warnungen": [],
            }

            # Warnungen für diese Verbindung berechnen
            v["warnungen"] = warnungen_fuer_verbindung(warn_items, snapshot_map, v)
            verbindungen.append(v)

        # GLobal: aktive Warnungen (zeitlich) – aber nur jene, die nicht schon pro Verbindung angezeigt werden
        # allgemeine Warnungen zur Suchzeit die nicht konkret auf die Route matchen
        if hits:
            t0 = hits[0].abfahrt
            already = {
                w.get("warnungId")
                for v in verbindungen
                for w in (v.get("warnungen") or [])
                if w.get("warnungId") is not None
            }
            for w in warn_items:
                if not _warnung_matches_time(w, t0, t0):
                    continue
                if w.get("warnungId") in already:
                    continue
                warnungen_global.append(w)

        if not verbindungen:
            flash("Keine passende Verbindung gefunden.")

    return render_template(
        "verbindungssuche.html",
        title="Verbindungssuche",
        form=form,
        verbindungen=verbindungen,
        warnungen=warnungen_global,
        bahnhoefe=bahnhoefe,
    )


@bp.route("/tickets/buchen/<int:fahrt_id>", methods=["POST"])
@login_required
def ticket_buchen(fahrt_id):
    """
    Ticket wird final gespeichert
        """

    start_halt = request.form.get("start_halt")
    ziel_halt = request.form.get("ziel_halt")

    abfahrt_str = request.form.get("abfahrt")
    ankunft_str = request.form.get("ankunft")

    umstiege = int(request.form.get("umstiege", 0))

    halteplan_id = request.form.get("halteplan_id")
    preis = float(request.form.get("preis"))
    sitzplatz = request.form.get("sitzplatz") == "1"
    aktion_id = request.form.get("aktion_id")

    zug_id = int(request.form.get("zug_id") or 0)

    # Umstieg / zweite Fahrt
    fahrt_id2_raw = (request.form.get("fahrt_id2") or "").strip()
    halteplan_id2_raw = (request.form.get("halteplan_id2") or "").strip()
    zug_id2 = int(request.form.get("zug_id2") or 0)

    umstieg_bahnhof = (request.form.get("umstieg_bahnhof") or "").strip() or None
    umstieg_ank_str = (request.form.get("umstieg_ankunft") or "").strip()
    umstieg_ab_str = (request.form.get("umstieg_abfahrt") or "").strip()

    fahrt_id2 = int(fahrt_id2_raw) if fahrt_id2_raw else None
    halteplan_id2 = int(halteplan_id2_raw) if halteplan_id2_raw else None

    # ISO Strings wieder zu datetime
    try:
        abfahrt = datetime.fromisoformat(abfahrt_str)
        ankunft = datetime.fromisoformat(ankunft_str)
    except (TypeError, ValueError):
        flash("Verbindungsdaten ungültig.")
        return redirect(url_for("main.verbindungssuche"))

    # Vergangenheit blocken
    now = _now_utc()
    if abfahrt <= now:
        flash("Vergangene Verbindungen können nicht gebucht werden.", "warning")
        return redirect(url_for("main.verbindungssuche"))

    # Sitzplatzpreis erst hier draufrechnen
    if sitzplatz:
        preis = round(preis + 5.0, 2)

    # Umstiegzeiten
    umstieg_ank = None
    umstieg_ab = None
    if umstiege == 1:
        try:
            umstieg_ank = datetime.fromisoformat(umstieg_ank_str) if umstieg_ank_str else None
            umstieg_ab = datetime.fromisoformat(umstieg_ab_str) if umstieg_ab_str else None
        except Exception:
            umstieg_ank = None
            umstieg_ab = None

    # Sitzplatz: lokale Reservierung
    if sitzplatz:
        # basic checks
        if not zug_id:
            flash("Sitzplatzreservierung nicht möglich (keine Zug-ID).", "warning")
            return redirect(url_for("main.verbindungssuche"))

        # an Flotte-Service: wie viele Plätze gibt es
        try:
            cap = flotte_kapazitaet(zug_id)
            total = sum(int(w.get("kapazitaet", 0)) for w in (cap.get("personenwagen") or []))
        except Exception:
            flash("Flotten-Service nicht erreichbar (Sitzplatz konnte nicht geprüft werden).", "warning")
            return redirect(url_for("main.verbindungssuche"))

        if total <= 0:
            flash("Keine Sitzplätze verfügbar (Kapazität=0).", "warning")
            return redirect(url_for("main.verbindungssuche"))

        # Lokaler Counter: wie viele aktive Reservierungen gibt es schon?
        used = Ticket.query.filter(
            Ticket.fahrt_id == fahrt_id,
            Ticket.status == "aktiv",
            Ticket.sitzplatzReservierung.is_(True),
        ).count()

        if used >= total:
            flash("Keine Sitzplätze mehr verfügbar (ausgebucht).", "warning")
            return redirect(url_for("main.verbindungssuche"))

    # Ticket anlegen
    ticket = Ticket(
        user_id=current_user.id,
        status="aktiv",
        start_halt=start_halt,
        ziel_halt=ziel_halt,
        anzahl_umstiege=umstiege,

        abfahrt=abfahrt,
        ankunft=ankunft,

        # 1. Fahrt
        fahrt_id=fahrt_id,
        halteplan_id=int(halteplan_id) if halteplan_id else None,
        zug_id=zug_id,

        # 2. Fahrt + Umstieg
        fahrt_id2=fahrt_id2,
        halteplan_id2=halteplan_id2,
        zug_id2=zug_id2 if zug_id2 else None,
        umstieg_bahnhof=umstieg_bahnhof,
        umstieg_ankunft=umstieg_ank,
        umstieg_abfahrt=umstieg_ab,

        gesamtPreis=preis,
        sitzplatzReservierung=sitzplatz,
        aktion_id=int(aktion_id) if aktion_id else None,
    )

    db.session.add(ticket)
    db.session.commit()
    flash("Ticket erfolgreich gebucht.")
    return redirect(url_for("main.meine_tickets"))


@bp.route("/meine-tickets")
@login_required
def meine_tickets():
    """
    Tickets anzeigen + Status "verbraucht" automatisch setzen wenn Abfahrt schon vorbei ist
    """
    now = _now_utc()

    tickets = Ticket.query.filter_by(user_id=current_user.id).order_by(Ticket.erstelltAm.desc()).all()

    changed = False
    for t in tickets:
        if t.status == "aktiv" and t.abfahrt and t.abfahrt <= now:
            t.status = "verbraucht"
            changed = True

    if changed:
        db.session.commit()

    return render_template("meine_tickets.html", title="Meine Tickets", tickets=tickets, now=now)


@bp.route("/tickets/<int:ticket_id>/storno", methods=["POST"])
@login_required
def ticket_storno(ticket_id):
    """
    Storno nur für zukünftige Tickets, nicht für verbraucht, nicht für schon storniert
    """
    now = _now_utc()
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=current_user.id).first_or_404()

    if ticket.status == "storniert":
        flash("Ticket ist bereits storniert.")
        return redirect(url_for("main.meine_tickets"))

    if ticket.status == "verbraucht":
        flash("Ticket ist bereits verbraucht und kann nicht storniert werden.", "warning")
        return redirect(url_for("main.meine_tickets"))

    # nur zukünftige Tickets stornierbar
    if ticket.abfahrt and ticket.abfahrt <= now:
        flash("Nur zukünftige Tickets können storniert werden.", "warning")
        return redirect(url_for("main.meine_tickets"))

    ticket.status = "storniert"

    db.session.commit()
    flash("Ticket wurde storniert.")
    return redirect(url_for("main.meine_tickets"))
