import requests
from requests import RequestException

from app import db
from app.models import Zug


def sync_from_flotte(base_url: str) -> dict:
    """
    Holt /zuege vom Flotten-Service und spiegelt NUR Zug-Stammdaten
    in die Fahrplan-DB (keine Wartungslogik).
    """
    url = f"{base_url.rstrip('/')}/zuege"

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (RequestException, ValueError) as e:
        return {"ok": False, "error": f"Fetch/JSON failed: {e}"}

    if not isinstance(data, list):
        return {"ok": False, "error": "Unexpected JSON shape (expected list)."}

    try:
        created = 0
        updated = 0

        for it in data:
            ext_id = int(it["zugId"])

            zug = Zug.query.filter_by(external_id=ext_id).first()
            is_new = zug is None
            if is_new:
                zug = Zug(external_id=ext_id)
                db.session.add(zug)

            zug.bezeichnung = it.get("bezeichnung") or f"Zug {ext_id}"

            spurweite = it.get("spurweite")
            zug.spurweite = float(spurweite) if spurweite is not None else None

            if is_new:
                created += 1
            else:
                updated += 1

        db.session.commit()
        return {
            "ok": True,
            "zuege_total": len(data),
            "created": created,
            "updated": updated,
        }

    except Exception as e:
        db.session.rollback()
        return {"ok": False, "error": str(e)}
