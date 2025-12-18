from __future__ import annotations

from datetime import datetime, timedelta
import sqlalchemy as sa
from app import db
from app.models import (
    Halteplan, Haltepunkt, HalteplanSegment,
    Fahrtdurchfuehrung, FahrtHalt, FahrtSegment
)

def rebuild_fahrt_halte_und_segmente(fahrt: Fahrtdurchfuehrung) -> None:
    """
    Baut FahrtHalt + FahrtSegment aus dem zugehörigen Halteplan neu auf.
    - Zeiten: abfahrt_zeit der Fahrt + Segmentdauer + Haltedauer (Haltepunkt.halte_dauer_min)
    - Preise: final_price = HalteplanSegment.base_price * fahrt.price_factor
    """

    hp: Halteplan = fahrt.halteplan

    # Haltepunkte und Segmente in Reihenfolge
    stops = (
        db.session.query(Haltepunkt)
        .filter(Haltepunkt.halteplan_id == hp.halteplan_id)
        .order_by(Haltepunkt.position)
        .all()
    )
    segs = (
        db.session.query(HalteplanSegment)
        .filter(HalteplanSegment.halteplan_id == hp.halteplan_id)
        .order_by(HalteplanSegment.position)
        .all()
    )

    if len(stops) < 2:
        raise ValueError("Halteplan hat zu wenige Haltepunkte.")
    if len(segs) != len(stops) - 1:
        raise ValueError("Halteplan-Segmente passen nicht zur Anzahl der Haltepunkte.")

    # Alte Datensätze löschen (damit keine Inkonsistenzen bleiben)
    db.session.query(FahrtSegment).filter(FahrtSegment.fahrt_id == fahrt.fahrt_id).delete(synchronize_session=False)
    db.session.query(FahrtHalt).filter(FahrtHalt.fahrt_id == fahrt.fahrt_id).delete(synchronize_session=False)
    db.session.flush()

    # FahrtHalt erzeugen + Zeiten berechnen
    fh_list: list[FahrtHalt] = []

    t = fahrt.abfahrt_zeit  # Startzeit

    # 1) erster Halt: ankunft = abfahrt = Startzeit
    first = FahrtHalt(
        fahrt_id=fahrt.fahrt_id,
        bahnhof_id=stops[0].bahnhof_id,
        position=1,
        ankunft_zeit=t,
        abfahrt_zeit=t,
    )
    db.session.add(first)
    db.session.flush()
    fh_list.append(first)

    # 2) Rest
    for i in range(1, len(stops)):
        # Segment davor
        seg_duration = int(segs[i - 1].duration_min or 0)

        # ankunft am nächsten Bahnhof
        t = t + timedelta(minutes=seg_duration)
        ankunft = t

        is_last = (i == len(stops) - 1)

        if is_last:
            abfahrt = None
        else:
            # Haltedauer am Bahnhof i (Zwischenhalt) kommt aus Haltepunkt
            dwell = int(stops[i].halte_dauer_min or 0)
            abfahrt = ankunft + timedelta(minutes=dwell)
            t = abfahrt  # nächste Segmentrechnung ab Abfahrt

        fh = FahrtHalt(
            fahrt_id=fahrt.fahrt_id,
            bahnhof_id=stops[i].bahnhof_id,
            position=i + 1,
            ankunft_zeit=ankunft,
            abfahrt_zeit=abfahrt,
        )
        db.session.add(fh)
        db.session.flush()
        fh_list.append(fh)

    # FahrtSegment erzeugen (zwischen FahrtHalt-IDs)
    for pos in range(1, len(fh_list)):
        hpseg = segs[pos - 1]
        base_price = float(hpseg.base_price or 0.0)
        final_price = base_price * float(fahrt.price_factor or 1.0)

        db.session.add(
            FahrtSegment(
                fahrt_id=fahrt.fahrt_id,
                von_halt_id=fh_list[pos - 1].id,
                nach_halt_id=fh_list[pos].id,
                position=pos,
                duration_min=int(hpseg.duration_min or 0),
                final_price=float(final_price),
            )
        )
