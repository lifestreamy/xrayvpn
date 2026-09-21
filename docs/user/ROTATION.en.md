# Rotation — Runbook

I wrote this runbook as a reminder after having to rotate keys on my own VPS. If something doesn't match the real behavior — open an issue and I'll fix it. The guide applies when your VPS has already been deployed with this utility. If it was deployed with another utility, proper operation isn't guaranteed — it's better to remove the old deployment first and redeploy with this one.

## What rotation is and when to do it

**Rotation** is replacing VPN credentials with new ones: keys, client identifiers and related files. After rotation, old client configs stop connecting — you need to distribute new ones.

When it's done:

- **Compromise.** You found out (or suspect) that the REALITY keys or short ID leaked. In this case rotation is a must. Don't put it off.
- **Personal schedule.** You decided to rotate keys regularly — for example, once every 90 days, just in case.
- **Test.** You want to make sure rotation actually works on your VPS — that backups are written, new configs are downloaded, clients reconnect. Then you run the procedure once "for practice" and restore the original keys afterwards (see §5 below).

In all cases the algorithm is the same — section §2 below.

## Glossary

Briefly — the terms used in this file. All project terms — in [`docs/user/GLOSSARY.en.md`](GLOSSARY.en.md).

- **Rotation** — replacing credentials with new ones. Old credentials stop working.
- **The `xray_reality_rotate` switch** — a parameter that makes the role regenerate keys, short IDs and client UUIDs.
- **REALITY** — a stealth VPN technology in Xray that masks the server as a legitimate third-party site.
- **WARP** — an extra outgoing tunnel through Cloudflare. Rotated with a separate procedure (see §4).
- **`<VPS_IP>`** — your VPS IP address. Replace it before running commands.

## 1. How to control the rotation settings

Three scenarios:

| Component | Where it lives / action | Effect |
|---|---|---|
| Changing `xray_reality_rotate` | `config/settings.yml` or `-e ...` | Full rotation of REALITY keys, short ID and client UUIDs. |
| Changing `num_clients` | `config/settings.yml` | How many client configs to generate. Without `xray_reality_rotate: true` it acts as add/reduce. |
| WARP rotation | `/root/xray-config/wgcf-account.toml`, `/root/xray-config/wgcf-profile.conf` — delete manually, then re-run | Rotates WARP credentials (if enabled). Independent of `xray_reality_rotate`. Details in §4. |

## 2. Rotating the REALITY identity

### How to enable full rotation

The role has one switch:

```yaml
xray_reality_rotate: true
```

Pass it via `config/settings.yml` for a one-off run, or via `-e xray_reality_rotate=true` on the command line:

```bash
ansible-playbook -i inventory.yml deploy.yml -e xray_reality_rotate=true
```

### What changes

| What changes | Without rotation (default) | With rotation (`xray_reality_rotate: true`) |
|---|---|---|
| REALITY `private_key` | ❌ not touched | ✅ regenerated |
| REALITY `public_key` | ❌ not touched | ✅ regenerated |
| REALITY `short_id` | ❌ not touched | ✅ regenerated |
| Client UUIDs (in `reality-state.json`) | ❌ kept; new UUIDs only added when `num_clients` grows | ✅ all recreated |
| `/root/xray-config/reality-state.json` | ❌ rewritten only to top up UUIDs to `num_clients` | ✅ rewritten |
| `/root/xray-config/reality-state.json.bak-YYYY-MM-DD-HH:MM:SS` | ❌ not created | ✅ created from the old state |
| `/etc/xray/config.json` | ❌ rebuilt from the saved state and parameters (keys unchanged) | ✅ rebuilt with new keys |
| `/root/vpn-configs/*.json` and `*.yaml` (on the VPS) | ❌ overwritten based on the same state | ✅ overwritten with new UUIDs |
| `downloaded-clients/` (locally) | ❌ same as the previous run | ✅ new configs with new UUIDs |
| WARP credentials (`wgcf-account.toml`, `wgcf-profile.conf`) | ⚠️ rotated separately, see §4 below | ⚠️ rotated separately, see §4 below |

