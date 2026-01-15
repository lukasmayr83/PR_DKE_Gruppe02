from __future__ import annotations

from datetime import datetime, date, time, timedelta
import random

from app import db
from app.models import Zug, Haltepunkt, HalteplanSegment
from app.services.wartung_check import has_wartung_overlap, find_zug_fahrt_overlap

def generate_datetimes_interval(
    start_date: date,
    end_date: date,
    first_departure_time: time,
    interval_minutes: int,
    trips_per_day: int,
    weekdays: set[int],  # 0=Mo..6=So
) -> list[datetime]:
    if interval_minutes <= 0:
        raise ValueError("Intervall muss > 0 sein.")
    if trips_per_day <= 0:
        raise ValueError("Anzahl pro Tag muss > 0 sein.")
    if end_date < start_date:
        raise ValueError("Enddatum muss >= Startdatum sein.")
    if not weekdays:
        raise ValueError("Bitte mindestens einen Wochentag wählen.")

    out: list[datetime] = []
    d = start_date
    while d <= end_date:
        if d.weekday() in weekdays:
            base = datetime.combine(d, first_departure_time)
            for k in range(trips_per_day):
                out.append(base + timedelta(minutes=k * interval_minutes))
        d += timedelta(days=1)

    return out


def compute_fahrt_window(halteplan_id: int, start_dt: datetime) -> tuple[datetime, datetime]:
    hp_stops = (
        db.session.query(Haltepunkt)
        .filter(Haltepunkt.halteplan_id == halteplan_id)
        .order_by(Haltepunkt.position)
        .all()
    )
    hp_segs = (
        db.session.query(HalteplanSegment)
        .filter(HalteplanSegment.halteplan_id == halteplan_id)
        .order_by(HalteplanSegment.position)
        .all()
    )

    if len(hp_stops) < 2:
        raise ValueError("Halteplan benötigt mindestens 2 Haltepunkte.")
    if len(hp_segs) != (len(hp_stops) - 1):
        raise ValueError("Halteplan-Segmente passen nicht zur Anzahl der Haltepunkte.")

    cur = start_dt
    for i, seg in enumerate(hp_segs):
        cur += timedelta(minutes=int(seg.duration_min or 0))

        # Haltezeit am Zielhalt (außer letzter)
        is_last_stop = (i + 1) == (len(hp_stops) - 1)
        if not is_last_stop:
            cur += timedelta(minutes=int(hp_stops[i + 1].halte_dauer_min or 0))

    return start_dt, cur


def is_zug_available(zug: Zug, start_dt: datetime, end_dt: datetime) -> tuple[bool, str | None]:
    if has_wartung_overlap(zug.external_id, start_dt, end_dt):
        return False, "Wartung"

    with db.session.no_autoflush:
        conflict = find_zug_fahrt_overlap(
            zug_id=zug.id,
            start_dt=start_dt,
            end_dt=end_dt,
            exclude_fahrt_id=None,
        )
    if conflict:
        return False, f"Overlap mit Fahrt #{conflict.fahrt_id}"
    return True, None



def overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end  # klassischer interval overlap

def auto_assign_trains(
    windows: list[tuple[datetime, datetime]],   # [(start,end), ...] in gleicher Reihenfolge wie geplante Fahrten
    zuege: list[Zug],
) -> list[int | None]:
    assigned: list[int | None] = []
    local_alloc: dict[int, list[tuple[datetime, datetime]]] = {z.id: [] for z in zuege}

    for start_dt, end_dt in windows:
        chosen = None

        for z in zuege:
            ok, _reason = is_zug_available(z, start_dt, end_dt)
            if not ok:
                continue

            # lokaler Preview-Konflikt mit bereits zugewiesenen
            local_conflict = any(overlaps(start_dt, end_dt, s, e) for s, e in local_alloc[z.id])
            if local_conflict:
                continue

            chosen = z.id
            local_alloc[z.id].append((start_dt, end_dt))
            break

        assigned.append(chosen)

    return assigned



def auto_assign_crew(
    mitarbeiter_ids: list[int],
    crew_size: int,
    num_fahrten: int,
    seed: int | None = None,
) -> list[list[int]]:
    if crew_size <= 0:
        return [[] for _ in range(num_fahrten)]
    if crew_size > len(mitarbeiter_ids):
        raise ValueError("Crew-Größe größer als verfügbare Mitarbeiter.")

    rng = random.Random(seed)
    counts = {mid: 0 for mid in mitarbeiter_ids}
    result: list[list[int]] = []

    for _ in range(num_fahrten):
        # sort by (count, random) → fair
        mids = sorted(mitarbeiter_ids, key=lambda m: (counts[m], rng.random()))
        pick = mids[:crew_size]
        for m in pick:
            counts[m] += 1
        result.append(pick)

    return result
