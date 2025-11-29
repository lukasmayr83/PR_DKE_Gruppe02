from app import db
from app.models import Mitarbeiter, User
import sqlalchemy as sa

def validate_unique_svnr(svnr, current_svnr=None):
    # Wenn beim Bearbeiten die SVNR nicht geändert wurde → OK
    if current_svnr is not None and svnr == current_svnr:
        return True, None

    exists = db.session.scalar(
        sa.select(Mitarbeiter).where(Mitarbeiter.svnr == svnr)
    )

    if exists:
        return False, "Diese Sozialversicherungsnummer ist bereits vergeben!"

    return True, None


def validate_unique_username(username, current_user_id=None):
    user = db.session.scalar(
        sa.select(User).where(User.username == username)
    )

    if user and user.id != current_user_id:
        return False, "Dieser Benutzername ist bereits vergeben!"

    return True, None