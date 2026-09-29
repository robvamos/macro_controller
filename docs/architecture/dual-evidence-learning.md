# Dual-evidence Learning

Supervised Learning observes the user's own game client on two synchronized
evidence planes:

1. **Visual plane** — click, crop, full frame, OCR, detected UI node and
   before/after state.
2. **Network plane** — process-scoped TCP/UDP timestamp, direction, port,
   ordinal and byte count with TLS left encrypted.

The shared UTC timeline binds both planes without treating either one as
complete game meaning.

## Session lifecycle

`start_learning_mode.ps1` enables network observation by default. After the
game window and PID exist, the learner:

1. attaches a compatible active observer or starts a bounded one;
2. stores the network binding in the crash-safe learning manifest;
3. writes a network marker at every observed click;
4. captures event indices before the click and after visual stabilization;
5. stores those indices with the click and frame evidence;
6. stops only an observer it owns;
7. materializes `network_correlation_summary.json`.

If the observer is unavailable, visual learning continues and records the
reason as partial coverage. A session can intentionally disable observation
with `-DisableNetworkObservation`.

## Progressive semantic reconstruction

The initial domain registry covers:

- battle reports and ordered battle events;
- resources and inventory;
- armaments and equipment;
- gathering and map missions;
- workshop and production;
- research center;
- missions, objectives and rewards.

Additional domains can be declared with `-Domain <name>` without changing the
capture schema.

Each click summary contains visual lineage and a network fingerprint derived
only from application messages larger than the observed four-byte heartbeat
shape. Repeated fingerprints in comparable visual states become semantic
candidates.

Maturity remains:

`observed -> repeated candidate -> visually labeled -> human reviewed -> validated`

Only a validated mapping may update the semantic task graph. Validation does
not authorize playback: execution policy and postcondition evidence remain
separate gates.

## Safety boundary

- no headers, bodies, credentials or raw proprietary messages are persisted;
- no CA is installed and TLS remains encrypted;
- no request is replayed, altered or synthesized;
- no pinning, authentication or anti-cheat protection is bypassed;
- timing and byte size never prove action meaning alone;
- coordinates and nearby text never prove semantic meaning alone.