⚠️ — changed by a separate procedure, not by `xray_reality_rotate`.

### Increasing or reducing the number of clients

If you changed `num_clients` and ran the playbook without `xray_reality_rotate: true`:

- Increased `num_clients` → new UUIDs are added to `reality-state.json`, new client configs are exported.
- Decreased `num_clients` → existing UUIDs are kept, fewer configs are exported.
- Increased again → the previously kept UUIDs are used again.

If the switch is set to `xray_reality_rotate: true`, all client secrets will be updated.

### What happens during rotation

The full comparison is in the table above. Briefly:

1. The current `reality-state.json` is copied to a backup `reality-state.json.bak-YYYY-MM-DD-HH:MM:SS` in the same folder.
2. The current state file is deleted.
3. A new X25519 key pair, a new random short ID and new client UUIDs are generated.
4. A new `reality-state.json` is written.
5. The Xray service restarts with the updated `config.json`.

Right after the run, check that the backup of the old state and the new `reality-state.json` appeared:

```bash
ls -la /root/xray-config/reality-state.json*   # the backup and the new file should be visible
```

### After the run

- New client configs will be downloaded locally to the project folder from which you ran the script — `/downloaded-clients/` — and saved to `/root/vpn-configs/` on the VPS.
- Load the new configs into your VPN clients: Clash Verge / FlClash / Amnezia.
- Set `xray_reality_rotate` back to `false` in `config/settings.yml` if you want to keep the identity on the next runs.

## 4. Rotating WARP credentials

WARP credentials come from `wgcf` and are stored in two files on the VPS:

- `/root/xray-config/wgcf-account.toml`
- `/root/xray-config/wgcf-profile.conf`

Important: `wgcf-identity.json` is not used in this setup. Older versions of this runbook mentioned that file — ignore those mentions.

To rotate:

1. Connect to the VPS via SSH:

   ```bash
   ssh root@<VPS_IP>   # replace <VPS_IP> with your IP
   ```

2. Delete both files above:

   ```bash
   rm -v /root/xray-config/wgcf-account.toml /root/xray-config/wgcf-profile.conf   # delete both files
   ```

3. Re-run the playbook. The role will call `wgcf register` and `wgcf generate` again, and the WARP outbound in `xray_config.json` will pick up the new credentials. If you work from a local machine (not directly on the VPS), the command is the same:

   ```bash
   ansible-playbook -i inventory.yml deploy.yml   # other run methods — see README.md
   ```

Check WARP routing from outside the VPS, through a VPN client. Don't rely on `curl` from inside the Xray container.

From the machine where the VPN client runs (laptop, phone, another server), check the external IP. On a successful deployment it will show the VPS IP or the Cloudflare IP if WARP is enabled:

```bash
curl -4 https://ifconfig.io   # run on the client device, not on the VPS
curl -4 https://cloudflare.com/cdn-cgi/trace   # alternative, look for colo= and ip=
```

## 5. Recovery

The role creates a timestamped backup before rotation. Typical recovery:

1. Connect to the VPS via SSH: `ssh root@<VPS_IP>`.
2. Look at the backups: `ls -la /root/xray-config/reality-state.json.bak-*`.
3. If you want to roll back to the previous state. Substitute `YYYY-MM-DD-HH:MM:SS` with the real backup name from step 2:
   ```bash
   cp /root/xray-config/reality-state.json.bak-YYYY-MM-DD-HH:MM:SS \
      /root/xray-config/reality-state.json
   chown root:root /root/xray-config/reality-state.json
   chmod 0600 /root/xray-config/reality-state.json
   ```
4. Make sure `xray_reality_rotate: false` is set in `config/settings.yml`.
5. Re-run the playbook. The role will pick up the restored state and regenerate `config.json` and the client configs to match it.

Keep the latest backup until you've verified the new rotation end to end.
