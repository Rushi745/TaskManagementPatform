"""Wipe all HandOff collections and re-seed the demo data (use before a demo).
Run:  python -m scripts.reset_db   (this DELETES everything in the configured database)"""
from app import create_app
from app.extensions import get_db
from scripts.seed import run_seed

if __name__ == "__main__":
    app = create_app()  # seeds automatically if empty
    db = get_db()
    for name in ("people", "meetings", "action_items", "kb_docs", "briefs"):
        db[name].delete_many({})
    from app.services import retrieval

    retrieval.invalidate()
    ran = run_seed()
    from app.auth import ensure_credentials

    ensure_credentials()
    print("Reseeded." if ran else "Nothing to seed.")
