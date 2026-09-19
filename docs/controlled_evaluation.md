# SunoSentry controlled evaluation

This report measures **behavioral controls**, not customer impact, call-center
throughput, model accuracy, or production latency. It is deliberately small,
deterministic, and runnable from the repository.

Run it with:

```bash
PYTHONPATH=src python3 evals/voiceops_benchmark.py
```

## Result: `voiceops-control-v1`

| Control | Result | What it proves |
|---|---:|---|
| Total scripted voice-operation cases | 36 / 36 passed | Reproducible baseline across emergency, normal, and confirmed interactions |
| Emergency safety blocks | 12 / 12 | Gas/fume requests created no dispatch proposal and produced a blocked trace |
| Consent gates | 24 / 24 | Normal requests either stayed draft without confirmation or became human-review ready with confirmation |
| Required trace coverage | 36 / 36 | Every case emitted the expected specialist decision trail |
| Autonomous dispatches | 0 | The runtime never performs a booking or dispatch; final action remains human-reviewed |

The benchmark uses simulated capacity and policy evidence. It should be rerun
when triage rules, policy tools, or consent behavior changes.

## Resume-safe interpretation

It is accurate to say *“validated 36 scripted safety and consent scenarios with
100% control coverage”*. It is **not** accurate to convert this result into
customer savings, real-world accuracy, production volume, or a latency SLA.
