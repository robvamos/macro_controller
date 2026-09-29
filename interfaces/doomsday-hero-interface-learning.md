# doomsday-hero-interface-learning

- Producer: ddgameass
- Status: experimental
- Interface version: 0.2.0
- Default mode: supervised, evidence-only

## Purpose

This interface learns how the Doomsday hero UI is traversed without assigning
meaning from coordinates alone. It records click crops, stable full-window
frames and a crash-safe event journal, then binds observations to an
evidence-gated semantic workflow.

## Declared workflow

The versioned definition is
[hero_inspection_workflow.json](../data/doomsday/knowledge/hero_inspection_workflow.json).
It models entry into the hero section, selector, left roster list, sorting,
hero selection, profile attributes, statistics, abilities and talents.

All nodes start with maturity `expected`. A transition becomes automatable only
after it reaches `validated`, has user confirmation, and contains valid
`before_frame` and `after_frame` evidence. The current workflow therefore does
not authorize playback.

## Learning session

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_learning_mode.ps1 `
  -Mode general -Minutes 15 -Scenario hero-inspection
```

Stop cleanly with `Ctrl+Alt+S`.

Each session writes under `.tools/learning_sessions/<session>/`:

- `session.json`: objective, declared workflow and status;
- `events.jsonl`: one durable record per click;
- `frames.jsonl`: full-frame hashes, quality and lineage;
- PNG frames at click time and after stabilization (new sessions).
- `network_correlation_summary.json`: per-click metadata-only traffic shape,
  latency candidate and repeatable fingerprint.

Learning now enables per-PID network observation by default. The session
manifest records whether the observer was started, attached or unavailable.
Visual learning continues fail-soft when the observer cannot start, but the
evidence coverage is explicitly partial. Use `-DisableNetworkObservation` only
for an intentional visual-only session.

## Interrupted-session recovery

`recover_learning_session()` opens the workstation-local macro database using SQLite
`mode=ro&immutable=1`. It never creates or updates a Macro row. It validates
sequence continuity and predecessor links, then writes a supplemental JSON and
click crops under the selected profile's local `runtime/doomsday/recovered_learning_sessions/`
directory. The shared exporter publishes only a sanitized click sequence; raw
click crops remain local.

## OCR anchors

`TesseractCliEngine` invokes Tesseract through PNG stdin and TSV stdout. The
default language is `ita+eng`. The current capture profile contains only the
validated home-screen label `Eroe`; it is an OCR anchor, not a click target.

## Safety boundaries

- no labels from screen position alone;
- no autonomous clicks in learning mode;
- no direct roster mutation from OCR;
- no network/API meaning inferred from timing alone;
- network correlations require repeated validated UI transitions and cannot
  bypass authentication or game protections.
