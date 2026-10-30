"""briefs collection (audit trail of generated catch-up / handover briefs)."""
from app.extensions import get_db


def insert(doc):
    return get_db().briefs.insert_one(doc).inserted_id
