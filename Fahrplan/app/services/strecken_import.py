import requests
from requests import RequestException

from app import db
from app.models import Bahnhof, Abschnitt, Strecke, StreckeAbschnitt


def sync_from_strecken(base_url: str) -> dict:
    """
    Holt /api/strecken-export vom Strecken-Service und spiegelt in die Fahrplan-DB.
    base_url z.B. "http://127.0.0.1:5001"
    """
    url = f"{base_url.rstrip('/')}/api/strecken-export"

    # -----------------------
    # 0) Daten holen (robust)
    # -----------------------
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (RequestException, ValueError) as e:
        return {"ok": False, "error": f"Fetch/JSON failed: {e}"}

    missing_bahnhoefe_refs = 0
    missing_abschnitt_refs = 0

    try:
        # -----------------------
        # 1) Bahnhöfe upserten
        # -----------------------
        bahnhof_map = {}  # external_id -> internal id (DB pk)
        for b in data.get("bahnhoefe", []):
            ext_id = int(b["id"])
            obj = Bahnhof.query.filter_by(external_id=ext_id).first()
            if obj is None:
                obj = Bahnhof(external_id=ext_id)
                db.session.add(obj)

            obj.name = b.get("name")

            db.session.flush()  # damit obj.id verfügbar ist
            bahnhof_map[ext_id] = obj.id

        # -----------------------
        # 2) Abschnitte upserten
        # -----------------------
        abschnitt_map = {}  # external_id -> internal id
        for a in data.get("abschnitte", []):
            ext_id = int(a["id"])
            obj = Abschnitt.query.filter_by(external_id=ext_id).first()
            if obj is None:
                obj = Abschnitt(external_id=ext_id)
                db.session.add(obj)

            obj.spurweite = a.get("spurweite")
            obj.max_geschwindigkeit = a.get("maxGeschwindigkeit")
            obj.nutzungsentgelt = a.get("nutzungsentgelt")
            obj.laenge = a.get("laenge")

            start_ext = int(a["startBahnhofId"])
            end_ext = int(a["endBahnhofId"])

            obj.start_bahnhof_id = bahnhof_map.get(start_ext)
            obj.end_bahnhof_id = bahnhof_map.get(end_ext)

            if obj.start_bahnhof_id is None or obj.end_bahnhof_id is None:
                missing_bahnhoefe_refs += 1

            db.session.flush()
            abschnitt_map[ext_id] = obj.id

        # -----------------------
        # 3) Strecken upserten + Join-Tabelle neu setzen
        # -----------------------
        strecken_count = 0
        links_count = 0

        for s in data.get("strecken", []):
            ext_id = int(s["id"])
            obj = Strecke.query.filter_by(external_id=ext_id).first()
            if obj is None:
                obj = Strecke(external_id=ext_id)
                db.session.add(obj)

            obj.name = s.get("name")
            db.session.flush()
            strecken_count += 1

            # Join-Einträge für diese Strecke komplett neu aufbauen
            (
                StreckeAbschnitt.query
                .filter_by(strecke_id=obj.id)
                .delete(synchronize_session=False)
            )

            for pos, abs_ext_id in enumerate(s.get("abschnittIds", []), start=1):
                abs_int_id = abschnitt_map.get(int(abs_ext_id))
                if abs_int_id is None:
                    missing_abschnitt_refs += 1
                    continue

                db.session.add(
                    StreckeAbschnitt(
                        strecke_id=obj.id,
                        abschnitt_id=abs_int_id,
                        position=pos,
                    )
                )
                links_count += 1

        db.session.commit()

        return {
            "ok": True,
            "bahnhoefe": len(bahnhof_map),
            "abschnitte": len(abschnitt_map),
            "strecken": strecken_count,
            "strecke_abschnitt_links": links_count,
            "missing_bahnhoefe_refs": missing_bahnhoefe_refs,
            "missing_abschnitt_refs": missing_abschnitt_refs,
        }

    except Exception as e:
        db.session.rollback()
        return {"ok": False, "error": str(e)}
