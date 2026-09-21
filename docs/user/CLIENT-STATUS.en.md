# Client status

Which VPN clients I've tested with this setup and how they work. Honestly: what I use myself, what works but I don't recommend, and what I haven't tested at all.

Legend:

- ✅ green check — I use it myself / I recommend it.
- ⚠️ yellow triangle — works, but has known issues. I don't recommend it.
- — blue dash — not tested.

## My experience with clients

| Client | Status |
|---|---|
| Clash Verge (Windows 11) | ✅ I use it myself |
| FlClash (Android) | ✅ I use it myself |
| Amnezia (Windows 11, Android) | ⚠️ works, but has stability issues |
| Others | — not tested |

## Clients by platform

| Client | Windows | macOS | Linux | Android | iOS |
|---|---|---|---|---|---|
| Clash Verge | ✅ | — | — | — | — |
| FlClash | — | — | — | ✅ | — |
| Amnezia | ⚠️ | — | — | ⚠️ | — |

## Notes

- **Clash Verge** — my main client on Windows 11. Import `clash_client_*.yaml` and it works.
- **FlClash** — my main client on Android. The same YAML config.
- **Amnezia** — the first client this project generated configs for. It connects, but has known issues: on Windows split-tunnel can crash the network stack, on Android keepalive and background operation are unstable. Prefer Clash Verge or FlClash unless you specifically need Amnezia.
