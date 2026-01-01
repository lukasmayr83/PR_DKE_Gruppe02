from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Dict, Any, Tuple

from app.services.external_clients import (
    fahrplan_snapshot,
    strecken_bahnhoefe,
)

# Umstiegsregeln
MIN_UMSTIEG_MIN = 5        # mind. 5 Minuten Umstieg
MAX_UMSTIEG_MIN = 240      # max 4 Stunden warten


@dataclass
class VerbindungHit:
    # 1. Teilfahrt
    fahrtdurchfuehrung_id: int
    halteplan_id: int
    zug_id: int

    # Strecke (gesamt)
    start_name: str
    ziel_name: str
    abfahrt: datetime
    ankunft: datetime
    preis: float

    # Umstieg
    umstiege: int = 0
    umstieg_bahnhof: Optional[str] = None
    umstieg_ankunft: Optional[datetime] = None
    umstieg_abfahrt: Optional[datetime] = None

    # 2. Teilfahrt (nur wenn umstiege == 1)
    fahrtdurchfuehrung_id2: Optional[int] = None
    halteplan_id2: Optional[int] = None
    zug_id2: Optional[int] = None


def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str)


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _resolve_bahnhof_name(query: str) -> Optional[str]:
    """
    Nimmt einen User-String und holt Bahnhofs-Namen
    aus dem Strecken-Service (erste Übereinstimmung)
    """
    data = strecken_bahnhoefe(query)
    items = data.get("items", []) or []
    if not items:
        return None
    name = (items[0].get("name") or "").strip()
    return name or None


def _match_norm(stop_norm: str, cand_norms: List[str]) -> bool:
    """
    Robust: exact match ODER substring match (hilft bei kleinen Tippfehlern / Abkürzungen)
    """
    for c in cand_norms:
        if not c:
            continue
        if stop_norm == c:
            return True
        if stop_norm in c or c in stop_norm:
            return True
    return False


