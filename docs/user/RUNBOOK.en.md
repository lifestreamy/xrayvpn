# RUNBOOK — recovering the VPN

The VPN fails in two ways: the service is down, or the outbound path has degraded. The second one is the tricky case — the service reports `active`, clients look "connected", and there is no internet. This runbook exists mostly for it. Rebooting the OS is almost never the answer.

## Symptoms and diagnosis

| Symptom | Likely cause | Check over SSH |
|---|---|---|
| Client connected, no internet | WARP tunnel degraded (outbound errors) | `journalctl -u xray --since '-30m' -o cat \| grep -Ec 'wireguard\|outbound'` |
| Client cannot connect, service `active` | Another process owns port 443 | `ss -tulpn '( sport = :443 )'` |
| Service is `failed` | Xray exited; the reason is in the journal | `systemctl status xray` |
| Logs empty after a reboot | journald without persistence (the role fixes this) | `ls /var/log/journal` |

The error count is the main reading. Single digits are noise. Tens — that's the incident.

## Point restart of the service

This fixes the degraded outbound. Only Xray restarts; clients reconnect in 10–15 seconds.

1. SSH into the server. From a phone: Termux or Termius.
2. Grab the diagnostic snapshot before restarting — those lines are gone afterwards:

   ```bash
   journalctl -u xray --since '-30m' -o cat | grep -E 'wireguard|outbound' | tail -20
   systemctl show xray -p NRestarts,ActiveEnterTimestamp
   ```
3. Restart the service:

   ```bash
   systemctl restart xray
   ```
4. Verify: `systemctl is-active xray`, `ss -tulpn '( sport = :443 )'`, then a client.
5. Health check: Xray should sit around 15 MB (`free -m`). While degrading, it burns tens or hundreds of megabytes on useless re-handshakes.

## Full reboot: when, and why rarely

Rebooting the host is the last resort. It resets everything the point restart would have fixed, and a volatile journal used to erase the only evidence of why things broke. With this role the journal persists on disk and the watchdog restarts the service on its own, so a manual reboot is justified only when:

- SSH itself does not answer;
- `ss` shows a foreign process on :443 that cannot be stopped precisely;
- the provider banner insists on a kernel reboot — but that is planned maintenance, not an emergency step.

## Logs and snapshots

- Xray and system logs live in journald on disk: capped at 120 MB and 3 days (`xray_journal_*` in `config/settings.yml`).
- `journalctl -u xray` — the service life: starts, errors, the outbound failure stream.
- `journalctl -t xray-obs -n 80` — the black box: every 10 minutes it records listeners, routes, firewall tail, memory and the WARP endpoint status. This is exactly what was missing after the reboot incident.
- `journalctl -t xray-watchdog` — automatic restarts and alerts. The watchdog restarts the service at most 3 times per hour, then logs `[ALERT]` and waits for a human. An alert means: work through the steps above by hand.
- Without SSH, from your own machine: `xrayvpn service status`, `xrayvpn service restart`, `xrayvpn service logs` (dumps the journal to a file).

## The mechanics in two sentences

WARP lives inside Xray. When the Cloudflare peer goes stale, Xray cannot rebuild the tunnel at runtime — the error lines flood the log, the process stays "healthy", and the server is deaf. A service restart recreates the tunnel from scratch.
