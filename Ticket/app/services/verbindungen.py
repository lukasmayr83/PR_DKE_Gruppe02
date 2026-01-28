"""
23.01.2026/ Daniel Schober:

Dieser Service sucht Zugverbindungen zwischen zwei Bahnhöfen auf Basis
 eines Fahrplan "Snapshots" (JSON vom Fahrplan-Service)

 Es können Direktverbindungen und Verbindungen mit einem Umstieg gesucht werden.

 Die UI verwendet Dropdowns wodurch Start/Zielbahnhöfe exakt reinkommen und nicht
 normalisiert werden müssen.

 Das "Matching" kann jetzt über die Namens-Übereinstimmung erfolgen.
 
 Ablauf grob:
    - Fahrplan-Snapshot holen
    - Snapshot in interne Struktur "rides" umwandeln (build_rides)
    (ride ist eine konkrete Fahrt (FahrtdurchfuehrungId) mit Liste von Halten = "stops")
    - Für jede Fahrt dann:
        prüfen ob Start und Ziel vorkommen + richtige Reihenfolge
        Zeiten prüfen (Datum, Ab-Zeit)
        Preis für Segment berechnen (Summe von den Tarifen)

    - Für Umstiege:
        1. Fahrt: Start - irgendein Halt danach als Umstieg
        2. Fahrt: muss den Umstieg als Halt haben und danach das Ziel
        Umstiegszeit muss zwischen MIN nud MAX sein
        Preis = Preis von 1. Segment + Preis von 2. Segment

        Ergebnis: LIste von VerbindungsHit-Objekten sortiert nach Abfahrt, Umstiegen, Ankunft
"""



from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Dict, Any, Tuple

from app.services.external_clients import fahrplan_snapshot


# Umstiegsregeln
MIN_UMSTIEG_MIN = 5        # mind. 5 Minuten Umstieg
MAX_UMSTIEG_MIN = 30      # max  warten

# Ergebnis Datensatz für eine gefundene Verbindung, kann entweder Direktverbindung
# sein, oder 1 Umstieg haben (dann sind 2. Teilfahrt-Felder gesetzt)
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

# Zweck: im "Snapshot" sind Zeiten ISO Strings zB "2026-01-23T12:30:00",
# brauche datetime Objekte zum Vergleichen
def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str)

