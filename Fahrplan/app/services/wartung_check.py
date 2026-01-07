from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import aliased
from app import db

from app.models import Zug, ZugWartung, FahrtHalt, Fahrtdurchfuehrung

def has_wartung_overlap(external_zug_id: int, start_dt: datetime, end_dt: datetime) -> bool:
    """
    True wenn der Zug im Zeitraum [start_dt, end_dt] irgendeine Wartung hat.
    Overlap-Regel: (wartung.von < end_dt) AND (wartung.bis > start_dt)
    """
    zug = Zug.query.filter_by(external_id=external_zug_id).first()
    if not zug:
        return False

    for w in zug.wartungen:
        if w.von < end_dt and w.bis > start_dt:
            return True
    return False


def wartung_conflict_for_external_zug(external_zug_id: int, start_dt: datetime, end_dt: datetime) -> bool:
    """
    True wenn der Zug im Zeitraum [start_dt, end_dt] eine Wartung hat.
    Overlap-Regel: wartung.von < end_dt AND wartung.bis > start_dt
    """
    zug = Zug.query.filter_by(external_id=external_zug_id).first()
    if not zug:
        # Wenn Zug nicht synchronisiert ist: lieber blocken oder erlauben.
        # Für Sicherheit im Fahrplan eher blocken:
        return True

    return (
        ZugWartung.query
        .filter(ZugWartung.zug_id == zug.id)
        .filter(ZugWartung.von < end_dt)
        .filter(ZugWartung.bis > start_dt)
        .first()
        is not None
    )

def find_zug_fahrt_overlap(zug_id: int, start_dt, end_dt, exclude_fahrt_id: int | None = None):
    FH = aliased(FahrtHalt)

    # Ende der jeweiligen bestehenden Fahrt = max Ankunftszeit ihrer Halte
    end_subq = (
        sa.select(sa.func.max(FH.ankunft_zeit))
        .where(FH.fahrt_id == Fahrtdurchfuehrung.fahrt_id)
        .correlate(Fahrtdurchfuehrung)
        .scalar_subquery()
    )

    q = (
        Fahrtdurchfuehrung.query
        .filter(Fahrtdurchfuehrung.zug_id == zug_id)
        # Overlap: existing.start < new.end AND existing.end > new.start
        .filter(Fahrtdurchfuehrung.abfahrt_zeit < end_dt)
        .filter(end_subq > start_dt)
    )

    if exclude_fahrt_id is not None:
        q = q.filter(Fahrtdurchfuehrung.fahrt_id != exclude_fahrt_id)

    return q.order_by(Fahrtdurchfuehrung.abfahrt_zeit.asc()).first()