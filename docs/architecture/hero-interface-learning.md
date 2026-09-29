# Hero interface learning architecture

The hero-learning path is split into four layers:

1. **Declared semantics** describe what the user says exists in the UI.
2. **Raw evidence** preserves clicks, crops, frames, hashes and quality.
3. **Validated bindings** connect evidence to workflow transitions.
4. **Roster ingestion** turns confirmed OCR fields into a reviewed change set.

This separation prevents a coordinate, nearby text or temporally adjacent
network request from becoming proof of meaning.

## Evidence lifecycle

`expected -> observed_unlabeled -> labeled -> validated`

Automation remains disabled until the last state. A validated transition needs
human confirmation and valid frames before and after the action. Invalid or
black DirectX captures are retained for diagnostics but cannot validate it.

## Current acquisition path

- The foreground Windows client is observed through Win32 capture.
- The learner runs elevated because the game may reject lower-integrity input
  observation.
- Every click is journaled immediately.
- Spatial popup-dismissal inference is disabled for hero learning.
- A delayed full frame captures the rendered post-click state.

The first July demonstration was interrupted after 22 clicks. Its raw recovered
session and click crops are kept in the workstation-local runtime; the sanitized
click sequence is published in the shared learning-session catalog. Four legacy
events retain a `shared_spatial_placeholder` gap because their click-specific
crops were not retained in the canonical catalog.

The follow-up supervised session `20260714_173207` completed with 23 distinct
clicks and 23 valid full frames. Conservative OCR-anchor
classification found 8 hero profiles, 4 talent views, 4 ability views, 4
equipment views, 2 equipment-item details and 1 home view, with no unknown
screen. These results are stored in
[20260714_173207.json](../../data/doomsday/knowledge/hero_learning_observations/20260714_173207.json).
They label screen states, not the action performed by each click.

## Roster transaction boundary

Images enter `LiveRosterWorkflow` as immutable SHA-256 artifacts. Candidates are
previewed; conflicts remain visible. Every item is accepted, rejected or
overridden, then the set is confirmed before an optimistic-lock commit. The
commit writes revision, history, audit and evidence outbox in one transaction.

## Dual-evidence correlation

Learning now binds the visual journal to a metadata-only per-PID network
session. Every click preserves the network event range around click-time and
post-stabilization frames. A final summary extracts directional sizes, ports,
latency candidates and stable fingerprints. Correlation still requires repeated
observations and consistent visual transitions; protocol work cannot bypass
authentication, anti-cheat or access controls.
