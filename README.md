# 🎮 Twitch Monitoring

<p align="center">
<b>Telegram бот для мониторинга Twitch-стримеров</b>
</p>

---

## 📌 О проекте

**Twitch-Monitoring** — автоматический мониторинг Twitch-каналов с отправкой уведомлений в Telegram.

Бот отслеживает состояние стримеров, получает данные через Twitch API и сообщает о начале трансляций.

---

## ✨ Возможности

- 📺 Проверка онлайн/офлайн статуса Twitch каналов
- 🔔 Уведомления о начале стрима
- 🎮 Получение названия трансляции и категории
- 👥 Поддержка нескольких стримеров
- ⚙️ Настройка сообщений уведомлений
- 🗂 Индивидуальные настройки для каждого канала
- 🤖 Управление через Telegram команды

---

## 🛠 Технологии

- 🐍 Python
- 🤖 Aiogram
- 🎮 Twitch Helix API
- ⚡ AsyncIO
- 🔐 dotenv

---

## ⚙️ Установка

```bash
git clone https://github.com/bwproject/Twitch-Monitoring.git
cd Twitch-Monitoring
pip install -r requirements.txt
```

Создайте `.env`:

```env
TELEGRAM_TOKEN=your_token
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_secret
```

Запуск:

```bash
python bot.py
```

---

## 📁 Структура

```
Twitch-Monitoring/
├── bot.py          # Запуск Telegram бота
├── twitch.py       # Мониторинг стримеров
├── twitch_api.py   # Работа с Twitch API
├── admin.py        # Администрирование
├── streamers.json  # Список каналов
└── requirements.txt
```

---

## 🔧 Команды

| Команда | Описание |
|---|---|
| `/start` | Запуск бота |
| `/streamerslist` | Список стримеров |
| `/edit` | Настройка сообщений |
| `/test` | Проверка уведомлений |
| `/notify` | Настройки уведомлений |

---

## 🚧 Roadmap

- ✅ Twitch мониторинг
- ✅ Telegram уведомления
- ✅ Настройка сообщений
- 🔄 Web-панель управления
- 🔄 Docker deployment
- 🔄 Расширенная статистика

---

## 🤝 Поддержка

Нашли ошибку или есть идея?

Создайте Issue или Pull Request.

---

<p align="center">
❤️ BW Project
</p>
