from __future__ import annotations

from typing import Dict, List, Tuple, Optional, Any

import sqlalchemy as sa
from app import db
from app.models import StreckeAbschnitt, Abschnitt



DEFAULT_KM_PER_ABSCHNITT: float = 1.0

# faktor für Mindestzeit, (laenge/vmax) *60 *0,75:
DEFAULT_SPEED_FACTOR: float = 0.75




def _load_strecke_abschnitte(strecke_id: int) -> List[dict]:
    rows = db.session.execute(
        sa.select(
            StreckeAbschnitt.position,
            Abschnitt.start_bahnhof_id,
            Abschnitt.end_bahnhof_id,
            Abschnitt.nutzungsentgelt,
            Abschnitt.max_geschwindigkeit,
            Abschnitt.laenge,          # FIX
        )
        .join(Abschnitt, Abschnitt.id == StreckeAbschnitt.abschnitt_id)
        .where(StreckeAbschnitt.strecke_id == strecke_id)
        .order_by(StreckeAbschnitt.position)
    ).all()

    result: List[dict] = []
    for _, start_b, end_b, entgelt, vmax, laenge in rows:
        km = float(laenge) if laenge else DEFAULT_KM_PER_ABSCHNITT

        result.append({
            "start_bahnhof_id": int(start_b),
            "end_bahnhof_id": int(end_b),
            "nutzungsentgelt": float(entgelt or 0.0),
            "vmax": int(vmax or 0),
            "km": km,
        })

    return result


def _derive_bahnhof_chain(abschnitte: List[dict]) -> List[int]:
    """
    Leitet aus den Abschnittsdaten die Bahnhofskette in Reihenfolge ab:
    [B0, B1, B2, ...]
    """
    if not abschnitte:
        return []

    chain: List[int] = [abschnitte[0]["start_bahnhof_id"]]
    for a in abschnitte:
        chain.append(a["end_bahnhof_id"])
    return chain


def _build_prefix_sums(
    abschnitte: List[dict],
    speed_factor: float,
) -> Tuple[List[float], List[float]]:
    """
    Prefix-Summen:
      - cost_prefix[k] = Summe nutzungsentgelt der ersten k Abschnitte
      - time_prefix[k] = Summe minuten der ersten k Abschnitte
    Prefix-Listen haben Länge len(abschnitte)+1 und starten mit 0.
    """
    cost_prefix: List[float] = [0.0]
    time_prefix: List[float] = [0.0]

    for a in abschnitte:
        cost_prefix.append(cost_prefix[-1] + float(a["nutzungsentgelt"]))

        vmax = float(a["vmax"])
        km = float(a["km"])

        # Dauerformel:
        # Stunden = km / (vmax * speed_factor)
        # Minuten = Stunden * 60
        if vmax <= 0:
            minutes = 0.0
        else:
            effective_speed = vmax * float(speed_factor)
            minutes = (km / effective_speed) * 60.0

        time_prefix.append(time_prefix[-1] + minutes)

    return cost_prefix, time_prefix




def compute_min_cost_map(strecke_id: int) -> Dict[Tuple[int, int], float]:
    """
    Liefert min_cost für ALLE "von_bahnhof_id -> nach_bahnhof_id" entlang der Strecke.
    min_cost = Summe nutzungsentgelt aller Abschnitte zwischen den beiden Bahnhöfen
    entlang der Strecken-Reihenfolge.

    Key: (from_bahnhof_id, to_bahnhof_id)
    """
    abschnitte = _load_strecke_abschnitte(strecke_id)
    chain = _derive_bahnhof_chain(abschnitte)
    if not chain:
        return {}

    cost_prefix, _ = _build_prefix_sums(abschnitte, speed_factor=DEFAULT_SPEED_FACTOR)

    min_map: Dict[Tuple[int, int], float] = {}
    n = len(chain)
    for i in range(n):
        for j in range(i + 1, n):
            b_from = chain[i]
            b_to = chain[j]
            min_cost = cost_prefix[j] - cost_prefix[i]
            min_map[(b_from, b_to)] = float(min_cost)

    return min_map


