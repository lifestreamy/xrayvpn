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

## CHANGELOG
- Ведётся по выпущенным версиям; записи вносит релизный коммит; формат — Added / Changed / Fixed /
  Removed.