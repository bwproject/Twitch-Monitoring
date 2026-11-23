# Twitch Monitoring — ProjectBW

Сервис мониторинга Twitch с отдельными Twitch Chat, Telegram, Discord и Lolka ботами и веб-панелью.

## Запуск Pelican / Pterodactyl

Команда запуска не меняется: python main.py. В настройках Pelican укажите requirements.txt и AUTO_UPDATE=1.

## Структура проекта

- main.py — единая точка запуска.
- paths.py — централизованные пути и миграция старых JSON-файлов.
- twitch/ — Twitch Helix API, мониторинг, Twitch Chat Bot и его команды.
- telegram_bot/ — Telegram polling и обработчики.
- discord_bot/ — отдельный Discord-клиент уведомлений.
- lolka_bot/ — отдельный Lolka-клиент уведомлений.
- web/ — FastAPI, авторизация и HTML-шаблоны.
- data/ — постоянные данные, отделённые от исходного кода:
  - data/twitch/streamers.json — список стримеров.
  - data/twitch/streamers/<login>.json — индивидуальные настройки и шаблоны.
  - data/twitch/cache.json — Twitch cache.
  - data/twitch/chat/ — конфигурация Twitch Chat Bot и команды.
  - data/admin/ — пользователи, сессия и интеграционные токены.
  - data/applications.json — заявки с главной страницы.

Корневые admin.py, chat.py, command.py, command_loader.py, twitch_api.py, twitch_monitor.py, webapp.py и web_auth.py оставлены как тонкие compatibility-imports. Новая разработка ведётся в пакетах.

## Данные и миграция

Изменяемые данные хранятся в BOT_DATA_DIR (по умолчанию data/). При первом запуске paths.py копирует старые корневые JSON-файлы в новые каталоги, только если целевой файл ещё не существует. Существующие файлы в data/ не перезаписываются. Старые корневые JSON-файлы временно оставлены как источники миграции; приложение больше не записывает в них новые изменения.

Перед первым обновлением на сервере с AUTO_UPDATE=1 сделайте резервную копию корневых streamers.json, <login>.json, global_commands.json, *_commands.json, chat_config.json и twitch_cache.json, если вы меняли их вручную или через старую версию панели. Стартовый скрипт Pelican выполняет git reset --hard и сбрасывает локальные изменения отслеживаемых файлов до запуска приложения.

Для другого расположения данных задайте BOT_DATA_DIR абсолютным путём.

## Независимые боты

Каждая платформа запускается независимо:
- пустой TELEGRAM_TOKEN или ошибка авторизации Telegram не мешают Twitch мониторингу, Discord, Lolka и веб-панели;
- пустой DISCORD_BOT_TOKEN или ошибка Discord не мешают остальным компонентам;
- пустой LOLKA_BOT_TOKEN или ошибка Lolka не мешают остальным компонентам;
- Twitch Chat Bot также пропускает отсутствие обязательных Twitch Chat credentials.

Для уведомлений укажите ID каналов соответствующих платформ в настройках стримера. Telegram chat_id можно оставить пустым, если запись нужна только для Discord или Lolka.

## Настройки

Секреты задаются через .env или Environment в Pelican. Админ-панель может сохранять токены в data/admin/integrations.json. Не публикуйте .env, токены и runtime-каталог data/.

## Веб-интерфейс

- / — главная;
- /apply — подача заявки;
- /admin — браузерная админка;
- /twitch/ — Telegram Mini App для управления Twitch-уведомлениями.

API работает на WEB_HOST / WEB_PORT (по умолчанию 0.0.0.0:1047).

## Зависимости

Поддерживается Python 3.12+ (включая Python 3.14). Установка: python -m pip install -r requirements.txt.
