# UI and live verification report

Checked on 2026-10-04.

## Browser UI build

The local Cloud Run-equivalent build was exercised in the Codex in-app browser
at `http://127.0.0.1:8091/`:

| Flow | Result |
|---|---|
| New call greeting | Pass |
| Water-leak text submission | Pass; draft proposal and four-step trace rendered |
| Explicit confirmation | Pass; human-review handoff rendered |
| Gas/fume scenario | Pass; safety escalation rendered and proposal absent |
| Voice selector | Pass; Samantha selected in the browser voice catalog |
| Natural voice demo control | Pass; narration button and selected-voice status rendered |
| Observability counters | Pass; agent steps, blocks, handoffs, abstentions, failures, and redactions updated |

The voice is browser speech synthesis. It prefers a conversational installed
voice and does not upload or persist audio. Exact voice quality depends on the
browser/OS voice catalog.

## Automated and API verification

- `7/7` repository tests passed.
- The 2,048-case adversarial suite passed for the rules-first multi-agent
  control path.
- The real MCP stdio smoke call returned and verified signed evidence.

## Current Cloud Run status

The source was not redeployed during this check. GCP currently reports billing
disabled for project `project-2281c357-4539-4bc6-b96`, so Cloud Build/Artifact
Registry rejects a new deployment. The two known SunoSentry Cloud Run URLs
returned HTTP 404 during the live smoke check; therefore the live production
UI cannot honestly be marked passed until billing is restored and a new
revision is deployed.
