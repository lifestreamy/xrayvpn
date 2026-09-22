# AGENTS.md — entry points for unfamiliar agents

> Pure pointer file. If you are an AI coding agent reading this repo for the first time,
> start with the files below to understand the project. No project-specific workflow or
> authoring patterns are encoded here — this file is intentionally tool-agnostic.

## What this project is

Personal VLESS Xray Reality VPN server deployment, automated with Ansible.
See `README.md` (RU) / `README.en.md` (EN) for the full description.

## Read these first

- `README.md` or `README.en.md` — project overview, motivation, scope, contents.
- `LICENSE` / `LICENSE.ru.md` — licensing terms (read before touching the code).
- `docs/user/SETUP.md` — provisioning and initial deployment.
- `docs/user/TEST-VPS.md` — validating a fresh VPS before running the playbook.
- `docs/user/ROTATION.md` — credential/certificate rotation procedures.
- `docs/user/CLIENT-STATUS.md` — tested VPN clients.
- `docs/dev/RELEASE.md` — release policy: versioning, tags, changelog.
- `docs/user/PLANNED.md` — what is coming next (roadmap).
- `docs/user/GLOSSARY.md` — domain-specific terms used in this project.

## Entry-point files

- `deploy.yml` — top-level Ansible playbook.
- `inventory.yml.example` — template for the inventory (real `inventory.yml` is gitignored).
- `shell-clients/bash/provision-vpn.sh` / `shell-clients/powershell/Provision-VPN.ps1` — convenience wrappers around the playbook.
- `python-client/` — the primary client (Python CLI `xrayvpn`), local and remote execution modes.
- `group_vars/` — Ansible group variables.
- `roles/` — Ansible roles (the actual logic lives here).

## Tech stack

- **Automation:** Ansible (playbooks + roles), Jinja2 templates.
- **Server:** Xray-core with VLESS Reality.
- **Optional outbound:** Cloudflare Warp.
- **Client configs produced:** Amnezia, Clash Verge, FlClash (JSON / YAML).

## Validate without deploying

```bash
ansible-playbook --syntax-check -i inventory.yml.example deploy.yml
ansible-lint deploy.yml roles/
```