from flask import Blueprint, request

from app.api._helpers import body, ok
from app.schemas.kb import KBCreate
from app.services import kb_service

bp = Blueprint("kb_api", __name__, url_prefix="/api/kb")


@bp.get("")
def list_docs():
    return ok(kb_service.list_docs(request.args.get("q")))


@bp.post("")
def add_doc():
    return ok(kb_service.add_doc(body(KBCreate)), 201)


@bp.get("/<doc_id>")
def get_doc(doc_id):
    return ok(kb_service.get_doc(doc_id))
