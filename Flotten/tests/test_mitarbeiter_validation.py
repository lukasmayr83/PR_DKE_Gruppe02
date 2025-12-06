import pytest
from app.mitarbeiter_validation import validate_unique_svnr, validate_unique_username
from app.models import Mitarbeiter, User, Role

 # Tests für eindeutige svnr
class TestValidateUniqueSvnr:

    def test_svnr_verfuegbar(self, app):
        with app.app_context():
            valid, msg = validate_unique_svnr(9999999999)

            assert valid is True
            assert msg is None

    def test_svnr_bereits_vergeben(self, app, test_mitarbeiter):
        with app.app_context():
            valid, msg = validate_unique_svnr(test_mitarbeiter.svnr)

            assert valid is False
            assert "bereits vergeben" in msg

    def test_svnr_bearbeiten_unveraendert(self, app, test_mitarbeiter):
        with app.app_context():
            valid, msg = validate_unique_svnr(
                test_mitarbeiter.svnr,
                current_svnr=test_mitarbeiter.svnr
            )
            assert valid is True
            assert msg is None

    def test_svnr_bearbeiten_auf_vergebene_svnr(self, app,test_mitarbeiter, test_mitarbeiter2):
        with app.app_context():
            # Versuche SVNR von test_mitarbeiter auf SVNR von test_mitarbeiter2 zu ändern
            valid, msg = validate_unique_svnr(
                test_mitarbeiter2.svnr,
                current_svnr=test_mitarbeiter.svnr
            )
            assert valid is False
            assert "bereits vergeben" in msg

    def test_svnr_bearbeiten_auf_neue_svnr(self, app,  test_mitarbeiter):
        with app.app_context():
            valid, msg = validate_unique_svnr(
                8888888888,  # Neue SVNR
                current_svnr=test_mitarbeiter.svnr
            )
            assert valid is True
            assert msg is None

 # Tests für eindeutige Usernamen
class TestValidateUniqueUsername:

    def test_username_verfuegbar(self, app):
        with app.app_context():
            valid, msg = validate_unique_username("neuer_user")

            assert valid is True
            assert msg is None

    def test_username_bereits_vergeben(self, app, test_user):
        with app.app_context():
            valid, msg = validate_unique_username(test_user.username)

            assert valid is False
            assert "Benutzername" in msg
            assert "bereits vergeben" in msg

    def test_username_bearbeiten_unveraendert(self, app, test_user):
        with app.app_context():
            valid, msg = validate_unique_username(
                test_user.username,
                current_user_id=test_user.id
            )
            assert valid is True
            assert msg is None

    def test_username_bearbeiten_auf_vergebenen_username(self, app, test_user, test_user2):
        with app.app_context():
            # Versuche Username von test_user auf Username von test_user2 zu ändern
            valid, msg = validate_unique_username(
                test_user2.username,
                current_user_id=test_user.id
            )
            assert valid is False
            assert "bereits vergeben" in msg

    def test_username_bearbeiten_auf_neuen_username(self, app, test_user):
        with app.app_context():
            valid, msg = validate_unique_username(
                "komplett_neuer_username",
                current_user_id=test_user.id
            )
            assert valid is True
            assert msg is None