def _build_rides(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    rides: List[Dict[str, Any]] = []

    for f in (snap.get("items") or []):
        stops_raw = f.get("haltepunkte") or []
        stops: List[Dict[str, Any]] = []

        for s in stops_raw:
            name = (s.get("bahnhofName") or "").strip()
            dep = _parse_iso(s.get("planAbfahrt") or s.get("planAnkunft"))
            arr = _parse_iso(s.get("planAnkunft") or s.get("planAbfahrt"))
            tarif = float(s.get("tarif") or 0.0)

            stops.append(
                {
                    "name": name,
                    "norm": _norm(name),
                    "dep": dep,
                    "arr": arr,
                    "tarif": tarif,
                }
            )

        idx_map: Dict[str, List[int]] = {}
        for i, st in enumerate(stops):
            idx_map.setdefault(st["norm"], []).append(i)

        rides.append(
            {
                "id": int(f.get("fahrtdurchfuehrungId")),
                "halteplan_id": int(f.get("halteplanId") or 0),
                "zug_id": int(f.get("zugId") or 0),
                "stops": stops,
                "idx_map": idx_map,
            }
        )

    return rides


def _preis_segment(stops: List[Dict[str, Any]], i_from: int, i_to: int) -> float:
    """
    Preisberechnung: tarif ist segmentweise ab dem nächsten Halt
    Daher summieren wir stops[from+1 .. to] inklusive
    """
    p = 0.0
    for i in range(i_from + 1, i_to + 1):
        p += float(stops[i].get("tarif") or 0.0)
    return round(p, 2)


def _find_indices_for_candidates(
    stops: List[Dict[str, Any]],
    cand_norms: List[str],
) -> List[int]:
    out = []
    for i, st in enumerate(stops):
        if _match_norm(st["norm"], cand_norms):
            out.append(i)
    return out


def suche_verbindungen(
    start_name: str,
    ziel_name: str,
    datum: date,
    ab_zeit: Optional[time] = None,
    snapshot: Optional[Dict[str, Any]] = None,
) -> List[VerbindungHit]:
    """
    findet Direktverbindungen, 1-Umstieg-Verbindungen (1 Umstieg)

    Matching per bahnhofName (Snapshot) – Verwendung name (nicht ID)
    """

    start_canon = _resolve_bahnhof_name(start_name) or start_name
    ziel_canon = _resolve_bahnhof_name(ziel_name) or ziel_name

    # Kandidaten als Norm-Strings
    start_cands = list(dict.fromkeys([_norm(start_canon), _norm(start_name)]))
    ziel_cands = list(dict.fromkeys([_norm(ziel_canon), _norm(ziel_name)]))

    snap = snapshot if snapshot is not None else fahrplan_snapshot()
    rides = _build_rides(snap)

    hits: List[VerbindungHit] = []

    # ----------------------------
    # 1) Direktfahrten
    # ----------------------------
    for r in rides:
        stops = r["stops"]

        idx_starts = _find_indices_for_candidates(stops, start_cands)
        idx_ziels = _find_indices_for_candidates(stops, ziel_cands)

        if not idx_starts or not idx_ziels:
            continue

        # Nimm frühesten Start; Ziel muss danach liegen -> nimm erstes Ziel > Start
        idx_start = min(idx_starts)
        idx_ziel = next((j for j in sorted(idx_ziels) if j > idx_start), None)
        if idx_ziel is None:
            continue

        dt_ab = stops[idx_start]["dep"] or stops[idx_start]["arr"]
        dt_an = stops[idx_ziel]["arr"] or stops[idx_ziel]["dep"]
        if not dt_ab or not dt_an:
            continue

        if dt_ab.date() != datum:
            continue
        if ab_zeit and dt_ab.time() < ab_zeit:
            continue

        preis = _preis_segment(stops, idx_start, idx_ziel)

        hits.append(
            VerbindungHit(
                fahrtdurchfuehrung_id=r["id"],
                halteplan_id=r["halteplan_id"],
                zug_id=r["zug_id"],
                start_name=stops[idx_start]["name"] or start_canon,
                ziel_name=stops[idx_ziel]["name"] or ziel_canon,
                abfahrt=dt_ab,
                ankunft=dt_an,
                preis=preis,
                umstiege=0,
            )
        )

    # ----------------------------
    # 2) 1 Umstieg
    # ----------------------------
    min_buf = timedelta(minutes=MIN_UMSTIEG_MIN)
    max_buf = timedelta(minutes=MAX_UMSTIEG_MIN)

    seen_keys: set[Tuple[int, int, str, datetime]] = set()

    for r1 in rides:
        s1 = r1["stops"]

        idx_starts_1 = _find_indices_for_candidates(s1, start_cands)
        if not idx_starts_1:
            continue

        idx_start_1 = min(idx_starts_1)
        dt_start = s1[idx_start_1]["dep"] or s1[idx_start_1]["arr"]
        if not dt_start:
            continue

        if dt_start.date() != datum:
            continue
        if ab_zeit and dt_start.time() < ab_zeit:
            continue

        # potenzielle Umstiegsbahnhöfe = alle Halte nach Start (nicht Start selbst)
        for idx_t1 in range(idx_start_1 + 1, len(s1)):
            t_name = s1[idx_t1]["name"]
            t_norm = s1[idx_t1]["norm"]
            if not t_name or not t_norm:
                continue

            arr_t1 = s1[idx_t1]["arr"] or s1[idx_t1]["dep"]
            if not arr_t1:
                continue

            # Preis 1. Leg Start -> Umstieg
            preis1 = _preis_segment(s1, idx_start_1, idx_t1)

            # suche 2. Fahrt, die an t_norm startet (bzw. dort einsteigt) und später Ziel enthält
            for r2 in rides:
                if r2["id"] == r1["id"]:
                    continue

                s2 = r2["stops"]

                # Umstieg muss in r2 vorkommen
                idx_ts2 = r2["idx_map"].get(t_norm) or []
                if not idx_ts2:
                    continue

                # Ziel muss in r2 vorkommen
                idx_ziels_2 = _find_indices_for_candidates(s2, ziel_cands)
                if not idx_ziels_2:
                    continue

                # nimm erstes Transfer-Index in r2 und erstes Ziel danach
                # (falls Bahnhof mehrfach vorkommt, probieren aller t-indices)
                for idx_t2 in idx_ts2:
                    idx_ziel_2 = next((j for j in sorted(idx_ziels_2) if j > idx_t2), None)
                    if idx_ziel_2 is None:
                        continue

                    dep_t2 = s2[idx_t2]["dep"]  # beim Umstieg - Abfahrt
                    if not dep_t2:
                        continue


                    # Umstiegszeit prüfen
                    wait = dep_t2 - arr_t1
                    if wait < min_buf:
                        continue
                    if wait > max_buf:
                        continue

                    dt_arr_final = s2[idx_ziel_2]["arr"] or s2[idx_ziel_2]["dep"]
                    if not dt_arr_final:
                        continue

                    preis2 = _preis_segment(s2, idx_t2, idx_ziel_2)
                    total = round(preis1 + preis2, 2)

                    key = (r1["id"], r2["id"], t_norm, dt_start)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    hits.append(
                        VerbindungHit(
                            fahrtdurchfuehrung_id=r1["id"],
                            halteplan_id=r1["halteplan_id"],
                            zug_id=r1["zug_id"],
                            start_name=s1[idx_start_1]["name"] or start_canon,
                            ziel_name=s2[idx_ziel_2]["name"] or ziel_canon,
                            abfahrt=dt_start,
                            ankunft=dt_arr_final,
                            preis=total,
                            umstiege=1,
                            umstieg_bahnhof=t_name,
                            umstieg_ankunft=arr_t1,
                            umstieg_abfahrt=dep_t2,
                            fahrtdurchfuehrung_id2=r2["id"],
                            halteplan_id2=r2["halteplan_id"],
                            zug_id2=r2["zug_id"],
                        )
                    )

    # Sortierung: zuerst früh dann direkt vor umstieg
    hits.sort(key=lambda x: (x.abfahrt, x.umstiege, x.ankunft))
    return hits
