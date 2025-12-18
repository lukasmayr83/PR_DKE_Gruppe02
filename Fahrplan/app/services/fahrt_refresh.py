from __future__ import annotations

from datetime import timedelta
import sqlalchemy as sa
import sqlalchemy.orm as so

from app import db
from app.models import (
    Fahrtdurchfuehrung,
    Halteplan,
    Haltepunkt,
    HalteplanSegment,
    FahrtHalt,
    FahrtSegment,
)

def refresh_fahrt_snapshot(fahrt_id: int) -> dict:
    """
    Baut FahrtHalt + FahrtSegment für eine Fahrtdurchführung neu auf.
    Quelle: Halteplan.haltepunkte + Halteplan.segmente + fahrt.abfahrt_zeit + fahrt.price_factor
    Speichert bei FahrtSegment nur final_price (+ duration_min), wie ausgemacht.
    """

    # 1) Daten laden
    fahrt = db.session.scalar(
        sa.select(Fahrtdurchfuehrung)
        .where(Fahrtdurchfuehrung.fahrt_id == fahrt_id)
        .options(
            so.joinedload(Fahrtdurchfuehrung.halteplan)
            .joinedload(Halteplan.haltepunkte),
            so.joinedload(Fahrtdurchfuehrung.halteplan)
            .joinedload(Halteplan.segmente),
        )
    )
    if fahrt is None:
        raise ValueError(f"Fahrt {fahrt_id} nicht gefunden")

    halteplan = fahrt.halteplan
    haltepunkte = sorted(halteplan.haltepunkte, key=lambda x: x.position)
    segmente = sorted(halteplan.segmente, key=lambda x: x.position)

    if len(haltepunkte) < 2:
        raise ValueError("Halteplan braucht mindestens 2 Haltepunkte")
    if len(segmente) != len(haltepunkte) - 1:
        raise ValueError("HalteplanSegment-Anzahl muss (Haltepunkte - 1) sein")

    # 2) Alte Snapshots löschen (einfach & robust)
    db.session.execute(sa.delete(FahrtSegment).where(FahrtSegment.fahrt_id == fahrt_id))
    db.session.execute(sa.delete(FahrtHalt).where(FahrtHalt.fahrt_id == fahrt_id))
    db.session.flush()

    # 3) FahrtHalt neu erzeugen
    # Startzeit ist Abfahrt am ersten Halt
    t = fahrt.abfahrt_zeit

    fahrt_halt_ids: list[int] = []

    # erster Halt: Abfahrtzeit = fahrt.abfahrt_zeit, Ankunft optional = gleich
    first = haltepunkte[0]
    fh0 = FahrtHalt(
        fahrt_id=fahrt_id,
        bahnhof_id=first.bahnhof_id,
        position=1,
        ankunft_zeit=t,   # optional
        abfahrt_zeit=t,
    )
    db.session.add(fh0)
    db.session.flush()
    fahrt_halt_ids.append(fh0.id)

    # weitere Halte: Zeit wird aus Segment-Dauern aufaddiert
    for i in range(1, len(haltepunkte)):
        # Segment i-1 führt von Halt i-1 zu Halt i
        seg = segmente[i - 1]
        t = t + timedelta(minutes=int(seg.duration_min))

        hp = haltepunkte[i]
        fh = FahrtHalt(
            fahrt_id=fahrt_id,
            bahnhof_id=hp.bahnhof_id,
            position=i + 1,
            ankunft_zeit=t,
            abfahrt_zeit=t,  # falls du später Aufenthaltszeit willst, kannst du das splitten
        )
        db.session.add(fh)
        db.session.flush()
        fahrt_halt_ids.append(fh.id)

    # 4) FahrtSegment neu erzeugen (nur final_price speichern)
    links = 0
    for i, hpseg in enumerate(segmente, start=1):
        # Validierung kostendeckend: base_price muss >= min_cost
        base_price = float(hpseg.base_price)
        min_cost = float(hpseg.min_cost)
        if base_price < min_cost:
            raise ValueError(
                f"HalteplanSegment pos={i}: base_price ({base_price}) < min_cost ({min_cost})"
            )

        final_price = base_price * float(fahrt.price_factor)

        # zur Sicherheit nochmal kostendeckend (nach Faktor eigentlich eh >= min_cost wenn base>=min)
        if final_price < min_cost:
            final_price = min_cost

        fs = FahrtSegment(
            fahrt_id=fahrt_id,
            von_halt_id=fahrt_halt_ids[i - 1],
            nach_halt_id=fahrt_halt_ids[i],
            position=i,
            final_price=final_price,
            duration_min=int(hpseg.duration_min),
        )
        db.session.add(fs)
        links += 1

    db.session.commit()
    return {
        "fahrt_id": fahrt_id,
        "halte": len(fahrt_halt_ids),
        "segmente": links,
    }