def compute_min_duration_map(
    strecke_id: int,
    speed_factor: float = DEFAULT_SPEED_FACTOR,
) -> Dict[Tuple[int, int], int]:
    """
    Liefert Mindestdauer in Minuten für ALLE Bahnhof-Paare entlang der Strecke.

    - verwendet Abschnitt.km, falls vorhanden (z.B. Abschnitt.laenge_km)
    - sonst fallback DEFAULT_KM_PER_ABSCHNITT
    - speed_factor (z.B. 0.75) reduziert die effektive Geschwindigkeit
    """
    abschnitte = _load_strecke_abschnitte(strecke_id)
    chain = _derive_bahnhof_chain(abschnitte)
    if not chain:
        return {}

    _, time_prefix = _build_prefix_sums(abschnitte, speed_factor=speed_factor)

    dur_map: Dict[Tuple[int, int], int] = {}
    n = len(chain)
    for i in range(n):
        for j in range(i + 1, n):
            b_from = chain[i]
            b_to = chain[j]
            minutes = time_prefix[j] - time_prefix[i]

            # "Mindestdauer" => aufrunden (damit nicht zu optimistisch)
            dur_map[(b_from, b_to)] = int(minutes + 0.999)

    return dur_map


def compute_stats_between(
    strecke_id: int,
    from_bahnhof_id: int,
    to_bahnhof_id: int,
    speed_factor: float = DEFAULT_SPEED_FACTOR,
) -> Dict[str, float | int]:
    """
    Liefert Mindestkosten + Mindestdauer für ein konkretes Bahnhofpaar
    entlang der Strecken-Reihenfolge.
    """
    abschnitte = _load_strecke_abschnitte(strecke_id)
    chain = _derive_bahnhof_chain(abschnitte)
    if not chain:
        raise ValueError("Strecke hat keine Abschnitte.")

    index_of = {b: i for i, b in enumerate(chain)}
    if from_bahnhof_id not in index_of or to_bahnhof_id not in index_of:
        raise ValueError("Bahnhof liegt nicht auf der Strecke.")

    i = index_of[from_bahnhof_id]
    j = index_of[to_bahnhof_id]
    if i >= j:
        raise ValueError("Ungültige Reihenfolge (from liegt nach to).")

    cost_prefix, time_prefix = _build_prefix_sums(abschnitte, speed_factor=speed_factor)

    min_cost = float(cost_prefix[j] - cost_prefix[i])
    duration_min = int((time_prefix[j] - time_prefix[i]) + 0.999)

    return {"min_cost": min_cost, "duration_min": duration_min}


def build_halteplan_segments_payload(
    strecke_id: int,
    bahnhof_ids_in_halteplan_order: List[int],
    speed_factor: float = DEFAULT_SPEED_FACTOR,
) -> List[dict]:
    """
        Rückgabe:
      [
        {
          "position": 1,
          "from_bahnhof_id": ...,
          "to_bahnhof_id": ...,
          "min_cost": ...,
          "duration_min": ...
        },
        ...
      ]
    """
    if len(bahnhof_ids_in_halteplan_order) < 2:
        return []

    segments: List[dict] = []
    for pos in range(1, len(bahnhof_ids_in_halteplan_order)):
        b_from = int(bahnhof_ids_in_halteplan_order[pos - 1])
        b_to = int(bahnhof_ids_in_halteplan_order[pos])

        stats = compute_stats_between(
            strecke_id=strecke_id,
            from_bahnhof_id=b_from,
            to_bahnhof_id=b_to,
            speed_factor=speed_factor,
        )

        segments.append(
            {
                "position": pos,
                "from_bahnhof_id": b_from,
                "to_bahnhof_id": b_to,
                "min_cost": float(stats["min_cost"]),
                "duration_min": int(stats["duration_min"]),
            }
        )

    return segments


def to_json_keyed_map(pair_map: Dict[Tuple[int, int], float | int]) -> Dict[str, float | int]:
    """
    Wandelt {(from,to): value} in {"from-to": value} um (JSON kompatibel).
    """
    return {f"{a}-{b}": v for (a, b), v in pair_map.items()}
