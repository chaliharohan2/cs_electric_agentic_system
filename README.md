# CS Electric Client Support Agent

A fully agentic framework for a client support system for the company CS Electric.

It exposes a RESTful Flask API backed by PostgreSQL (via SQLAlchemy). When a
customer opens a support ticket, the built-in **support agent** automatically
triages it (category + priority) and drafts a reply, mirroring how a human
first-line support agent would respond.

## Stack

- Python 3.11
- Flask (RESTful API)
- SQLAlchemy + Flask-SQLAlchemy (ORM)
- PostgreSQL

## Project layout

```
app/
  __init__.py     # application factory
  extensions.py   # SQLAlchemy instance
  models.py       # Ticket, TicketMessage ORM models
  agent.py        # SupportAgent: triage + reply generation
  routes.py       # RESTful API blueprint
config.py         # environment-driven configuration
wsgi.py           # WSGI entry point (gunicorn wsgi:app)
scripts/
  dev-install.sh  # create venv + install deps (idempotent)
  dev-start.sh    # start PostgreSQL, ensure DB + schema
  serve.sh        # run the API server
  init_db.py      # create tables
tests/            # pytest API tests
```

## Local development

Prerequisites: Python 3.11 and PostgreSQL 16 installed and available.

```bash
# 1. Install dependencies (creates .venv)
./scripts/dev-install.sh

# 2. Bring up PostgreSQL, create the role/databases, and the schema
./scripts/dev-start.sh

# 3. Run the API
./scripts/serve.sh
```

The API listens on `http://localhost:5000`.

Configuration is read from environment variables (see `.env.example`). The
default database URL is
`postgresql+psycopg2://cselectric:cselectric@127.0.0.1:5432/cs_electric`.

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Service + database health check |
| POST | `/api/tickets` | Create a ticket (agent triages + replies) |
| GET | `/api/tickets` | List tickets (`?status=`, `?category=` filters) |
| GET | `/api/tickets/<id>` | Fetch a ticket with its messages |
| POST | `/api/tickets/<id>/messages` | Add a customer message (agent follows up) |
| PATCH | `/api/tickets/<id>` | Update status (`open`/`pending`/`resolved`/`closed`) |

### Example

```bash
curl -X POST http://localhost:5000/api/tickets \
  -H 'Content-Type: application/json' \
  -d '{
        "customer_name": "Grace Hopper",
        "customer_email": "grace@example.com",
        "subject": "Power outage on Elm Street",
        "body": "There is no power at all since this morning, total blackout."
      }'
```

The agent classifies this as an `outage` at `high` priority and returns an
auto-drafted reply as the first agent message on the ticket.

## Tests

```bash
./scripts/dev-start.sh        # ensures the test database exists
.venv/bin/python -m pytest -q
```
