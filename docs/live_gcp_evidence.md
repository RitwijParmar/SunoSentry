# Live GCP evidence

This document records the non-sensitive integration checks performed on the
public Cloud Run deployment. It is not a customer-performance claim.

## Deployed services

- **Cloud Run:** `sunosentry-benchmark` in `us-central1`, autoscaled to zero.
- **Firestore Native:** redacted session state only; raw audio is never stored.
- **Pub/Sub:** `sunosentry-handoff-events` receives human-review metadata only.
- **Vertex AI:** structured triage and wording layers are enabled with a
  deterministic policy-rule fallback when the model call fails or returns an
  invalid structured value.

## Integration check

On 2026-09-19, a confirmed heating-service request was submitted to the live
API. The response verified:

| Signal | Observed result |
|---|---|
| Session persistence | `firestore` |
| Human-review event | Pub/Sub message ID returned |
| Action status | `ready_for_handoff` |
| Triage safety behavior | Deterministic `rules_fallback` selected `no_heat` when the structured model result was unavailable |

The event payload excludes raw audio and caller transcript. It contains only a
redacted proposal, trace identifier, and redaction count.
