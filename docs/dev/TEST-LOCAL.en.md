# Local end-to-end test (molecule → client)

> Verified: 2026-08-21 (after first green molecule run, branch alpha). Updated 2026-08-26: molecule uses the delegated driver and `xray_runtime: native` — Xray is installed directly on the runner, no container.

This document describes the manual end-to-end check after `molecule test` passes green. The goal is to confirm that traffic from the local machine through the locally-installed Xray actually exits through the REALITY tunnel.

`molecule test` only confirms that the role deployed and the artifacts are in place. The real handshake with the server, traffic routing, and DNS through the client are a separate step. They are semi-automatic because the client runs on your machine and the server (under `xray_runtime: native`) runs on the same host under systemd.

## Requirements

- WSL2 with Docker Desktop (or Docker Engine directly inside a WSL distro).
- The `mihomo` utility (the Clash Verge core). Download it from the Clash Verge distribution or from the mihomo project on GitHub.
- `curl` for the checks.
- A free TCP 443 on the WSL2 side (see §1 below).

## Step 1. Preparation

Before the test, check two things.

### 1.1. Port 443 is free in WSL2

```bash
sudo ss -lntp | grep ':443 '
```

If the port is busy (often occupied by the Docker Desktop proxy or another service), stop that process or switch to another port in the molecule scenario.

### 1.2. Clash Verge is stopped

Clash Verge installs its own TUN driver and proxy. Running it alongside the test mihomo causes port and TUN-interface conflicts. Stop Verge for the duration of the test.

## Step 2. Pull the client config

After `molecule converge` (delegated driver) the client config is on the runner: `/root/vpn-configs/clash_client_0.yaml`. Copy it to your working directory:

```bash
cp /root/vpn-configs/clash_client_0.yaml ./clash_client_0.yaml
```

## Step 3. Adapt the config for the test

Open `clash_client_0.yaml` and patch the block so the client does not try to install a TUN (which conflicts with the host) and can reach the local network:

| What | Default | For the test |
|---|---|---|
| `proxies[0].server` | `<server IP>` | `127.0.0.1` or the WSL2 IP (see §3.1) |
| `tun.enable` | `true` | `false` |
| `mixed-port` | `7890` | `7899` (any free port) |
| `dns.listen` | `0.0.0.0:1053` | `127.0.0.1:1053` |
| `IP-CIDR 192.168/10/172.16` rules | `DIRECT` | `Proxy` (see §3.2) |

### 3.1. Which address to use in `server`

It depends on where Xray runs.

| Scenario | Use in `server` |
|---|---|
| Xray installed natively on the same WSL2 / Linux host | `127.0.0.1` |
| Xray on another WSL2 / Linux host or remote VPS | that host's address (`hostname -I`) |

### 3.2. Why change the LAN rules

By default the config sends traffic to `192.168/10/172.16` directly (bypassing the tunnel). That is correct for production — the local network should not go through the VPN. But for the LAN-hop check (§5 step 7) we need the opposite: route LAN traffic through the tunnel. Change `DIRECT` to `Proxy` only for the duration of the test.

## Step 4. Start the client

### 4.1. Validate the config

```bash
mihomo -t -d . -f clash_client_0.yaml
```

If the config is valid, you will see `Configuration file ... is valid`. Otherwise — an error pointing at a line.

### 4.2. Run

```bash
mihomo -d . -f clash_client_0.yaml
```

Logs go to stdout (or to `mihomo.log` if you enable `log-file` in the config). `info` level is enough for debugging.

## Step 5. Checks

Run them in order. Each step depends on the previous one.

### 5.1. mihomo log — no TLS/REALITY errors

Open the mihomo log. There should be no lines like `tls: handshake failure` or `reality: ...` at ERROR level. If there are, the handshake failed and there is no point continuing — debug first.

### 5.2. Xray log — successful connections

```bash
journalctl -u xray --no-pager -n 30
```

Look for lines like `accepted ... vless ...`. If none, the client did not reach the server.

### 5.3. CONNECT — `generate_204`

```bash
curl -x http://127.0.0.1:7899 https://google.com/generate_204
```

Expected: empty body and HTTP code `204`. This confirms the tunnel is up and HTTPS works through it.

### 5.4. EXIT-IP — `ifconfig.io`

```bash
curl -x http://127.0.0.1:7899 https://ifconfig.io
```

Expected: your VPS IP (without WARP) or a Cloudflare IP (with WARP — but WARP is disabled in the molecule scenario). Not your home ISP IP — that would mean traffic bypasses the tunnel.

### 5.5. DNS through mihomo

```bash
nslookup google.com 127.0.0.1 -port=1053
```

Expected: `Address: 198.18.x.x` (a fake-IP from mihomo) or a real `google.com` IP. If DNS does not resolve, check that the `dns.listen` block in the mihomo config points at `127.0.0.1:1053`.

### 5.6. LAN TCP through the tunnel

```bash
curl -x http://127.0.0.1:7899 http://<LAN host>:<port>
```

Example: `curl -x http://127.0.0.1:7899 http://192.168.1.1:80`. Your router should answer. This confirms traffic to LAN hosts also goes through the tunnel (after the §3.2 rule fix).

ICMP is not tunnelled through Xray, so `ping` does not work here. Use TCP instead (curl, wget, nc).

## Step 6. Wrap up

When all 7 checks are green, the manual end-to-end test passes.

Record the result in this file:

```
- 2026-08-21 — end-to-end test passed (molecule + mihomo, WSL2, Ubuntu 22.04).
```

After that the changes can roll forward into the branch and merge.

## Common errors

| Symptom | Most likely cause |
|---|---|
| `Connection refused` on curl | port 7899 is in use, or mihomo did not start |
| `502 Bad Gateway` | mihomo cannot reach Xray (see §3.1) |
| DNS works but HTTP does not | rules in §3.2 not fixed, traffic goes DIRECT |
| Xray journal: `connection refused` from client | wrong `server` in config (see §3.1) |

## What's next

The end-to-end check is complete. From here you can work with the config under `config/`, see the project README.
