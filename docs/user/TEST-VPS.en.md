# Checking a VPS before paying

I've been lucky with servers — you might not be. Before paying for a VPS long-term, take the
cheapest test plan and run through the short checklist below. The point: make sure the server
answers you — pings pass, ports are open, DNS works, and TLS to the sites you need isn't cut.

## What to check

- **ICMP** — basic connectivity: under 100 ms ping from your region.
- **TCP 443** — the port must be reachable: that's where REALITY will listen.
- **DNS** — resolving common domains (`google.com`, `youtube.com`, `github.com`).
- **SNI censorship** — REALITY disguises itself as a legitimate site; if a censor drops TLS
  handshakes to popular domains by SNI, REALITY will work badly. This is the hard part to test.

## What must be OK before you pay

- Ping to the VPS < 100 ms (or whatever is normal for your region).
- TCP 443 open.
- DNS works (e.g. `dig google.com @8.8.8.8` from the VPS).
- No SNI blocking to popular domains — critical for REALITY.

## Commands

SSH into the VPS after buying the test plan and run:

```bash
ping -c 4 <VPS_IP>                  # basic connectivity (from your machine)
nc -zv <VPS_IP> 443                 # the TLS/HTTPS port (listen on VPS, probe from your side)
curl -4 https://ifconfig.io         # after deployment and the client — the egress IP
```

Expected:

- `ping` — 4 packets sent, 4 received, `0% packet loss`, time in milliseconds (e.g.
  `time=25.3 ms`). Any loss or > 150 ms — the server is far or overloaded.
- `nc -zv <VPS_IP> 443` — `succeeded!`; `Connection refused` — the port is closed or nothing
  listens, sort it out before paying.
- `curl -4 https://ifconfig.io` — before VPN it shows the data-center IP; through the client
  without WARP — your VPS IP; with WARP — a Cloudflare IP.

The first two checks run before deployment, the last one after.

## Warning

The manual set does not catch subtle DPI systems — they can cut SNI selectively, and simple
commands won't reveal it. In a heavily censored region, treat this as a real risk: only actual
traffic after payment tests it fully.