# baut aus dem JSON Snapshot eine Liste an "rides" (eine Fahrt)
# inkl Liste an Halten "stops"
def _build_rides(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    rides = []

    # snap "items" = Liste an Fahrten, jede Fahrt = f
    for f in (snap.get("items") or []):
        stops = []
        # jede Fahrt hat Haltepunkte, Halte als Liste
        for s in (f.get("haltepunkte") or []):
            name = (s.get("bahnhofName") or "").strip()
            # plan Abfahrt und Ankunft sind ISO Strings - parsen
            dep = _parse_iso(s.get("planAbfahrt") or s.get("planAnkunft"))
            arr = _parse_iso(s.get("planAnkunft") or s.get("planAbfahrt"))
            # tarif ist der Preis von einem "Segment" ab dem halt
            tarif = float(s.get("tarif") or 0.0)
            # Stops Elemente hinzufügen
            stops.append(
                {
                    "name": name,
                    "dep": dep,
                    "arr": arr,
                    "tarif": tarif,
                }
            )
        # idx_map = Liste von Indizes pro Bahnhof-Name (Bahnhof kann öfter vorkommen)
        # warum idx_map: damit Position von Bahnhof schnell gefunden werden kann
        idx_map: Dict[str, List[int]] = {}
        for i, st in enumerate(stops):
            idx_map.setdefault(st["name"], []).append(i)

# Fahrt in rides Liste anhängen
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
    Berechnet den Preis zwischen 2 Stop Indizes

    "tarif" ist segmentweise ab dem nächsten Halt

    summieren von stops[from+1 .. to] 
    """
    p = 0.0
    for i in range(i_from + 1, i_to + 1):
        p += float(stops[i].get("tarif") or 0.0)
    return round(p, 2)

# HAUPTFUNKTION - sucht Verbindungen
# Eingaben Start/ Ziel Bahnhofsnamen exakt aus dem Dropdown
# Datum, optionale AbfahrtsZeit (also nicht vor dieser Uhrzeit)
def suche_verbindungen(
    start_name: str,
    ziel_name: str,
    datum: date,
    ab_zeit: Optional[time] = None,
    snapshot: Optional[Dict[str, Any]] = None,     # für Test: bereits übergebenen Snapshot nutzen
) -> List[VerbindungHit]:

# SNAPSHOT HOLEN (von extern Fahrplan...) bzw den gegebenen hernehmen
    snap = snapshot if snapshot is not None else fahrplan_snapshot()

    # den Snapshot in die oben definierte interne Struktur umwandlen
    rides = _build_rides(snap)

    hits: List[VerbindungHit] = []

    # ----------------------------
    # 1) Direktfahrten
    # ----------------------------
    for r in rides:
        stops = r["stops"]

        # alle Indizes wo Start/Ziel vorkommen
        idx_starts = r["idx_map"].get(start_name) or []
        idx_ziels = r["idx_map"].get(ziel_name) or []

        # wenn start/ziel gar nicht vorkommen KEINE Direktverbindung
        if not idx_starts or not idx_ziels:
            continue

        # Nimm frühesten Start; Ziel muss danach liegen -> nimm erstes Ziel > Start
        idx_start = min(idx_starts)
        # Ziel muss nach Start liegen, erstes Ziel j > idx_start
        idx_ziel = next((j for j in sorted(idx_ziels) if j > idx_start), None)
        if idx_ziel is None:
            continue

        # Abfahrt / Ankunft Zeiten aus stops ziehen
        dt_ab = stops[idx_start]["dep"] or stops[idx_start]["arr"]
        dt_an = stops[idx_ziel]["arr"] or stops[idx_ziel]["dep"]
        if not dt_ab or not dt_an:
            continue

        # Datum muss passen
        if dt_ab.date() != datum:
            continue

        # Ab-Zeit prüfen optional
        if ab_zeit and dt_ab.time() < ab_zeit:
            continue

        # Preis für Segment berechnen
        preis = _preis_segment(stops, idx_start, idx_ziel)

        # ergebnis speichern
        hits.append(
            VerbindungHit(
                fahrtdurchfuehrung_id=r["id"],
                halteplan_id=r["halteplan_id"],
                zug_id=r["zug_id"],
                start_name=start_name,
                ziel_name=ziel_name,
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

    # duplikate vermeiden 
    seen_keys: set[Tuple[int, int, str, datetime]] = set()

    # Erste Fahrt 
    for r1 in rides:
        s1 = r1["stops"]

        # start muss in r1 vorkommen
        idx_start_list = r1["idx_map"].get(start_name) or []
        if not idx_start_list:            continue

        idx_start_1 = min(idx_start_list)
        
        # Abfahrt von erster Fahrt
        dt_start = s1[idx_start_1]["dep"] or s1[idx_start_1]["arr"]
        if not dt_start:
            continue

        # Datum bzw ab zeit prüfen
        if dt_start.date() != datum:
            continue
        if ab_zeit and dt_start.time() < ab_zeit:
            continue

        # potenzielle Umstiegsbahnhöfe = jeder Halt NACH dem Start in r1
        for idx_t1 in range(idx_start_1 + 1, len(s1)):
            t_name = s1[idx_t1]["name"]
            # Ankunft am Umstieg in 1. Fahrt
            arr_t1 = s1[idx_t1]["arr"] or s1[idx_t1]["dep"]
            if not t_name or not arr_t1:
                continue

            # Preis 1. Leg Start -> Umstieg
            preis1 = _preis_segment(s1, idx_start_1, idx_t1)

            # suche 2. Fahrt, die an t_norm startet (bzw. dort einsteigt) und später Ziel enthält
            for r2 in rides:
                # gleiche Fahrt überspringen
                if r2["id"] == r1["id"]:
                    continue

                s2 = r2["stops"]

                # Umstieg muss in r2 vorkommen
                idx_ts2 = r2["idx_map"].get(t_name) or []
                if not idx_ts2:
                    continue

                # Ziel muss in r2 vorkommen
                idx_z2 = r2["idx_map"].get(ziel_name) or []
                if not idx_z2:
                    continue

                # nimm erstes Transfer-Index in r2 und erstes Ziel danach
                # (falls Bahnhof mehrfach vorkommt, probieren aller t-indizes)
                # Für jeden möglichen Umstieg-Index in r2 prüfen
                for idx_t2 in idx_ts2:
                    # ziel muss NACH umstieg liegen
                    idx_ziel_2 = next((j for j in sorted(idx_z2) if j > idx_t2), None)
                    if idx_ziel_2 is None:
                        continue
                    # Abfahrt 2. fahrt am Umstieg
                    dep_t2 = s2[idx_t2]["dep"]  # beim Umstieg - Abfahrt
                    if not dep_t2:
                        continue


                    # Umstiegszeit prüfen mit oben eingegebenen Werten
                    wait = dep_t2 - arr_t1
                    if wait < min_buf:
                        continue
                    if wait > max_buf:
                        continue
                    # Ankunft am finalen ziel
                    dt_arr_final = s2[idx_ziel_2]["arr"] or s2[idx_ziel_2]["dep"]
                    if not dt_arr_final:
                        continue

                    # Preis für 2. Segment (umstieg->ziel)
                    preis2 = _preis_segment(s2, idx_t2, idx_ziel_2)
                    
                    # Gesamtpreis
                    total = round(preis1 + preis2, 2)

                    # Duplikate vermeiden
                    key = (r1["id"], r2["id"], t_name, dt_start)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    # Treffer "Hit" speichern
                    hits.append(
                        VerbindungHit(
                            fahrtdurchfuehrung_id=r1["id"],
                            halteplan_id=r1["halteplan_id"],
                            zug_id=r1["zug_id"],
                            start_name=start_name,
                            ziel_name=ziel_name,
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

    # Sortierung: zuerst früh dann direkt vor umstieg dann Ankunft
    hits.sort(key=lambda x: (x.abfahrt, x.umstiege, x.ankunft))
    return hits
