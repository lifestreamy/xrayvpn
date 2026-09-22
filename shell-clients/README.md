# Shell-клиенты

> English version: [README.en.md](README.en.md).

Альтернативные командные клиенты для развёртывания VPN-сервера — обычные шелл-скрипты.
Самодостаточны: не зависят от Python-клиента, и наоборот.

Оба клиента **поддерживаются**: работают и задокументированы, но дальше не развиваются.
Новые возможности появляются только в Python-клиенте.

| Оболочка | Файл | Запуск на |
|---|---|---|
| Bash | `bash/provision-vpn.sh` | Linux, WSL (Ubuntu/Debian) |
| PowerShell | `powershell/Provision-VPN.ps1` | Windows (нужен WSL; оборачивает Bash-клиент) |

Оба клиента работают от корня репозитория (родительский каталог): `inventory.yml` и
каталог результата `downloaded-clients/` лежат рядом с `deploy.yml`, а не здесь.

Быстрый старт:

```bash
# Bash (Linux/WSL)
./shell-clients/bash/provision-vpn.sh -H 1.2.3.4 --pkey ~/.ssh/id_rsa
```

```powershell
# PowerShell (Windows)
.\shell-clients\powershell\Provision-VPN.ps1 -HostName 1.2.3.4 -PKey C:\Users\You\.ssh\id_rsa
```
