# CS Electric Client Support Agent

CLI-only LangGraph product-support framework backed by synthetic WiNbreak2 and
DP-Contactor fixture data.

## Run

Python 3.11 or newer is required. The repository uses a local `.venv` when the
project-specific venv is unavailable.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m cs_agent.run
# or
.venv/bin/python -m cs_agent.run --question "Compare suitable MCCB families"
```

Set the OpenAI-compatible endpoint/key values in `.env`. `CS_MODELS` can target
all nodes (`all:qwen_27b`) or selected nodes
(`agent:qwen_a3b,composer:qwen_27b`). `CS_BACKEND` defaults to `fixtures`;
`postgres` intentionally raises `SCHEMA_PENDING` until the production schema is
defined.
