"""End-to-end API tests for the CS Electric support system."""
from __future__ import annotations


def _create(client, **overrides):
    payload = {
        "customer_name": "Ada Lovelace",
        "customer_email": "ada@example.com",
        "subject": "General enquiry",
        "body": "I have a question about my account.",
    }
    payload.update(overrides)
    return client.post("/api/tickets", json=payload)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["database"] is True


def test_create_ticket_triages_and_replies(client):
    resp = _create(
        client,
        subject="Power outage on my street",
        body="There is no power at all since this morning, total blackout.",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["category"] == "outage"
    assert data["priority"] == "high"
    assert data["status"] == "open"
    authors = [m["author"] for m in data["messages"]]
    assert authors == ["customer", "agent"]
    assert "CS Electric Support Agent" in data["messages"][1]["body"]


def test_safety_ticket_is_urgent(client):
    resp = _create(
        client,
        subject="Sparks from meter box",
        body="I can see sparks and smell burning near the fuse box.",
    )
    data = resp.get_json()
    assert data["category"] == "safety"
    assert data["priority"] == "urgent"


def test_missing_fields_rejected(client):
    resp = client.post("/api/tickets", json={"customer_name": "Nobody"})
    assert resp.status_code == 400
    assert "Missing required fields" in resp.get_json()["error"]


def test_list_and_filter(client):
    _create(client, subject="Billing issue", body="I was overcharged on my invoice.")
    _create(client, subject="Outage", body="No electricity, blackout in the whole block.")

    resp = client.get("/api/tickets")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 2

    resp = client.get("/api/tickets?category=billing")
    body = resp.get_json()
    assert body["count"] == 1
    assert body["tickets"][0]["category"] == "billing"


def test_get_ticket_and_add_message(client):
    created = _create(client).get_json()
    ticket_id = created["id"]

    resp = client.get(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 200

    resp = client.post(
        f"/api/tickets/{ticket_id}/messages", json={"body": "Any update please?"}
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert len(data["messages"]) == 4  # customer, agent, customer, agent


def test_update_status(client):
    ticket_id = _create(client).get_json()["id"]
    resp = client.patch(f"/api/tickets/{ticket_id}", json={"status": "resolved"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "resolved"

    resp = client.patch(f"/api/tickets/{ticket_id}", json={"status": "bogus"})
    assert resp.status_code == 400


def test_not_found(client):
    assert client.get("/api/tickets/99999").status_code == 404
