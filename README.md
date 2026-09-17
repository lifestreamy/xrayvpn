**Version:** v0.4.2 · **Last updated:** 2026-09-13

[![English](https://img.shields.io/badge/English-808080?style=flat)](README.en.md)
[![Русский](https://img.shields.io/badge/%D0%A0%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-00a693?style=flat)](README.md)

---

# Xray Reality VPN Server — развёртывание

> Личный VPN-сервер на своём VPS (облачном сервере) — в минимальном варианте достаточно передать в параметрах только IP и пароль root пользователя. Автоматическая настройка VLESS Xray Reality VPN + Cloudflare Warp outbound (опционально) через Ansible. Генерирует и загружает в директорию проекта готовые .json/.yaml конфиги для Amnezia / Clash Verge / FlClash.

## Содержание

- [Привет](#привет)
- [Быстрый старт](#быстрый-старт)
- [Для кого это](#для-кого-это)
- [Что делает и в чём смысл](#что-делает-и-в-чём-смысл)
- [Преимущества подхода](#преимущества-подхода)
- [Где запускается](#где-запускается)
- [Требования](#требования)
- [Конфигурация](#конфигурация)
- [Клиенты](#клиенты)
- [Подробная документация](#подробная-документация)
- [Лицензия](#лицензия)
- [Автор и контакты](#автор-и-контакты)

## Привет!

Привет, это [Тим Корелов](https://korelov.dev). Делюсь своим решением для развёртывания персонального VPN, который и вы сами можете свободно и бесплатно использовать (исключительно для защиты персональных данных, естественно, и согласно всем законам). Не забудьте посмотреть правила лицензии. 

> [!TIP]
> Если хочется сразу запустить — [Быстрый старт](#быстрый-старт).

Зачем я всё это сделал? Мой сервер — мои правила. Мне захотелось иметь свой личный VPN, где:
- никто не слушает мой трафик и не логирует мои данные
- не нужно покупать сервис у кого-то, кто может завтра упасть или поменять условия
- я вижу своими глазами, что на моём сервере происходит и почему, а не доверяю на слово кому-то другому
- я могу в любой момент обновить его компоненты и кастомизировать так, как захочу, например, добавить туннель, дополнительные сервисы

Всё автоматизировал специально, чтобы можно было переиспользовать, и не настраивать руками каждый раз.

Остановился на Ansible — подробнее, почему, в блоке ниже.

<details>
  <summary>Почему Ansible (подробности для технарей)</summary>

  Ansible — зрелый инструмент автоматизации. Он идемпотентен: повторный запуск не ломает состояние, приводит сервер к нужному виду. Он расширяемый — роли и плагины уже написаны и проверены, их не нужно писать заново. Он показывает, что именно меняется на каждом шаге, и ничего не трогает, пока не попросите. Он декларативен (но позволяет добавлять и императивные части). Вся логика уже написана: я только описываю желаемое состояние сервера через готовые модули.

  Ansible запускается на вашей машине в сценарии local (в Windows — внутри WSL) и по SSH выполняет команды на сервере. В сценарии remote Ansible устанавливается прямо на VPS — локальная настройка тогда не нужна.

</details>

Проект не просто протестирован разово — я (и множество других людей) пользуюсь им постоянно, так как делал его в первую очередь для себя и под себя. Если что-то ломается — оно ломается и у меня, поэтому я быстро вношу правки.

Но если я что-то упустил, у вас что-то сломалось, не запускается изначально или есть пожелания — создайте новый issue. Если перестал работать уже развёрнутый VPN — сначала пройдитесь по [`docs/RUNBOOK.md`](docs/RUNBOOK.md).



## Быстрый старт

Самый простой путь — standalone-приложение, без Python и Ansible: скачайте portable-сборку своей платформы (`xrayvpn-<версия>-windows-x64-portable.exe`, `xrayvpn-<версия>-linux-x64-portable`, `xrayvpn-<версия>-linux-arm64-portable`, `xrayvpn-<версия>-macos-arm64-portable`) из [раздела Releases](https://github.com/lifestreamy/xrayvpn/releases), положите в обычную папку (не в синхронизируемый диск) и запустите — на Windows просто двойным кликом. Откроется консольный помощник: достаточно набрать `deploy`, интерактивно спросится IP VPS и (скрыто) пароль; `ru` включает русский интерфейс. Файлы конфигурации (`config/settings.yml`, `inventory.yml`) можно положить рядом с исполняемым файлом — подробности в [`docs/SETUP.md`](docs/SETUP.md), раздел «Standalone-приложение».

Тем, кто работает с репозиторием, доступны три клиента и прямой запуск playbook. Параметры не обязательны: клиент можно запустить вообще без аргументов — `xrayvpn deploy` интерактивно спросит режим исполнения (по умолчанию `remote`) и IP VPS, затем скрыто запросит пароль. Минимальный случай — только IP VPS.

Запустить можно тремя клиентами или вообще без них:

- `xrayvpn` (Python) — [`python-client/`](python-client/README.md) — Windows, Linux и macOS; рекомендуется из скриптовых клиентов;
- Bash — [`shell-clients/bash/provision-vpn.sh`](shell-clients/bash/provision-vpn.sh) — Linux / WSL (поддерживается, но не развивается);
- PowerShell — [`shell-clients/powershell/Provision-VPN.ps1`](shell-clients/powershell/Provision-VPN.ps1) — Windows + WSL;
- напрямую Ansible — `ansible-playbook -i inventory.yml deploy.yml`, без клиента.

### Про конфигурацию

Минимально достаточно IP и пароля — всё остальное настроится само. Если нужно что-то поменять (число клиентов, WARP, порт, домен маскировки), дополнительная конфигурация производится через два файла:

- `inventory.yml` — подключение к VPS (создаётся из `inventory.yml.example`).
- `config/settings.yml` — параметры сервера: `num_clients`, `warp_enabled`, `xray_port`, `reality_camouflage_domain` и другие.

Подробнее про каждый файл — в [`docs/SETUP.md`](docs/SETUP.md), раздел «Файлы конфигурации».

<details>
<summary>xrayvpn (Python) — команды</summary>

Python-клиент `xrayvpn` работает одинаково на Windows, Linux и macOS; для удалённого режима WSL не нужен.

```bash
# Удалённый режим (VPS). Достаточно IP — пароль спросит скрыто.
uv run --project python-client xrayvpn deploy --execution remote --host 1.2.3.4
uv run --project python-client xrayvpn deploy --execution remote --use-inventory
```

Нет `uv`? Ставится одной командой: Windows — `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, Linux/macOS — `curl -LsSf https://astral.sh/uv/install.sh | sh`.

Хотите вводить `xrayvpn` без префикса `uv run`? Установите команду в PATH: `uv tool install --editable python-client` из корня репозитория; запускать из папки репозитория (подробности — [`python-client/README.md`](python-client/README.md)).

Остальное (`--pkey`, узел выполнения ansible `--execution local|remote`, confirmation-план, сценарии клиента) — в [`python-client/README.md`](python-client/README.md).

</details>

<details>
<summary>Bash — команды</summary>

На Windows должен быть доступен WSL с созданным образом Ubuntu/Debian — как проверить и настроить, в [`docs/SETUP.md`](docs/SETUP.md). Если Ubuntu в WSL установлен, в меню «Пуск» будет видна иконка. Если вы уже на Linux, то вам вряд ли нужно объяснять, как пользоваться терминалом. На Windows — найдите в поиске (Win + S) powershell или terminal.

```bash
./shell-clients/bash/provision-vpn.sh -H 1.2.3.4
./shell-clients/bash/provision-vpn.sh -H 1.2.3.4 --pkey ~/.ssh/id_rsa
./shell-clients/bash/provision-vpn.sh --use-inventory
```

</details>

<details>
<summary>PowerShell — команды</summary>

Как открыть командную строку: Пуск → наберите «PowerShell» → Enter. Перейдите в папку проекта:

```powershell
cd C:\путь\к\проекту
```

(вместо `C:\путь\к\проекту` подставьте реальный путь, куда распаковали файлы)

```powershell
.\shell-clients\powershell\Provision-VPN.ps1 -HostName 1.2.3.4
.\shell-clients\powershell\Provision-VPN.ps1 -HostName 1.2.3.4 -PKey C:\Users\You\.ssh\id_rsa
```

</details>

<details>
<summary>Напрямую Ansible — команды</summary>

Нужны ansible-core 2.14+ и коллекция `community.general`. Подготовьте `inventory.yml` из шаблона (команды — в разделе «Конфигурация» ниже):

```bash
# Debian 12+ / Ubuntu 24.04: подойдёт apt. На Ubuntu 22.04 apt даёт 2.12 — только pip.
pip install ansible-core
ansible-galaxy collection install community.general
ansible-playbook -i inventory.yml deploy.yml
```

В этом режиме клиентские конфиги не скачиваются — они остаются на VPS в `/root/vpn-configs`.

</details>

## Для кого это

Для тех, кто хочет свой VPN и не готов полагаться на чужие сервисы. Не важно, разбираетесь вы в Ansible, Xray, VPN, серверах или нет — скрипт сделает всё сам. Если захотите копнуть глубже, технические детали — в раскрывающихся блоках и в [`docs/`](docs/GLOSSARY.md).

## Что делает и в чём смысл

- Поднимает VPN-сервер на вашем VPS за один запуск скрипта.
- Ваши данные проходят только через ваш сервер в зашифрованном виде, никто кроме вас не читает и не логирует их. На своём сервере вы уверены, что трафик видите только вы. В публичном VPN-сервисе такой уверенности нет, особенно если вы пользуетесь „бесплатным" тарифом.
- Вы не зависите от провайдера VPN: его аптайма, условий, цены, других ограничений. Не делите канал с другими пользователями.
- Полная кастомизация — это ваш сервер, вы решаете, какие функции вам нужны и в каком виде.
- Генерирует готовые конфиги для клиентов: Clash Verge / FlClash / Amnezia.

```mermaid
flowchart LR
    A[Ваше устройство\n+ VPN-клиент\nClash Verge / FlClash / Amnezia] -->|VLESS + REALITY\nзамаскированный TLS| B[Ваш VPS\nXray-сервер]
    B -->|напрямую\nесли WARP выключен| D[Внешний сайт\nто, что вы открываете]
    B -->|через Cloudflare WARP\nесли включён| C[Cloudflare WARP\nсайт видит IP Cloudflare]
    C --> D
```

Конечная цель — внешний сайт. Сайт видит IP вашего VPS (напрямую) или IP Cloudflare (через WARP).

> В моих планах — мультиплатформенный клиент с простым интерфейсом, чтобы развёртывание и управление были ещё проще. Полный список планов — в [docs/PLANNED.md](docs/PLANNED.md).

<details>
  <summary>Подробности для технарей</summary>

  Реальный стек: Ansible-роль `roles/xray_vpn/`, шаблоны Jinja2,
  Docker-образ `teddysun/xray:26.6.27`, персистентное состояние
  `/root/xray-config/reality-state.json`. Транспорт — VLESS + REALITY
  (модифицированный TLS 1.3, X25519). Опционально — исходящий туннель
  через Cloudflare WARP.

</details>

## Преимущества подхода

Xray VLESS + REALITY не требует своего домена и TLS-сертификата. Сервер маскируется под чужой легитимный сайт (`reality_camouflage_domain`, по умолчанию `dl.google.com`). Это снимает главный барьер для самостоятельной настройки VPN: не нужно покупать домен, получать и продлевать сертификат, настраивать DNS.

Ядро сервера — [Xray-core](https://github.com/XTLS/Xray-core). По умолчанию устанавливается нативно как `/usr/local/xray/xray` под управлением systemd (вариант `xray_runtime: native` в `config/settings.yml` — наименьший footprint, рекомендуемый). Доступен также вариант `docker` (легаси-путь через Docker Engine). Стек: VLESS + REALITY.

От вас нужно три вещи: 
- купить VPS (Ubuntu 20.04+ или Debian 11+) — могу подсказать проверенных провайдеров, буду признателен за регистрацию по моей реферальной ссылке
- скачать файлы проекта 
- запустить клиент или playbook — команды в разделе [«Быстрый старт»](#быстрый-старт) выше. 

> Получить файлы можно так: кнопка **Code → Download ZIP** на странице репозитория, либо архив исходников в разделе **Releases** (справа). Дальше клиент развернёт Xray на VPS, сгенерирует клиентские конфиги и скачает их к вам. В удалённом режиме окружение для Ansible создаётся прямо на сервере — локально ничего ставить не нужно. Знание Ansible, SSH или Xray не требуется. НО потребуется базовое умение пользоваться командной строкой для запуска клиента с параметрами.

WARP outbound через Cloudflare включается одной строкой (`warp_enabled: true` в `config/settings.yml`). С ним сайты видят IP Cloudflare вместо IP вашего VPS.

Перед оплатой VPS на длительный срок проверьте его через [`carrox-vps-check`](https://github.com/AiCarrox/carrox-vps-check) или похожий инструмент. Подробности — в [`docs/TEST-VPS.md`](docs/TEST-VPS.md).

## Где запускается

Пути запуска и требования по платформам — в «Быстром старте» выше.

## Требования

**VPS:** свежий Ubuntu 20.04+ или Debian 11+, root или sudo, публичный IP.

**Локальная машина:**

- Python 3.12+ для основного клиента `xrayvpn` (установка/запуск — через `uv`, см. [`python-client/README.md`](python-client/README.md)); SSH-доступ к VPS по ключу или паролю (используется встроенный `paramiko` — `sshpass` не нужен).
- Для альтернативных shell-клиентов: Linux/WSL с `apt`; на Windows — WSL2 с Ubuntu/Debian.

Обёртка сама доустановит Python 3, Ansible и `sshpass`, если их нет. На Windows нужен только WSL.

## Конфигурация

Два способа:

- **CLI-параметры** — `--pkey` или `--pass` (взаимоисключающие). Если ни один не задан — пароль спросит скрыто.
- **Inventory-файл** — `inventory.yml` + `--use-inventory` (`-UseInventory` в PowerShell). Shell-клиенты умеют и произвольный путь: `--inventory PATH` (`-Inventory <path>`). Подробности режимов — в [`docs/SETUP.md`](docs/SETUP.md), раздел «CLI-флаги `xrayvpn deploy`».

Для режима `--use-inventory` нужен файл `inventory.yml` в корне проекта. В репозитории лежит шаблон `inventory.yml.example` — скопируйте его и заполните своими данными:

```bash
cp inventory.yml.example inventory.yml
```

Windows PowerShell — аналог команды:

```powershell
Copy-Item inventory.yml.example inventory.yml
```

Заполните `ansible_host`, `ansible_user`, `ansible_port` и один из двух: `ansible_ssh_private_key_file` или `ansible_ssh_pass`. Файл `inventory.yml` в `.gitignore` — личные данные в git не уйдут.

CLI-режим (`-H` без `--use-inventory`) файл `inventory.yml` не использует — скрипт сам соберёт нужный inventory во временной папке на время запуска.

Это — способы передать параметры подключения. Остальная конфигурация (число клиентов, WARP, порт, домен маскировки) задаётся в `config/settings.yml` — подробнее в [`docs/SETUP.md`](docs/SETUP.md), раздел «Файлы конфигурации».

## Структура репозитория

- `python-client/` — основной клиент (Python, CLI `xrayvpn`): деплой всегда на VPS; ansible
  выполняется на сервере (default) или на вашей машине (`--execution local`).
- `shell-clients/` — альтернативные shell-клиенты: Bash и PowerShell (поддерживаются, но не развиваются).
- `scripts/` — инструменты разработчика: настройка тестового окружения и локальные тесты.
- `config/`, `roles/`, `deploy.yml` — Ansible-проект (конфигурация, роль, точка входа playbook).

## Клиенты

Я пользуюсь Clash Verge (Windows) и FlClash (Android). Amnezia работает, но из-за нестабильности рекомендую Mihomo-клиенты. Таблица про то, что я проверил сам, а что нет — [`docs/CLIENT-STATUS.md`](docs/CLIENT-STATUS.md).

## Подробная документация

- [`docs/SETUP.md`](docs/SETUP.md) — настройка, переменные `config/settings.yml`, WARP, проверка после развёртывания.
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — что делать, когда VPN перестал работать.
- [`docs/ROTATION.md`](docs/ROTATION.md) — смена ключей и UUID клиентов.
- [`docs/TEST-VPS.md`](docs/TEST-VPS.md) — проверка VPS перед оплатой.
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — термины проекта.
- [`docs/CLIENT-STATUS.md`](docs/CLIENT-STATUS.md) — статус клиентов.
- [`docs/PLANNED.md`](docs/PLANNED.md) — что запланировано дальше.
- [`docs/RELEASE.md`](docs/RELEASE.md) — релизная политика и статусы релизов.
- [`CHANGELOG.md`](CHANGELOG.md) — что менялось по версиям.

## Лицензия

AGPL-3.0 с дополнительным ограничением коммерческого использования.

Свободно для личного использования и некоммерческого распространения. Коммерческое использование — только с моего письменного разрешения: **tim.korelov@yandex.com**.

Полный текст — в [`LICENSE`](LICENSE) (English). Краткое описание на русском — в [`LICENSE.ru.md`](LICENSE.ru.md).

## Автор и контакты

Tim Korelov — https://korelov.dev

Почта: **tim.korelov@yandex.com**
Telegram: **@timkore** (рабочий) — по вопросам этого проекта, с предложениями поработать вместе, приглашениями и т. п.
