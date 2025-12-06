import pytest
from datetime import date, datetime, time
import app.wartungszeitraum_validation as wartungszeitraum_validation

 # Wartungszeitraum Validation Test Klassen

 # Test ob zugid exisitert
class TestValidateZugExistiert:

    def test_zug_existiert(self, app, test_zug):
        with app.app_context():
            assert wartungszeitraum_validation.validate_zug_existiert(test_zug.zugid) is True

    def test_zug_existiert_nicht(self, app):
        with app.test_request_context():
            assert wartungszeitraum_validation.validate_zug_existiert(9999) is False

 # Tests für Datums validierung
class TestValidateDatetimeNichtVergangenheit:

    def test_datum_zukunft_gueltig(self, app):
        with app.test_request_context():
            datum = date(2026, 12, 31)
            von = time(10, 0)
            bis = time(12, 0)
            assert wartungszeitraum_validation.validate_datetime_nicht_vergangenheit(datum, von, bis) is True

    def test_datum_vergangenheit_ungueltig(self, app):
        with app.test_request_context():
            datum = date(2025, 12, 1)
            von = time(10, 0)
            bis = time(12, 0)
            assert wartungszeitraum_validation.validate_datetime_nicht_vergangenheit(datum, von, bis) is False

    def test_fehlendes_datum(self, app):
        with app.test_request_context():
            von = time(10, 0)
            bis = time(12, 0)
            assert wartungszeitraum_validation.validate_datetime_nicht_vergangenheit(None, von, bis) is False

    def test_fehlendes_von(self, app):
        with app.test_request_context():
            datum = date(2026, 12, 31)
            bis = time(12, 0)
            assert wartungszeitraum_validation.validate_datetime_nicht_vergangenheit(datum, None, bis) is False

    def test_fehlendes_bis(self, app):
        with app.test_request_context():
            datum = date(2026, 12, 31)
            von = time(10, 0)
            assert wartungszeitraum_validation.validate_datetime_nicht_vergangenheit(datum, von, None) is False

 # Test für Von - Bis Validierung
class TestValidateVonVorBis:

    def test_von_vor_bis_gueltig(self, app):
        with app.test_request_context():
            von = time(10, 0)
            bis = time(12, 0)
            assert wartungszeitraum_validation.validate_von_vor_bis(von, bis) is True

    def test_von_nach_bis_ungueltig(self, app):
        with app.test_request_context():
            von = time(14, 0)
            bis = time(12, 0)
            assert wartungszeitraum_validation.validate_von_vor_bis(von, bis) is False

    def test_von_gleich_bis_ungueltig(self, app):
        with app.test_request_context():
            von = time(12, 0)
            bis = time(12, 0)
            assert wartungszeitraum_validation.validate_von_vor_bis(von, bis) is False

 # Test für Mitarbeiter verfügbarkeit
class TestGetVerfuegbareMitarbeiter:

    def test_alle_mitarbeiter_verfuegbar(self, app,session, test_mitarbeiter, test_mitarbeiter2):
        with app.app_context():
            datum = date(2026, 1, 1)
            von = time(10, 0)
            bis = time(12, 0)

            verfuegbare = wartungszeitraum_validation.get_verfuegbare_mitarbeiter(datum, von, bis)

            assert len(verfuegbare) == 2  # weil ich zwei Testmitarbeiter angelegt habe

    def test_mitarbeiter_belegt( self, app, test_mitarbeiter2):
        with app.app_context():
            datum = date(2025, 12, 10)
            von = time(10, 0)
            bis = time(12, 0)

            verfuegbare = wartungszeitraum_validation.get_verfuegbare_mitarbeiter(datum, von, bis)

            # test_mitarbeiter ist belegt, test_mitarbeiter2 ist frei
            assert len(verfuegbare) == 1
            assert verfuegbare[0].svnr == test_mitarbeiter2.svnr

    # Test für Bearbeiten von Wartungen
    def test_ignore_wartung(self, app,test_wartungszeitraum,test_mitarbeiter, test_mitarbeiter2):
        with app.app_context():
            datum = date(2025, 12, 10)
            von = time(10, 0)
            bis = time(12, 0)

            # Mit ignore_wzid sollte test_mitarbeiter auch verfügbar sein
            verfuegbare = wartungszeitraum_validation.get_verfuegbare_mitarbeiter(
                datum, von, bis, ignore_wzid=test_wartungszeitraum.wartungszeitid
            )

            assert len(verfuegbare) == 2