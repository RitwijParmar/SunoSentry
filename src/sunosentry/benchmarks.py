"""Published, reproducible controlled-evaluation baseline.

These are behavioral-control checks, not customer outcomes or production-call
metrics. Update them only by running evals/voiceops_benchmark.py.
"""

CONTROLLED_BENCHMARK = {
    "suite": "voiceops-control-v1",
    "cases": 36,
    "emergency_cases": 12,
    "normal_cases": 24,
    "safety_blocks": "12 / 12",
    "consent_gates": "24 / 24",
    "trace_complete": "36 / 36",
    "autonomous_dispatches": 0,
    "disclaimer": "Controlled deterministic evaluation; not a customer-impact or production-scale claim.",
}
