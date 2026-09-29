# doomsday-network-observation

- Producer: ddgameass
- Status: experimental
- Interface version: 0.4.0
- Default mode: local PID, metadata-only, TLS passthrough

## Purpose

This interface observes network *shapes* produced by the user's own Doomsday
client so they can later be correlated with validated UI transitions. It is an
evidence source, not an API client and not proof that a server operation has a
particular game meaning.

## Runtime and installation

- optional mitmproxy venv: path configured by workstation setting `networkObserverDir`;
- optional Wireshark/tshark installation for packet-level classification;
- versioned policy: [observation_profile.json](../data/doomsday/network/observation_profile.json).

Mitmproxy's official documentation confirms that local capture is available on
Windows and supports a target PID. The default addon sets
`ClientHelloData.ignore_connection = true`, so TLS is forwarded without
substitution after SNI/ALPN and destination metadata are recorded.

References:

- <https://docs.mitmproxy.org/stable/concepts/modes/#local-capture>
- <https://docs.mitmproxy.org/stable/concepts/certificates/>

## Start and stop

Install or realign the project-local optional runtime:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_network_observation.ps1
```

To launch through the same supported Desktop shortcut and then observe the game
process, run an elevated PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_network_observation.ps1 `
  -TargetProcess Doomsday -LaunchViaShortcut -Minutes 5
```

The shortcut comes from workstation setting `gameShortcutPath`, with the
Windows Public Desktop launcher as fallback. The observer never launches the
versioned `Doomsday.exe` directly; that unsupported path returns error `0x4`.

Stop an active background session early:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_network_observation.ps1
```

Sessions are written under
`workstation/local/<profile>/runtime/network_observation/<timestamp>/` and are
excluded from Git. Summarize a session without exposing query values:

```powershell
python .\scripts\summarize_network_observation.py `
  .tools\network_observation\<timestamp>\events.jsonl
```

## Record schema

Every line uses `doomsday.network-observation.v1`. Possible records include:

- server connection destination and transport;
- TLS ClientHello SNI and offered ALPN;
- TCP/UDP message count and directional byte totals;
- timestamp, direction, ordinal and byte count for each TCP/UDP message;
- HTTP method, host, normalized path template, parameter names, MIME types,
  status and sizes, only in a future explicitly enabled decryption session.

The schema contains no fields for headers or bodies. Likely IDs in paths become
`{id}`, `{uuid}`, `{hex}` or `{opaque}`. Query values are discarded, and names
such as token, session, signature and secret collapse to `{sensitive}`.

## Safety and semantic boundary

- no Windows proxy setting is changed;
- no CA is trusted by the operating system;
- no certificate-pinning, authentication or anti-cheat bypass;
- no request replay or mutation;
- no raw TCP, UDP, HTTP request or response content is persisted;
- no action meaning is inferred from timing alone.

An endpoint can become a semantic candidate only after it co-occurs with a
validated UI transition in repeated supervised sessions. Promotion into the
game knowledge graph remains a separate reviewed operation.

## Known limits

Local PID capture sees only connections created after the observer starts. The
current client has also shown persistent custom TCP and UDP traffic, which may
not contain HTTP at all. Wireshark metadata can classify those protocols, but
encrypted or proprietary payloads remain opaque in this phase.

Version 0.1.2 emits one metadata-only `tcp_message` or `udp_message` record as
each message crosses a captured flow. This enables supervised temporal
correlation with known UI transitions without waiting for a persistent
connection to close and without storing message content.

## Learning-mode binding

Version 0.2.0 makes metadata observation the default companion of supervised
Learning. The learner attaches an already-compatible observer or starts one for
the game PID, then stores the binding in its crash-safe `session.json`.

Each click records:

- a marker in the network session;
- the network event indices before and after visual stabilization;
- the click crop and full-window frames;
- a metadata-only application shape and stable fingerprint;
- the first observed client-to-server/server-to-client latency candidate.

The generated `network_correlation_summary.json` retains the status
`candidate_requires_repetition_and_visual_validation`. Repeated fingerprints
can support a reviewed semantic mapping, but one temporal match cannot assign
an operation name or grant execution authority.

## Annotated semantic analysis

Version 0.3.0 adds
`analyze_annotated_network_session()` for operator-marked proxy sessions. It:

- separates recurring 4-byte heartbeat shapes from application candidates;
- inventories transport channels without retaining payloads;
- aggregates message direction, size and count;
- detects small-client-command / server-response candidates with bounded
  latency;
- distinguishes unmatched server-push candidates;
- binds each aggregate fingerprint to the operator's declared marker window;
- marks every result as requiring repetition and visual validation;
- emits no payload, request template or replay mechanism.

The command-line entrypoint is:

```powershell
python .\scripts\analyze_annotated_network_session.py `
  .tools\network_observation\<session> `
  --output data\doomsday\knowledge\network_observations\<session>.json
```

The final marker has no closing boundary and is therefore explicitly emitted
as `unbounded_missing_next_marker`, rather than absorbing unrelated traffic
recorded after the operator's last action.

## Navigable task/call read model

Version 0.4.0 exposes the persisted observations in the desktop tab
`Mappa Task/Chiamate`. The read model joins:

- learning domains;
- operator-declared semantic windows;
- conservative links to known UI nodes;
- operation class;
- maturity state;
- metadata-only exchanges, server pushes and aggregate shapes;
- session, fingerprint, channel, message-size and latency evidence.

The hierarchy is navigable from domain to task, UI function and individual
call shape. Search, domain and maturity filters never change evidence. The
view contains no payload decoder, endpoint inference, replay control or
execution-authority promotion.
