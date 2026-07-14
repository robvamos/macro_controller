# doomsday-runtime-roster-acquisition

- Producer: ddgameass
- Status: draft
- Interface version: 0.2.0
- Current transport: Python in-process plus versioned JSON registry
- Default control mode: read-only and supervised

## Purpose

This interface exposes runtime discovery and evidence-preserving roster capture
without coupling consumers to registry details, VirtualBox commands, BlueStacks
configuration or Win32 device contexts.

Architecture and safety boundaries are documented in
[runtime-roster-acquisition.md](../docs/architecture/runtime-roster-acquisition.md).

## Runtime registry

Canonical project snapshot:

[game_runtime_registry.json](../data/doomsday/runtime/game_runtime_registry.json)

Schema: `doomsday.runtime.registry.v1`.

Required top-level fields:

| Field | Meaning |
| --- | --- |
| schema | Registry contract version |
| observed_at | UTC observation timestamp |
| workstation | Host on which paths were observed |
| active_runtime_id | Preferred runtime, or null |
| runtimes | Historical, available and active runtime records |
| excluded_candidates | Checked but absent or unverified alternatives |
| safety | Probe side-effect guarantees |

Consumers load it through `load_runtime_registry`; they should not assume that
absolute paths are portable to another workstation.

## Discovery service

Public entry point:

```python
from doomsday.runtime import GameRuntimeDiscoveryService

registry = GameRuntimeDiscoveryService().discover()
```

`discover()` may read:

- Windows uninstall/application registry;
- allowlisted BlueStacks configuration fields;
- process metadata;
- VirtualBox `list vms` and `showvminfo --machinereadable`;
- installation version files.

It must not start the game, a VM, an emulator or ADB. Device/account IDs and
credentials must not be returned.

`write_snapshot(path)` is an explicit mutation and is never called by
`discover()`.

## Roster capture port

Public package:

```python
from doomsday.services.live_roster_service import (
    GameRosterCaptureProvider,
    LiveRosterAcquisitionService,
    NativeWindowCaptureProvider,
    RosterCaptureSession,
    RosterObservation,
)
```

`GameRosterCaptureProvider` requires:

- `runtime_id`;
- `capture_method`;
- `capture_frame() -> PIL.Image.Image`.

The native provider requires an already visible Doomsday window. It does not
bring the window to front, click, type or navigate.

`LiveRosterAcquisitionService.capture_supervised_frame()` writes only to the
destination explicitly supplied by the caller.

## Observation contract

`RosterObservation` contains:

- hero_id;
- atomic field mapping;
- confidence from 0 to 1;
- observed_at;
- source_ref;
- capture_method;
- runtime_id;
- game_version;
- normalization notes.

`to_contributions()` emits one `ProviderContribution` per field with provider
type `first-party-game-ui`. The output is suitable for the shared evidence
resolver and never performs a roster write.

`observation_from_ocr_text()` uses the existing OCR parsers and removes
unobserved default values. It rejects empty/unreliable results.

## Stability

Stable in 0.1.0:

- runtime registry schema and loader validation;
- read-only discovery guarantees;
- provider capture port;
- observation-to-contribution mapping.

Experimental:

- screen-region calibration beyond the validated home `Eroe` OCR anchor;
- hero-list segmentation;
- automatic UI navigation.

Stable in 0.2.0:

- an injected BlueStacks capture adapter that accepts only an already verified
  ADB session and executes only `screencap -p`;
- fail-closed detection of the static-port collision between installed
  BlueStacks instances;
- immutable artifact storage and candidate ingestion;
- explicit preview, per-field decision, confirmation and atomic roster commit;
- optimistic revision locking, audit, fact history and evidence outbox;
- idempotent commit retry and outbox publication.
