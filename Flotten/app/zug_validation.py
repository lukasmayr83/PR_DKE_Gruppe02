from app import db
from app.models import Triebwagen, Personenwagen

 # Prüft ob ein Triebwagen und Personenwagen ausgewählt wurden, die Spurweite gleich ist und die Zugkraft ausreicht
def validate_zug(request_form):

    tw_id = request_form.get("triebwagen_id")
    pw_ids = request_form.getlist("personenwagen_ids")

    if not tw_id:
        return False, None, None, "Bitte wählen Sie einen Triebwagen aus!"
    if not pw_ids:
        return False, None, None, "Bitte wählen Sie mindestens einen Personenwagen aus!"

    tw = db.session.get(Triebwagen, tw_id)
    pws = [db.session.get(Personenwagen, pid) for pid in pw_ids]

    # Prüfung Spurweite
    target = tw.spurweite
    for pw in pws:
        if pw.spurweite != target:
            return False, None, None, (
                f"Spurweite stimmt nicht überein! "
                f"Triebwagen: {target}, Personenwagen {pw.wagenid}: {pw.spurweite}"
            )

    # Prüfung Gesamtgewicht
    total_weight = sum(pw.maxgewicht for pw in pws)
    if tw.maxzugkraft < total_weight:
        return False, None, None, (
            f"Fehler: Zu schwer! Triebwagen schafft {tw.maxzugkraft}t - Personenwagen wiegen zusammen {total_weight}t."
        )

    return True, tw, pws, None