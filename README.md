# SunoSentry (सुनो Sentry)

**A verifiable multi-agent voice-operations platform for field-service dispatch.**

**Live demo:** https://sunosentry-122722888597.us-east4.run.app

Most voice-agent demos optimize for a natural conversation. SunoSentry is built
for the operational moment after the conversation: whether a proposed service
action is safe, grounded in policy, explicitly confirmed, and simple for a
human dispatcher to audit.

![SunoSentry architecture](docs/architecture.svg)

## Why this is a stronger voice-AI project

Field service, property operations, utilities, and customer-support teams all
receive high-intent voice requests. The implementation focuses on the hard,
portable production concerns rather than a single scripted appointment flow:

- **Voice-first web experience:** browser microphone recognition and speech
  synthesis, with typed fallback for a reproducible demo.
- **Bounded multi-agent supervisor:** triage, policy-grounding, planning,
  consent, and safety specialists emit a visible per-call trace.
- **Verifiable action:** a recommendation can only move to a human-review
  queue after explicit confirmation. The app never silently books, bills, or
  dispatches.
- **Real safety control:** suspected gas/fume incidents block automation and
  immediately produce a human-escalation packet.
- **MCP boundary:** the included MCP server exposes named policy and capacity
  evidence only—no arbitrary SQL, arbitrary HTTP, or write tool is available
  to an agent.
- **VoiceOps observability:** latency, step completeness, PII redactions,
  safety blocks, verified handoffs, and full decision traces are visible.
- **Vertex AI, safely bounded:** Gemini can polish an already-approved spoken
  acknowledgement; it cannot classify risk, select policy, invoke an MCP write,
  or bypass the consent gate.

This is a simulated operational environment. It is not medical advice,
emergency response, telephony, technician dispatch, or a customer deployment.

## Architecture

```text
Browser microphone / text
          │
          ▼
 Cloud Run FastAPI ──► triage-agent ──► grounding-agent (MCP evidence)
          │                                      │
          │                         named policy + capacity evidence
          ▼                                      ▼
        planning-agent ──► consent-agent ──► human-review handoff
          │                    │
          └──── safety-agent blocks high-risk automation

Trace events → VoiceOps dashboard / future Cloud Trace & BigQuery sink
```

## GCP deployment

The container is designed for Cloud Run. The demo uses no committed secret and
does not need a telephony key. It can be deployed with:

```bash
gcloud run deploy sunosentry --source . --region us-east4 --allow-unauthenticated
```

The current public demo is deployed in `us-east4` with Cloud Run autoscaling to
zero. The active revision was independently checked for health and for the
gas/fume safety block before publication.

See [deployment guidance](docs/deployment.md) for the production path:
Vertex AI, Secret Manager, Cloud Trace, Pub/Sub, BigQuery, and a telephony
adapter with explicit consent and retention controls.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn sunosentry.api:app --reload --port 8080
```

Then open `http://localhost:8080` and try the three scenario buttons.

## Tests and evaluation

```bash
python3 -m pytest -q
python3 -m sunosentry.mcp_server
```

The unit suite verifies the two non-negotiable properties: emergency safety
blocks do not create a dispatch, and non-emergency proposals require spoken
confirmation before a human-review handoff.

## Resume-safe framing

> Built SunoSentry, a Cloud Run-deployed, multi-agent voice-operations demo
> for field-service intake; implemented policy-grounded MCP evidence tools,
> consent-gated dispatch proposals, PII redaction, and per-call safety/latency
> traces. All operational data and integrations are simulated.
