# Twitch Monitoring — ProjectBW

Telegram-бот и сервис мониторинга Twitch-трансляций с отдельным Twitch Chat Bot и WebApp-панелью.

## Требования

- Python 3.12 или новее (в том числе Python 3.14)
- Telegram Bot Token
- Twitch Client ID и Client Secret
- Отдельные OAuth-данные Twitch Chat Bot, если используется чат-бот

## Установка

1. Скопируйте `.env.example` в `.env`.
2. Заполните переменные окружения своими токенами.
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

- Не добавляйте `.env`, OAuth-токены, Telegram-токены или Twitch Client Secret в Git.
- Используйте переменные окружения панели Pelican либо локальный `.env`.
- Если токен или секрет когда-либо попал в публичный репозиторий, отзовите его и выпустите новый. Удаление файла не удаляет секрет из истории Git.

## Компоненты

- `main.py` — запуск приложения.
- `twitch.py`, `twitch_api.py` — мониторинг и Twitch Helix API.
- `admin.py`, `command.py` — Telegram-обработчики.
- `chat.py`, `command_loader.py` — Twitch Chat Bot.
- `webapp.py`, `twitch/index.html` — API и интерфейс WebApp.
- JSON-файлы — конфигурация стримеров, кэш и пользовательские команды.

## Pelican

Для Python 3.14 нельзя оставлять старую связку `aiogram==3.3.0` / `pydantic==2.5.3`: она приводит к сборке несовместимого `pydantic-core`. В этом репозитории используется актуальная линейка aiogram 3.x с совместимым Pydantic.
