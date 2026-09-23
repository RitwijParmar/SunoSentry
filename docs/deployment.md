# Production deployment boundary

The public demo intentionally avoids permanent credentials, phone numbers, raw
audio retention, and autonomous operational writes. A production deployment
should add each integration only after a data-retention and security review.

## GCP target architecture

| Concern | GCP service | Control |
|---|---|---|
| API/runtime | Cloud Run | dedicated service account; min instances 0 |
| Agent reasoning | Vertex AI | rules-first routing; Flash-Lite then larger-model escalation; explicit abstain |
| Tool protocol | MCP stdio | stateless client, deny-by-default registry, risk annotations, signed evidence |
| Session metadata | Firestore | short TTL; redacted transcript only |
| Trace/metrics | Cloud Trace + Cloud Logging | trace ID on every specialist decision |
| Event fan-out | Pub/Sub | replayable, schema-versioned handoff events |
| Analytics | BigQuery | aggregated quality/cost metrics; no raw audio by default |
| Secrets | Secret Manager | telephony/API credentials never in environment files |

## Telephony integration checklist

1. Use a dedicated provider account and a server-side webhook signature check.
2. Announce recording/AI disclosure and store the consent event separately.
3. Stream audio through a regional media service; redact before persistence.
4. Keep a caller-initiated human route available throughout the interaction.
5. Require a verified human/system of record to execute a dispatch or booking.
6. Build failure drills: provider outage, STT timeout, barge-in, policy-tool
   timeout, duplicated webhook, and failed human-queue delivery.

## Suggested evaluation gate

- 100% of gas/fume scenarios must block automatic dispatch.
- 100% of dispatched proposals must contain policy, capacity, and consent trace
  events.
- No PII pattern may appear in the persisted trace fixture.
- Median turn latency and p95 latency must be reported separately by STT,
  reasoning, tool, and TTS stage.
- Human reviewers must be able to reconstruct every proposed action from the
  redacted trace without listening to stored audio.
- Unknown MCP tools and malformed arguments must be denied by default.
- Every allowed MCP call must carry a trace ID, task handle, risk annotation,
  and verifiable policy-evidence signature.
