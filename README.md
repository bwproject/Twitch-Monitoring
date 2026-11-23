# Twitch Monitoring — ProjectBW

Telegram-бот и сервис мониторинга Twitch-трансляций с отдельным Twitch Chat Bot и WebApp-панелью.

## Требования

- Python 3.12 или новее (в том числе Python 3.14)
- Telegram Bot Token
- Twitch Client ID и Client Secret
- Отдельные OAuth-данные Twitch Chat Bot, если используется чат-бот

## Установка

1. Скопируйте `.env.example` в файл `.env` (или задайте те же переменные в панели Pelican).
2. Заполните в `.env` значения `TELEGRAM_TOKEN`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, а для Twitch Chat Bot также `TWITCH_BOT_NICK`, `TWITCH_BOT_ID` и `TWITCH_OAUTH`.
3. Установите зависимости:

```bash
python -m pip install -r requirements.txt
```

## Запуск Pelican / Pterodactyl

Рабочая точка входа остаётся совместимой с текущим запуском:

```bash
python main.py
```

В настройках сервера укажите файл зависимостей `requirements.txt`. Не используйте `PY_PACKAGES` для повторной установки тех же пакетов.

## Безопасность

- Все секреты Twitch и Telegram читаются из переменных окружения; локально их можно хранить в корневом файле `.env`.
- Файл `.env` исключён из Git. В репозитории хранится только безопасный шаблон `.env.example`.
- В Pelican добавьте те же переменные в настройки Environment сервера; сам файл `.env` в GitHub не загружается.
- Если токен или секрет когда-либо попал в публичный репозиторий, отзовите его и выпустите новый. Удаление файла не удаляет секрет из истории Git.

## Компоненты

- `main.py` — запуск приложения.
- `twitch_monitor.py`, `twitch_api.py` — мониторинг и Twitch Helix API.
- `admin.py`, `command.py` — Telegram-обработчики.
- `chat.py`, `command_loader.py` — Twitch Chat Bot.
- `webapp.py`, `twitch/index.html` — API и интерфейс WebApp.
- JSON-файлы — конфигурация стримеров, кэш и пользовательские команды.

## Pelican

Для Python 3.14 нельзя оставлять старую связку `aiogram==3.3.0` / `pydantic==2.5.3`: она приводит к сборке несовместимого `pydantic-core`. В этом репозитории используется актуальная линейка aiogram 3.x с совместимым Pydantic.
