# Checking a VPS before paying

I'm lucky with servers, but you might not be. So to avoid overpaying for a server that later turns out unsuitable for a VPN deployment, check the points from the checklist below in the cheapest test mode.

In other words, before deploying it's better to make sure the server suits you: pings pass, ports are open, DNS works, and the sites you need aren't blocked by SNI.

## What to check on the VPS

- **ICMP** — basic connectivity. Ping < 100 ms from your region.
- **TCP 443** — the port must be open. REALITY requires the client to reach your server on this port.
- **DNS** — resolution of popular domains (`google.com`, `youtube.com`, `github.com`).
- **SNI censorship** — REALITY masks itself as a legitimate site. If some censor cuts TLS handshakes by SNI to popular domains, REALITY may work poorly. This is harder to check without specialized scripts.

## Ready-made tools

Below are external projects that I don't bundle into the repository. Download and run them separately.

### `AiCarrox/carrox-vps-check`

A single bash script, ~5 minutes for a full run. Covers 14 items: virtualization, network, IP, disk, routing, streaming unlocks.

GitHub: https://github.com/AiCarrox/carrox-vps-check

Good for an overall VPS check.

### `dy0422/ipcheck-plus`

IP quality + streaming and AI-service unlocks. Useful if you want to know how the VPS looks to external services.

GitHub: https://github.com/dy0422/ipcheck-plus

## What should be OK before paying

- Ping to the VPS < 100 ms (or whatever is typical in your region).
- TCP 443 open.
- DNS works (for example, `dig google.com @8.8.8.8` via the VPS).
- No DPI on SNI to popular domains (critical for REALITY).

## Manual commands

If you don't want to run automatic scripts, here's the minimal check:

```bash
ping -c 4 <VPS_IP>                  # basic connectivity
nc -zv <VPS_IP> 443                # TLS/HTTPS port (REALITY will listen here)
curl -4 https://ifconfig.io        # after VPN deployment — the client's external IP
```

Expected command results (approximate):

- `ping` — 4 packets sent and received, `0% packet loss`, response time in milliseconds (for example, `time=25.3 ms`). If there are losses or the time is above 150 ms, the server is far away or overloaded.
- `nc -zv <VPS_IP> 443` — `succeeded!` — the port is open. `Connection refused` — the port is closed or nothing listens, deal with it before paying.
- `curl -4 https://ifconfig.io` — shows the external IP:
  - VPN off — your provider's IP;
  - VPN on without WARP — your VPS IP;
  - VPN on with WARP — the Cloudflare IP.

The first two are before deployment. The third — after connecting through a VPN client.

## Warning

A manual check doesn't cover specialized DPI systems. If you know censorship is strict in your region, use `carrox-vps-check` or a similar script before a long-term purchase. There aren't many such tools, and they go stale faster than filtering systems update.
