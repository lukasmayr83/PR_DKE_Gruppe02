import pytest
from app import create_app, db
from app.models import User, Role, Zuege, Wagen, Triebwagen, Personenwagen,Mitarbeiter, Wartungszeitraum, Wartung
from config import TestConfig
from datetime import date, datetime


# Flask App mit neuer Datenbank für tests erstellt - Datenbank nach jeden Test leer
@pytest.fixture(scope='function')
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

# Test client
@pytest.fixture(scope='function')
def client(app):
    return app.test_client()

# Test client runner
@pytest.fixture(scope='function')
def runner(app):
    """Test CLI Runner"""
    return app.test_cli_runner()

# Test Datenbank session
@pytest.fixture(scope='function')
def session(app):
    return db.session

################
## TEST-DATEN ##
################

 # Test Triebwagen erstellen
@pytest.fixture
def test_triebwagen(app,session):
    tw = Triebwagen(spurweite=1435.0,maxzugkraft=100.0,istfrei=None)
    session.add(tw)
    session.commit()
    return tw

# Test Personenwagen erstellen
@pytest.fixture
def test_personenwagen(app,session):
    pw = Personenwagen(spurweite=1435.0,kapazitaet=50,maxgewicht=30.0,istfrei=None)
    session.add(pw)
    session.commit()
    return pw

@pytest.fixture
def test_personenwagen_andere_spurweite(app,session):
    pw = Personenwagen(spurweite=760,kapazitaet=40,maxgewicht=25.0,istfrei=None)
    session.add(pw)
    session.commit()
    return pw

@pytest.fixture
def test_personenwagen_schwer(app,session):
    pw = Personenwagen(spurweite=1435.0,kapazitaet=100,maxgewicht=150.0,istfrei=None)
    session.add(pw)
    session.commit()
    return pw

# Test Zug erstellen
@pytest.fixture
def test_zug(app,session, test_triebwagen, test_personenwagen):
    zug = Zuege(bezeichnung="Test-Zug")
    session.add(zug)
    session.flush()

    test_triebwagen.istfrei = zug.zugid
    test_personenwagen.istfrei = zug.zugid
    session.commit()
    return zug

# Test User erstellen
@pytest.fixture
def test_user(app,session):
    user = User(id=1,username="testuser",role=Role.MITARBEITER)
    user.set_password("testuser")
    session.add(user)
    session.commit()
    return user

@pytest.fixture
def test_user2(app,session):
    user2 = User(id=2, username="testuser2", role=Role.MITARBEITER)
    user2.set_password("testuser2")
    session.add(user2)
    session.commit()
    return user2

# Test Mitarbeiter erstellen
@pytest.fixture
def test_mitarbeiter(app,session, test_user):
    mitarbeiter = Mitarbeiter(svnr=1234567890,vorname="Max",nachname="Mustermann",user_id=test_user.id)
    session.add(mitarbeiter)
    session.commit()
    return mitarbeiter
@pytest.fixture
def test_mitarbeiter2(app,session, test_user2):
    mitarbeiter2 = Mitarbeiter(svnr=9876543210, vorname="Anna", nachname="Beispiel", user_id=test_user2.id)
    session.add(mitarbeiter2)
    session.commit()
    return  mitarbeiter2

# Test Wartungszeitraum + Wartung erstellen
@pytest.fixture
def test_wartungszeitraum(app,session, test_zug, test_mitarbeiter):
    wzr = Wartungszeitraum(wartungszeitid=1,datum=date(2025, 12, 10),
                           von=datetime(2025, 12, 10, 9, 0),
                           bis=datetime(2025, 12, 10, 17, 0),dauer=480)
    session.add(wzr)
    session.commit()

    wartung = Wartung(wartungszeitid=wzr.wartungszeitid,svnr=test_mitarbeiter.svnr,zugid=test_zug.zugid)
    session.add(wartung)
    session.commit()
    return wzr

 # Mock-up für request.from
@pytest.fixture
def mock_request_form():

    class MockForm:
        def __init__(self, data):
            self._data = data

        # Simuliert request.form.get(key)
        def get(self, key, default=None):
            return self._data.get(key, default)

        # Simuliert request.form.getlist(key)  - brauch ich zb für Checkboxen
        def getlist(self, key):
            value = self._data.get(key, [])
            if isinstance(value, list):
                return value
            return [value] if value else []

    return MockForm

 # Mock-up für request.from.args
@pytest.fixture
def mock_request_form_args():

    class MockRequest:
        def __init__(self, data):
            self.args = self
            self._data = data

        def get(self, key, default=None):
            return self._data.get(key, default)

    return MockRequest
