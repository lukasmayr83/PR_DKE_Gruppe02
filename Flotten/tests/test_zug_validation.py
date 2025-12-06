import pytest
from app.zug_validation import validate_zug
from app.models import Wagen, Personenwagen, Triebwagen, Zuege

 # Test für Zug Validation
class TestValidateZug:

    def test_validate_zug_erfolgreich(self, app, test_triebwagen, test_personenwagen, mock_request_form):
        with app.app_context():
            form_data = {
                'triebwagen_id': str(test_triebwagen.wagenid),
                'personenwagen_ids': [str(test_personenwagen.wagenid)]
            }
            request_form = mock_request_form(form_data)

            valid, tw, pws, msg = validate_zug(request_form)

            assert valid is True
            assert tw is not None
            assert tw.wagenid == test_triebwagen.wagenid
            assert len(pws) == 1
            assert pws[0].wagenid == test_personenwagen.wagenid
            assert msg is None

    # Test keinen Triebwagen auswählen
    def test_validate_zug_kein_triebwagen(self, app, mock_request_form, test_personenwagen):
        with app.app_context():
            form_data = {
                'triebwagen_id': None,
                'personenwagen_ids': [str(test_personenwagen.wagenid)]
            }
            request_form = mock_request_form(form_data)

            valid, tw, pws, msg = validate_zug(request_form)

            assert valid is False
            assert tw is None
            assert "Triebwagen" in msg

    # Test keinen Personenwagen ausgewählt
    def test_validate_zug_kein_personenwagen(self, app, test_triebwagen, mock_request_form):
        with app.app_context():
            form_data = {
                'triebwagen_id': str(test_triebwagen.wagenid),
                'personenwagen_ids': []
            }
            request_form = mock_request_form(form_data)

            valid, tw, pws, msg = validate_zug(request_form)

            assert valid is False
            assert pws is None
            assert "Personenwagen" in msg

    # Test Zug mit unterschiedliche Wagen Spurweiten
    def test_validate_zug_spurweite_unterschiedlich(self, app,test_triebwagen, test_personenwagen_andere_spurweite, mock_request_form):
        with app.app_context():
            form_data = {
                'triebwagen_id': str(test_triebwagen.wagenid),
                'personenwagen_ids': [str(test_personenwagen_andere_spurweite.wagenid)]
            }
            request_form = mock_request_form(form_data)

            valid, tw, pws, msg = validate_zug(request_form)

            assert valid is False
            assert "Spurweite" in msg

    # Test Personenwagen zu schwer
    def test_validate_zug_schwer(self, app,test_triebwagen, test_personenwagen_schwer, mock_request_form):
        with app.app_context():
            form_data = {
                'triebwagen_id': str(test_triebwagen.wagenid),
                'personenwagen_ids': [str(test_personenwagen_schwer.wagenid)]
            }
            request_form = mock_request_form(form_data)

            valid, tw, pws, msg = validate_zug(request_form)

            assert valid is False
            assert "schwer" in msg.lower()

    # Test zug mit mehreren Personenwagen
    def test_validate_zug_mehrere_personenwagen(self, app, session, test_triebwagen, mock_request_form):
        """Test: Mehrere Personenwagen"""
        with app.app_context():
            pw1 = Personenwagen(wagenid=10, spurweite=1435.0, kapazitaet=50, maxgewicht=30.0)
            pw2 = Personenwagen(wagenid=11, spurweite=1435.0, kapazitaet=50, maxgewicht=30.0)
            session.add_all([pw1, pw2])
            session.commit()

            form_data = {
                'triebwagen_id': str(test_triebwagen.wagenid),
                'personenwagen_ids': [str(pw1.wagenid), str(pw2.wagenid)]
            }
            request_form = mock_request_form(form_data)

            valid, tw, pws, msg = validate_zug(request_form)

            assert valid is True
            assert tw is not None
            assert len(pws) == 2