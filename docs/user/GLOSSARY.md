# Глоссарий

Термины проекта. Если встретили незнакомое слово в документации — ищите его здесь.

## Runtime selector (`xray_runtime`)

Параметр в `config/settings.yml` (`xray_runtime: native | docker`), выбирает способ запуска Xray-сервера. По умолчанию `native` — наименьший footprint. `docker` — легаси-путь через Docker Engine.

## `xray_cli_command`

Команда для вызова Xray CLI и keygen. Зависит от рантайма: для `native` это `/usr/local/bin/xray`, для `docker` — `docker run --rm <image>`. Роль задаёт её сама в `roles/xray_vpn/tasks/runtime_setup.yml` — в задачах использовать её, а не прямой `docker run`.

## `xray_container_image`

Образ контейнера для `docker`. Роль вычисляет его сама (пин или сборка из репозитория и версии); как задать и какой сейчас пин — таблица переменных в `docs/user/SETUP.md`.

## Ротация

Замена учётных данных на новые. После ротации старые конфиги клиентов перестают подключаться, нужно раздать новые. Подробности — в `docs/user/ROTATION.md`.

## Переключатель `xray_reality_rotate`

Параметр в `config/settings.yml` или флаг `-e xray_reality_rotate=true` в командной строке. Заставляет Ansible-роль пересоздать ключи, short ID и UUID клиентов.

## REALITY

Технология стелс-VPN в Xray — модифицированный TLS 1.3. Маскируется под чужой легитимный сайт через `reality_camouflage_domain` — например, `dl.google.com`. Не требует своего домена или TLS-сертификата.

## VLESS

Протокол туннелирования в Xray без собственного шифрования. За шифрование и аутентификацию отвечает security-слой — в этой настройке REALITY (модифицированный TLS 1.3 с обменом ключей X25519).

## Private key / Public key

Пара ключей X25519. REALITY использует её для аутентификации сервера: private key остаётся на сервере в `/root/xray-config/reality-state.json`, public key попадает в клиентские конфиги. Шифрование сессии при этом даёт TLS 1.3, а не эта пара.

## Short ID

Короткий идентификатор «правильного клиента» при рукопожатии. После ротации меняется. Состоит из 8 hex-символов.

## UUID клиента

Уникальный идентификатор, который VPN-клиент шлёт в каждом пакете. После ротации меняется. На сервере хранится в `reality-state.json` как массив.

## `num_clients`

Сколько клиентских конфигов сгенерировать. Увеличение добавляет новые UUID в `reality-state.json`. Уменьшение не удаляет существующие UUID, только сокращает число экспортируемых конфигов.

## WARP

Дополнительный исходящий туннель через Cloudflare. Скрывает IP вашего VPS от посещаемых сайтов — вместо IP VPS они видят IP Cloudflare WARP. Опционален. Включается в `config/settings.yml` через `warp_enabled: true`.

Учётные данные WARP — `wgcf-account.toml` и `wgcf-profile.conf` в `/root/xray-config/`. Они ротируются отдельно от REALITY (через удаление файлов и повторный запуск playbook).

## `reality_camouflage_domain`

SNI легитимного сайта, под который маскируется REALITY. По умолчанию `dl.google.com`. Это публичный параметр, в ротации не нуждается.

## `reality-state.json`

Файл `/root/xray-config/reality-state.json` (режим `0600`). Хранит `private_key`, `public_key`, `short_id` и `client_uuids`. Состояние между прогонами playbook. Перед ротацией создаётся резервная копия: `reality-state.json.bak-YYYY-MM-DD-HH:MM:SS`.

## `<VPS_IP>`

Плейсхолдер. IP-адрес вашего VPS. Заменяйте перед запуском команд в этом руководстве.

## Ansible / inventory

Ansible — инструмент для управления конфигурациями. Роль проекта (`roles/xray_vpn/`) применяется на VPS через `deploy.yml`. Inventory-файл (`inventory.yml`) описывает подключение к хосту. Синтаксис — стандартный Ansible inventory.

## `xray_manage_ufw`

Параметр в `config/settings.yml` (по умолчанию `true`). Роль не устанавливает `ufw`; если `ufw` уже есть на сервере — добавляет allow-правило для порта `xray_port`/tcp (не выполняет `ufw enable`, чужие правила не трогает).

---

Все параметры `config/settings.yml` описаны в `docs/user/SETUP.md`.
