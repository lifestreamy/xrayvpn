# Релизная политика

Общие правила выпуска. Процесс короткий.

## Версии
- Формат `vX.Y.Z`; префикс `v` обязателен.
- В фазе 0.x: минор — существенные изменения (возможны ломающие), патч — исправления и небольшие
  правки.
- Тег — единственный факт выпущенного релиза.

## Статусы
- Обычный тег `vX.Y.Z` — релиз.
- `vX.Y.Z_experimental` — предварительный выпуск для полевой проверки: GitHub pre-release, канал
  Latest не занимает.
- Новые релизы выходят сразу обычным тегом; ошибки исправляются следующим патчем.

## Выпуск
- Релиз выходит после проверок: автотесты, сборки под все платформы и ручная проверка на живом
  сервере.
- Код без релиза в CHANGELOG не попадает.

## Где публикуется релиз
- GitHub Releases — сборки под все платформы, wheel/sdist и контрольные суммы.
- PyPI — `pip install xrayvpn`.
- apt-репозиторий — `apt install xrayvpn`; кодовые имена noble (Ubuntu 24.04), bookworm (Debian 12).
- Homebrew — формула в tap.
- AUR — `xrayvpn-bin`.
- winget — манифест.

Устройство публикации по каналам и ремонт канала — [`docs/dev/publishing/`](publishing/README.md).

Подключение apt-репозитория (отпечаток ключа — `60DA D207 F0BE 147C 5830 D3D8 1BD4 9EC3 0480 57D3`):

```bash
sudo curl -fsSL -o /usr/share/keyrings/xrayvpn-archive-keyring.gpg \
  https://lifestreamy.github.io/xrayvpn/apt/xrayvpn-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/xrayvpn-archive-keyring.gpg] https://lifestreamy.github.io/xrayvpn/apt/ $(. /etc/os-release; echo $VERSION_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/xrayvpn.list
sudo apt update && sudo apt install xrayvpn
```

Homebrew (macOS, Apple Silicon):

```bash
brew install lifestreamy/tap/xrayvpn
```

## Бейджи
- Бейджи в README обновляются по событиям (пайплайн `badges.yml`): публикация релиза и успешное
  завершение публикаций каналов (pypi, brew, apt). Версии берутся из самих каналов (могут
  различаться), `?v=` сдвигается у изменившегося бейджа, обновления уходят бот-коммитом в main.
- winget-бейдж показывает версию только при `CHANNEL_WINGET_LIVE=true` (переменная репозитория),
  иначе — «скоро»/«soon»; после включения — ручной прогон пайплайна.
- Ремонт — ручной запуск без входов (вкладка Actions).

## CHANGELOG
- Ведётся по выпущенным версиям; записи вносит релизный коммит; формат — Added / Changed / Fixed /
  Removed.

## Релиз-ноты (GitHub Release)
Тело релиза — пара RU/EN в одном тексте:
- иконка по центру; при наличии скриншотов — таблица с `align="center"`; затем `---` и заголовок
  `## vX.Y.Z — YYYY-MM-DD`;
- у каждого языка: видимый жирный лид (одна строка) и сворачиваемый блок
  `<details><summary>:us: English summary</summary>` / `<summary>:ru: Описание на русском</summary>`;
  порядок EN → RU, между блоками — `---`;
- внутри — короткие пункты Added / Changed / Fixed / Removed без деталей реализации; полные
  формулировки — в `CHANGELOG.md`;
- служебные пометки (например, про невыпущенный релиз) — `<sub>…</sub>` в конце своего блока;
- внизу — `<sub> Pre-built by the release-binaries workflow from tag vX.Y.Z. See SHA256SUMS.txt
  and latest.json. </sub>`.