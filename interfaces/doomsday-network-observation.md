# doomsday-network-observation

- Producer: ddgameass
- Status: experimental
- Interface version: 0.1.1
- Default mode: local PID, metadata-only, TLS passthrough

## Purpose

This interface observes network *shapes* produced by the user's own Doomsday
client so they can later be correlated with validated UI transitions. It is an
evidence source, not an API client and not proof that a server operation has a
particular game meaning.

## Runtime and installation

- project-local mitmproxy 12.2.3: `.tools/mitmproxy`;
- existing Wireshark 4.4.6 and Npcap 0.9982 for packet-level classification;
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

The shortcut is `C:\Users\Public\Desktop\Doomsday.lnk`, whose resolved target
is `F:\Doomsday\DoomsdayLastSurvivors.exe`. The observer never launches the
versioned `Doomsday.exe` directly; that unsupported path returns error `0x4`.

Stop an active background session early:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_network_observation.ps1
```

Sessions are written under `.tools/network_observation/<timestamp>/` and are
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
