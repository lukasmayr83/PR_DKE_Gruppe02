import requests
from requests import RequestException
from datetime import datetime

from app import db
from app.models import Zug, ZugWartung


def _combine_date_time(date_str: str | None, time_str: str | None) -> datetime | None:
    if not date_str or not time_str:
        return None
    try:
        return datetime.fromisoformat(f"{date_str}T{time_str}")
    except ValueError:
        return None


def sync_wartungen_from_flotte(base_url: str) -> dict:
    """
    Holt Wartungen aus dem Flotten-Service und synchronisiert sie nach Fahrplan.

    Unterstützte JSON-Formate:
    A) flat list (empfohlen):
       [
         {"zugId": 1, "wartungszeitid": 10, "datum": "...", "von": "...", "bis": "..."},
         ...
       ]

    B) grouped by zug:
       [
         {"zugId": 1, "wartungen": [{"wartungszeitid": 10, "datum": "...", "von": "...", "bis": "..."}, ...]},
         ...
       ]

    Logik:
      - nur aktuelle + zukünftige Wartungen (bis < now wird ignoriert)
      - pro Zug: lokale Wartungen löschen und neu einfügen
    """
    url = f"{base_url.rstrip('/')}/api/wartungen-export"

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (RequestException, ValueError) as e:
        return {"ok": False, "error": f"Fetch/JSON failed: {e}"}

    if not isinstance(data, list):
        return {"ok": False, "error": "Unexpected JSON shape (expected list)."}

    now = datetime.now()

    try:
        # -----------------------
        # 1) INPUT NORMALISIEREN -> groups[zugId] = [wartung_dict, ...]
        # -----------------------
        groups: dict[int, list[dict]] = {}

        for it in data:
            if not isinstance(it, dict):
                continue

            # Format B: {"zugId": X, "wartungen": [...]}
            if "wartungen" in it and isinstance(it.get("wartungen"), list):
                zug_id = int(it["zugId"])
                groups.setdefault(zug_id, []).extend(it["wartungen"])
                continue

            # Format A: flat wartung item
            # {"zugId": X, "wartungszeitid": Y, "datum": ..., "von": ..., "bis": ...}
            if "zugId" in it and "wartungszeitid" in it:
                zug_id = int(it["zugId"])
                groups.setdefault(zug_id, []).append(it)
                continue

        zuege_seen = len(groups)
        zuege_missing = 0
        wartungen_inserted = 0
        deleted_total = 0

        # -----------------------
        # 2) pro Zug sync
        # -----------------------
        for ext_zug_id, wartungen in groups.items():
            zug = Zug.query.filter_by(external_id=int(ext_zug_id)).first()
            if not zug:
                zuege_missing += 1
                continue

            # 2a) bestehende Wartungen des Zuges löschen (einmal!)
            deleted_total += (
                ZugWartung.query.filter_by(zug_id=zug.id)
                .delete(synchronize_session=False)
            )

            # 2b) neue Wartungen einfügen
            seen_wzids: set[int] = set()

            for w in wartungen:
                if not isinstance(w, dict):
                    continue

                wzid_raw = w.get("wartungszeitid") or w.get("wartungszeitId")
                if wzid_raw is None:
                    continue

                wzid = int(wzid_raw)
                if wzid in seen_wzids:
                    continue
                seen_wzids.add(wzid)

                von_dt = _combine_date_time(w.get("datum"), w.get("von"))
                bis_dt = _combine_date_time(w.get("datum"), w.get("bis"))
                if not von_dt or not bis_dt:
                    continue

                if bis_dt < now:
                    continue

                db.session.add(
                    ZugWartung(
                        zug_id=zug.id,
                        external_wartungszeitid=wzid,
                        von=von_dt,
                        bis=bis_dt,
                    )
                )
                wartungen_inserted += 1

        db.session.commit()
        return {
            "ok": True,
            "zuege_seen": zuege_seen,
            "zuege_missing_in_fahrplan": zuege_missing,
            "deleted_local_rows": deleted_total,
            "wartungen_inserted": wartungen_inserted,
        }

    except Exception as e:
        db.session.rollback()
        return {"ok": False, "error": str(e)}
