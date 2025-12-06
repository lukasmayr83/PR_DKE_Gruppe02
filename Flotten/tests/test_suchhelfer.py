import pytest
import app.suchhelfer as suchhelfer
from app.models import User, Role, Personenwagen, Triebwagen, Zuege, Wagen, Mitarbeiter, Wartungszeitraum,Wartung

 # Mitarbeiter
def test_search_mitarbeiter_no_query(test_mitarbeiter, mock_request_form_args):
    req = mock_request_form_args({})
    result = suchhelfer.search_mitarbeiter(req)
    assert test_mitarbeiter in result

def test_search_mitarbeiter_with_query(test_mitarbeiter, mock_request_form_args):
    req = mock_request_form_args({"q": "Max"})
    result = suchhelfer.search_mitarbeiter(req)
    assert test_mitarbeiter in result


 # Personenwagen
def test_search_personenwagen_no_query(test_personenwagen, mock_request_form_args):
    req = mock_request_form_args({})
    result = suchhelfer.search_personenwagen(req)
    assert test_personenwagen in result

def test_search_personenwagen_with_query(test_personenwagen, mock_request_form_args):
    req = mock_request_form_args({"q": str(test_personenwagen.kapazitaet)})
    result = suchhelfer.search_personenwagen(req)
    assert test_personenwagen in result


 # TRIEBWAGEN
def test_search_triebwagen_no_query(test_triebwagen, mock_request_form_args):
    req = mock_request_form_args({})
    result = suchhelfer.search_triebwagen(req)
    assert test_triebwagen in result

def test_search_triebwagen_with_query(test_triebwagen, mock_request_form_args):
    req = mock_request_form_args({"q": str(test_triebwagen.maxzugkraft)})
    result = suchhelfer.search_triebwagen(req)
    assert test_triebwagen in result


# ZÜGE
def test_search_zuege_no_query(test_zug, mock_request_form_args):
    req = mock_request_form_args({})
    result = suchhelfer.search_zuege(req)
    assert test_zug in result

def test_search_zuege_with_query(test_zug, mock_request_form_args):
    req = mock_request_form_args({"q": "Test-Zug"})
    result = suchhelfer.search_zuege(req)
    assert test_zug in result


# Freie Triebwagen in Züge hinzufügen
def test_search_freie_triebwagen_no_query(test_triebwagen, mock_request_form_args):
    req = mock_request_form_args({})
    result = suchhelfer.search_freie_triebwagen(req)
    assert test_triebwagen in result

def test_search_freie_triebwagen_with_query( test_triebwagen, mock_request_form_args):
    req = mock_request_form_args({"search_tw": str(test_triebwagen.maxzugkraft)})
    result = suchhelfer.search_freie_triebwagen(req)
    assert test_triebwagen in result

# Freie Personenwagen in Züge hinzufügen
def test_search_freie_personenwagen_no_query(test_personenwagen, mock_request_form_args):
    req = mock_request_form_args({})
    result = suchhelfer.search_freie_personenwagen(req)
    assert test_personenwagen in result

def test_search_freie_personenwagen_with_query(test_personenwagen, mock_request_form_args):
    req = mock_request_form_args({"search_pw": str(test_personenwagen.kapazitaet)})
    result = suchhelfer.search_freie_personenwagen(req)
    assert test_personenwagen in result



# Freie Triebwagen für Züge bearbeiten
def test_search_triebwagen_for_zug_bearbeiten_no_query(test_triebwagen, test_zug, mock_request_form_args):
    req = mock_request_form_args({"search_tw": ""})
    result = suchhelfer.search_triebwagen_for_zug_bearbeiten(req, test_zug.zugid)
    assert test_triebwagen in result

def test_search_triebwagen_for_zug_bearbeiten_with_query(test_triebwagen, test_zug, mock_request_form_args):
    req = mock_request_form_args({"search_tw": str(test_triebwagen.maxzugkraft)})
    result = suchhelfer.search_triebwagen_for_zug_bearbeiten(req, test_zug.zugid)
    assert test_triebwagen in result

# Freie Personenwagen für Züge bearbeiten
def test_search_personenwagen_for_zug_bearbeiten_no_query(test_personenwagen, test_zug, mock_request_form_args):
    req = mock_request_form_args({"search_pw": ""})
    result = suchhelfer.search_personenwagen_for_zug_bearbeiten(req, test_zug.zugid)
    assert test_personenwagen in result

def test_search_personenwagen_for_zug_bearbeiten_with_query(test_personenwagen, test_zug, mock_request_form_args):
    req = mock_request_form_args({"search_pw": str(test_personenwagen.kapazitaet)})
    result = suchhelfer.search_personenwagen_for_zug_bearbeiten(req, test_zug.zugid)
    assert test_personenwagen in result

# Wartungen
def test_search_wartungen_no_query(test_wartungszeitraum, mock_request_form_args):
    req = mock_request_form_args({})
    result = suchhelfer.search_wartungen(req)
    assert test_wartungszeitraum in result

def test_search_wartungen_with_query(test_wartungszeitraum, mock_request_form_args):
    req = mock_request_form_args({"q": str(test_wartungszeitraum.wartungszeitid)})
    result = suchhelfer.search_wartungen(req)
    assert test_wartungszeitraum in result
