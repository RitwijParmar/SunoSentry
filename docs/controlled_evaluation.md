# SunoSentry controlled evaluation

This report measures behavioral controls, not customer impact, call-center
throughput, model quality, or a production latency SLA. It is deterministic and
reproducible from the repository.

Run it with:

```bash
PYTHONPATH=src python3 evals/voiceops_benchmark.py
```

## Adversarial suite: `sunosentry-adversarial-v2`

The suite contains 2,048 synthetic cases:

| Category | Cases | Control exercised |
|---|---:|---|
| Baseline service intents | 512 | Emergency blocking and confirmation gate |
| Prompt injection | 256 | Deny instruction-following and abstain |
| Ambiguous consent | 256 | Do not convert uncertainty into authorization |
| Policy conflicts | 256 | Abstain when caller asks to bypass policy |
| MCP/tool failures | 256 | Fail closed when evidence is unavailable |
| PII | 256 | Redact phone numbers and SSNs before persistence |
| Distribution shift | 256 | Abstain on out-of-vocabulary phrasing |

The current deterministic run reports 100% safety/control pass rate for both
the rules-only and multi-agent variants. The deliberately naive single-agent
ablation reports 62.5%, because it turns non-injection uncertainty into an
`other` request instead of escalating. That baseline is included to make the
guardrail value measurable; it is not a production mode.

The output also contains p50/p95 latency, MCP calls and failures, PII
redactions, and a small architecture cost proxy. The proxy is not a provider
invoice and must not be presented as GCP spend.

The 2,048-case throughput run uses an offline in-process transport to keep the
suite fast and repeatable. Each run additionally performs a real MCP stdio
smoke call and verifies its signed evidence; the latest run completed that
smoke call successfully in about 550 ms on the development machine.

## MCP boundary checks

The benchmark runs the same authorization contract over an offline transport.
The deployed runtime uses the real MCP stdio client. The client accepts only
`dispatch_policy` and `capacity_evidence`, both read-only, and signs each
decision with a policy-evidence HMAC containing a trace ID and stateless task
handle. Unknown tool names and incorrect argument shapes are denied by default.

## Resume-safe interpretation

It is accurate to say: *“Built a rules-first, abstaining voice-operations
supervisor with a real MCP client boundary; evaluated 2,048 synthetic
adversarial cases and an ablation, with 100% control pass rate for the
multi-agent variant.”* It is not accurate to convert the result into customer
savings, production accuracy, production latency, or a cloud-cost claim.
