# Client status

Which VPN clients I tested: what I use, what works but I don't recommend, and what I haven't tested.

- ✅ green check — I use it myself / I recommend it.
- ⚠️ yellow triangle — works, but has issues. Not recommended.
- — not tested.

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

- **Clash Verge** — my main client on Windows 11. Import `clash_client_*.yaml`.
- **FlClash** — my main client on Android. The same YAML config.
- **Amnezia** — the first client this project generated configs for. It connects, but has issues: on Windows the split tunnel can take down the network stack; on Android keepalive and background work are unstable. Prefer Clash Verge or FlClash unless you specifically need Amnezia.
