# Shell clients

> This is the English copy of [README.md](README.md); the Russian file is the base.

Alternative command-line clients for provisioning the VPN server, written as
plain shell scripts. They are self-contained (no dependency on the Python
client, and vice versa).

Both clients are **supported** — they keep working and are documented; they are
not developed further. New functionality lands in the Python client only.

| Runtime | File | Runs on |
|---|---|---|
| Bash | `bash/provision-vpn.sh` | Linux, WSL (Ubuntu/Debian) |
| PowerShell | `powershell/Provision-VPN.ps1` | Windows (WSL required; wraps the Bash client) |

Both clients operate on the repository root (the parent of this directory):
`inventory.yml` and the `downloaded-clients/` output directory live next to
`deploy.yml`, not inside this folder.

Quick start:

```bash
# Bash (Linux/WSL)
./shell-clients/bash/provision-vpn.sh -H 1.2.3.4 --pkey ~/.ssh/id_rsa
```

```powershell
# PowerShell (Windows)
.\shell-clients\powershell\Provision-VPN.ps1 -HostName 1.2.3.4 -PKey C:\Users\You\.ssh\id_rsa
```
