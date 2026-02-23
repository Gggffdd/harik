
## 📄 **config.py**

```python
# config.py
"""
Конфигурация бота AirRep
"""

import os
from typing import Dict, Any

# Telegram Bot
BOT_TOKEN = "8544219275:AAHoTYhzCuHIv6QaJEe0gu_6SR31A1UD0AU"  # Замените на свой
ADMIN_ID = 896706118  # Ваш Telegram ID

# WebApp
WEBAPP_URL = "https://your-domain.com/webapp.html"  # URL для мини-приложения
WEBAPP_DEBUG = True  # Режим отладки

# База данных
DATABASE_PATH = "airrep.db"

# Настройки репутации
REP_COOLDOWN = 60  # Секунд между +реп
MAX_REP_PER_DAY = 20  # Максимум репы в день

# Типы шаров (цвет, минимальная репа, максимальная репа)
BALLOON_TYPES: Dict[str, Dict[str, Any]] = {
    "owner": {
        "name": "👑 Владелец",
        "color": "#FFD700",
        "min_rep": 1000,
        "max_rep": float('inf'),
        "size": 2.0,
        "glow": True
    },
    "top_moderator": {
        "name": "⚜️ Топ-модератор",
        "color": "#C0C0C0",
        "min_rep": 500,
        "max_rep": 999,
        "size": 1.8,
        "glow": True
    },
    "moderator": {
        "name": "🏆 Модератор",
        "color": "#CD7F32",
        "min_rep": 300,
        "max_rep": 499,
        "size": 1.6,
        "glow": False
    },
    "veteran": {
        "name": "🔵 Ветеран",
        "color": "#4169E1",
        "min_rep": 150,
        "max_rep": 299,
        "size": 1.4,
        "glow": False
    },
    "active": {
        "name": "🟢 Активный",
        "color": "#32CD32",
        "min_rep": 50,
        "max_rep": 149,
        "size": 1.2,
        "glow": False
    },
    "user": {
        "name": "🟠 Пользователь",
        "color": "#FFA500",
        "min_rep": 10,
        "max_rep": 49,
        "size": 1.0,
        "glow": False
    },
    "newbie": {
        "name": "🩵 Новичок",
        "color": "#87CEEB",
        "min_rep": 0,
        "max_rep": 9,
        "size": 0.8,
        "glow": False
    },
    "warning": {
        "name": "⚠️ Предупрежден",
        "color": "#FF4444",
        "min_rep": -10,
        "max_rep": -1,
        "size": 0.7,
        "glow": False
    },
    "banned": {
        "name": "💔 Забанен",
        "color": "#000000",
        "min_rep": float('-inf'),
        "max_rep": -11,
        "size": 0.5,
        "glow": False,
        "popped": True
    }
}

# Цвета для премиум эмодзи (для Telegram)
EMOJI_IDS = {
    "owner": "5904630315946611415",      # 👑
    "moderator": "5778423822940114949",   # ⚜️
    "veteran": "5877485980901971030",     # 🔵
    "active": "5775937998948404844",      # 🟢
    "user": "5879813604068298387",        # 🟠
    "newbie": "5967412305338568701",      # 🩵
    "warning": "5877485980901971030",      # ⚠️
    "banned": "5775937998948404844"        # 💔
}

# Логирование
LOG_LEVEL = "DEBUG"
LOG_FILE = "airrep.log"

# Проверка конфига
if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("⚠️ ВНИМАНИЕ: Укажите свой BOT_TOKEN в config.py!")
    print("Получить токен: @BotFather в Telegram")
