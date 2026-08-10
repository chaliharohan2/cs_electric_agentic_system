"""RESTful API routes for the CS Electric support system."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select, text

from .agent import agent
from .extensions import db
from .models import Ticket, TicketMessage

api = Blueprint("api", __name__)

_VALID_STATUSES = {"open", "pending", "resolved", "closed"}


def _error(message: str, status: int):
    return jsonify({"error": message}), status


@api.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # pragma: no cover - defensive
        db_ok = False
    status = 200 if db_ok else 503
    return jsonify({"status": "ok" if db_ok else "degraded", "database": db_ok}), status


@api.post("/api/tickets")
def create_ticket():
    payload = request.get_json(silent=True) or {}
    required = ["customer_name", "customer_email", "subject", "body"]
    missing = [f for f in required if not str(payload.get(f, "")).strip()]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}", 400)

    triage, reply = agent.handle(
        payload["customer_name"], payload["subject"], payload["body"]
    )

    ticket = Ticket(
        customer_name=payload["customer_name"].strip(),
        customer_email=payload["customer_email"].strip(),
        subject=payload["subject"].strip(),
        body=payload["body"].strip(),
        category=triage.category,
        priority=triage.priority,
        status="open",
    )
    ticket.messages.append(TicketMessage(author="customer", body=payload["body"].strip()))
    ticket.messages.append(TicketMessage(author="agent", body=reply))

    db.session.add(ticket)
    db.session.commit()
    return jsonify(ticket.to_dict()), 201


@api.get("/api/tickets")
def list_tickets():
    stmt = select(Ticket)
    status = request.args.get("status")
    category = request.args.get("category")
    if status:
        stmt = stmt.where(Ticket.status == status)
    if category:
        stmt = stmt.where(Ticket.category == category)
    stmt = stmt.order_by(Ticket.created_at.desc())

    tickets = db.session.scalars(stmt).all()
    return jsonify(
        {
            "count": len(tickets),
            "tickets": [t.to_dict(include_messages=False) for t in tickets],
        }
    )


@api.get("/api/tickets/<int:ticket_id>")
def get_ticket(ticket_id: int):
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None:
        return _error("Ticket not found", 404)
    return jsonify(ticket.to_dict())


@api.post("/api/tickets/<int:ticket_id>/messages")
def add_message(ticket_id: int):
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None:
        return _error("Ticket not found", 404)

    payload = request.get_json(silent=True) or {}
    body = str(payload.get("body", "")).strip()
    if not body:
        return _error("Missing required field: body", 400)

    ticket.messages.append(TicketMessage(author="customer", body=body))
    reply = agent.follow_up(ticket.customer_name, ticket.category, body)
    ticket.messages.append(TicketMessage(author="agent", body=reply))
    if ticket.status in ("resolved", "closed"):
        ticket.status = "open"

    db.session.commit()
    return jsonify(ticket.to_dict()), 201


@api.patch("/api/tickets/<int:ticket_id>")
def update_ticket(ticket_id: int):
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None:
        return _error("Ticket not found", 404)

    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status is not None:
        if status not in _VALID_STATUSES:
            return _error(
                f"Invalid status. Must be one of: {', '.join(sorted(_VALID_STATUSES))}", 400
            )
        ticket.status = status

    db.session.commit()
    return jsonify(ticket.to_dict())
