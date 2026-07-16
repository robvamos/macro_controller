# Network observation architecture

The network learner is intentionally split into four trust zones:

1. **Connection inventory** records process, destination, port and transport.
2. **Encrypted shape observation** records TLS SNI/ALPN and byte counts while
   forwarding ciphertext untouched.
3. **HTTP schema observation** is a future opt-in phase that requires normal CA
   trust by the client and still discards secrets and bodies.
4. **Semantic correlation** compares repeated network shapes with validated UI
   transitions; it never treats temporal proximity as proof.

The default implementation stops at zone 2. The mitmproxy CA may be generated
inside `.tools/network_observation/mitmproxy-config`, but it is not installed in
any Windows or application trust store.

## Launcher boundary

The supported native-client entrypoint is the public Desktop shortcut
`C:\Users\Public\Desktop\Doomsday.lnk`. It resolves to the IGG launcher
`F:\Doomsday\DoomsdayLastSurvivors.exe`, which prepares the context required by
the versioned game binary. Direct execution of `Doomsday.exe` is forbidden by
the observation workflow because the client responds with `ErrCode: 0x4`.

## Why two tools are retained

The native client currently opens HTTPS connections as well as long-lived TCP
connections on non-HTTP ports and a UDP socket. Mitmproxy is useful for HTTP,
TLS and connection events. The already-installed Wireshark/Npcap stack remains
the passive classifier for protocols that are not HTTP. Neither tool grants a
reason to decode, replay or alter proprietary traffic.

## Correlation lifecycle

`unclassified shape -> repeated candidate -> UI-correlated candidate -> human-reviewed mapping`

Only the last state may inform an API-shaped adapter. Even then, the adapter is
read-only until authentication, rate limits, terms, error handling and game
version boundaries have been explicitly modeled.
