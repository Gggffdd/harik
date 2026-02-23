#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🎈 AirRep - Воздушная Репутация
================================
Единый файл бота с 3D визуализацией для Telegram

GitHub: https://github.com/ваш_username/airrep
WebApp: https://ваш_username.github.io/airrep/

Автор: Ваше имя
Лицензия: MIT
"""

import logging
import sqlite3
import asyncio
import signal
import sys
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps
from enum import Enum

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

class Config:
    """Настройки бота"""
    
    # Telegram Bot
    BOT_TOKEN = "8544219275:AAHoTYhzCuHIv6QaJEe0gu_6SR31A1UD0AU"
    ADMIN_ID = 896706118
    
    # GitHub Pages (измените на свои)
    GITHUB_USERNAME = "Gggffdd"
    REPO_NAME = "airrep"
    
    # URL для WebApp
    WEBAPP_URL = f"https://{GITHUB_USERNAME}.github.io/{REPO_NAME}/"
    
    # База данных
    DATABASE_PATH = "airrep.db"
    
    # Настройки репутации
    REP_COOLDOWN = 60  # секунд
    MAX_REP_PER_DAY = 20
    
    # Логирование
    LOG_LEVEL = "DEBUG"
    LOG_FILE = "airrep.log"
    
    # Типы шаров
    BALLOON_TYPES = {
        "owner": {
            "name": "👑 Владелец",
            "color": "#FFD700",
            "min_rep": 1000,
            "max_rep": float('inf'),
            "size": 2.0,
            "height": 25,
            "glow": True,
            "emoji": "👑"
        },
        "top_moderator": {
            "name": "⚜️ Топ-модератор",
            "color": "#C0C0C0",
            "min_rep": 500,
            "max_rep": 999,
            "size": 1.8,
            "height": 20,
            "glow": True,
            "emoji": "⚜️"
        },
        "moderator": {
            "name": "🏆 Модератор",
            "color": "#CD7F32",
            "min_rep": 300,
            "max_rep": 499,
            "size": 1.6,
            "height": 17,
            "glow": False,
            "emoji": "🏆"
        },
        "veteran": {
            "name": "🔵 Ветеран",
            "color": "#4169E1",
            "min_rep": 150,
            "max_rep": 299,
            "size": 1.4,
            "height": 14,
            "glow": False,
            "emoji": "🔵"
        },
        "active": {
            "name": "🟢 Активный",
            "color": "#32CD32",
            "min_rep": 50,
            "max_rep": 149,
            "size": 1.2,
            "height": 11,
            "glow": False,
            "emoji": "🟢"
        },
        "user": {
            "name": "🟠 Пользователь",
            "color": "#FFA500",
            "min_rep": 10,
            "max_rep": 49,
            "size": 1.0,
            "height": 8,
            "glow": False,
            "emoji": "🟠"
        },
        "newbie": {
            "name": "🩵 Новичок",
            "color": "#87CEEB",
            "min_rep": 0,
            "max_rep": 9,
            "size": 0.8,
            "height": 5,
            "glow": False,
            "emoji": "🩵"
        },
        "warning": {
            "name": "⚠️ Предупрежден",
            "color": "#FF4444",
            "min_rep": -10,
            "max_rep": -1,
            "size": 0.7,
            "height": 2,
            "glow": False,
            "emoji": "⚠️"
        },
        "banned": {
            "name": "💔 Забанен",
            "color": "#000000",
            "min_rep": float('-inf'),
            "max_rep": -11,
            "size": 0.5,
            "height": 0,
            "glow": False,
            "emoji": "💔",
            "popped": True
        }
    }
    
    # Достижения
    ACHIEVEMENTS = {
        "first_rep": {"name": "🎈 Первый шаг", "desc": "Получить первую репутацию"},
        "rep_50": {"name": "⭐ 50 репутации", "desc": "Достичь 50 очков"},
        "rep_100": {"name": "🌟 100 репутации", "desc": "Достичь 100 очков"},
        "rep_500": {"name": "💫 500 репутации", "desc": "Достичь 500 очков"},
        "rep_1000": {"name": "👑 1000 репутации", "desc": "Достичь 1000 очков"},
        "first_report": {"name": "📝 Первый репорт", "desc": "Отправить первый репорт"},
        "reporter_10": {"name": "🛡️ 10 репортов", "desc": "Подтвердить 10 репортов"},
        "giver_100": {"name": "🤝 100 +реп", "desc": "Поставить 100 +реп"},
    }


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

class Database:
    """Работа с SQLite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        with self.get_connection() as conn:
            # Пользователи
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    rep_positive INTEGER DEFAULT 0,
                    rep_negative INTEGER DEFAULT 0,
                    rep_given_positive INTEGER DEFAULT 0,
                    rep_given_negative INTEGER DEFAULT 0,
                    reports_submitted INTEGER DEFAULT 0,
                    reports_confirmed INTEGER DEFAULT 0,
                    join_date TEXT,
                    last_active TEXT,
                    balloon_type TEXT DEFAULT 'newbie',
                    balloon_name TEXT,
                    balloon_desc TEXT,
                    balloon_color TEXT,
                    balloon_size REAL DEFAULT 1.0,
                    custom_data TEXT
                )
            ''')
            
            # Связи
            conn.execute('''
                CREATE TABLE IF NOT EXISTS connections (
                    user1_id INTEGER,
                    user2_id INTEGER,
                    strength INTEGER DEFAULT 1,
                    last_update TEXT,
                    PRIMARY KEY (user1_id, user2_id)
                )
            ''')
            
            # Репорты
            conn.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reporter_id INTEGER,
                    reported_id INTEGER,
                    reason TEXT,
                    message_id INTEGER,
                    chat_id INTEGER,
                    chat_username TEXT,
                    date TEXT,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            # Достижения
            conn.execute('''
                CREATE TABLE IF NOT EXISTS achievements (
                    user_id INTEGER,
                    achievement_id TEXT,
                    achieved_date TEXT,
                    PRIMARY KEY (user_id, achievement_id)
                )
            ''')
            
            # История репутации
            conn.execute('''
                CREATE TABLE IF NOT EXISTS rep_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_id INTEGER,
                    to_id INTEGER,
                    value INTEGER,
                    date TEXT
                )
            ''')
            
            conn.commit()
    
    # === Пользователи ===
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", 
                (user_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def create_user(self, user_id: int, username: str = "", first_name: str = "") -> Dict:
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO users (
                    user_id, username, first_name, join_date, last_active, balloon_type
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, now, now, 'newbie'))
            conn.commit()
            return self.get_user(user_id)
    
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = "") -> Dict:
        user = self.get_user(user_id)
        if not user:
            user = self.create_user(user_id, username, first_name)
        return user
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        values.append(user_id)
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?",
                values
            )
            conn.commit()
            return True
    
    def update_last_active(self, user_id: int):
        self.update_user(user_id, last_active=datetime.now().isoformat())
    
    def get_all_users(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY rep_positive DESC").fetchall()
            return [dict(row) for row in rows]
    
    def get_top_users(self, limit: int = 10) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT *, (rep_positive - rep_negative) as total_rep 
                FROM users 
                WHERE rep_positive - rep_negative > 0
                ORDER BY total_rep DESC 
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    # === Репутация ===
    
    def add_reputation(self, from_id: int, to_id: int, value: int) -> bool:
        field_pos = "rep_positive" if value > 0 else "rep_negative"
        field_given = "rep_given_positive" if value > 0 else "rep_given_negative"
        
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET {field_pos} = {field_pos} + 1 WHERE user_id = ?",
                (to_id,)
            )
            conn.execute(
                f"UPDATE users SET {field_given} = {field_given} + 1 WHERE user_id = ?",
                (from_id,)
            )
            conn.execute('''
                INSERT INTO rep_history (from_id, to_id, value, date)
                VALUES (?, ?, ?, ?)
            ''', (from_id, to_id, value, datetime.now().isoformat()))
            conn.commit()
            self.update_balloon_type(to_id)
            return True
    
    def get_reputation(self, user_id: int) -> int:
        user = self.get_user(user_id)
        if not user:
            return 0
        return user['rep_positive'] - user['rep_negative']
    
    def update_balloon_type(self, user_id: int):
        rep = self.get_reputation(user_id)
        for type_name, type_config in Config.BALLOON_TYPES.items():
            if type_config['min_rep'] <= rep <= type_config['max_rep']:
                self.update_user(
                    user_id, 
                    balloon_type=type_name,
                    balloon_color=type_config.get('color'),
                    balloon_size=type_config.get('size', 1.0)
                )
                break
    
    # === Связи ===
    
    def add_connection(self, user1_id: int, user2_id: int):
        with self.get_connection() as conn:
            existing = conn.execute(
                "SELECT * FROM connections WHERE user1_id = ? AND user2_id = ?",
                (user1_id, user2_id)
            ).fetchone()
            
            if existing:
                conn.execute('''
                    UPDATE connections 
                    SET strength = strength + 1, last_update = ?
                    WHERE user1_id = ? AND user2_id = ?
                ''', (datetime.now().isoformat(), user1_id, user2_id))
            else:
                conn.execute('''
                    INSERT INTO connections (user1_id, user2_id, strength, last_update)
                    VALUES (?, ?, ?, ?)
                ''', (user1_id, user2_id, 1, datetime.now().isoformat()))
            
            conn.commit()
    
    def get_connections(self, user_id: int, limit: int = 20) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT u.*, c.strength 
                FROM connections c
                JOIN users u ON u.user_id = c.user2_id
                WHERE c.user1_id = ?
                ORDER BY c.strength DESC
                LIMIT ?
            ''', (user_id, limit)).fetchall()
            return [dict(row) for row in rows]
    
    # === Репорты ===
    
    def add_report(self, reporter_id: int, reported_id: int, reason: str, 
                   message_id: int, chat_id: int, chat_username: str = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO reports 
                (reporter_id, reported_id, reason, message_id, chat_id, chat_username, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (reporter_id, reported_id, reason, message_id, chat_id, 
                  chat_username, datetime.now().isoformat()))
            
            conn.execute('''
                UPDATE users SET reports_submitted = reports_submitted + 1
                WHERE user_id = ?
            ''', (reporter_id,))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_pending_reports(self, limit: int = 10) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM reports 
                WHERE status = 'pending'
                ORDER BY date DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def resolve_report(self, report_id: int, confirmed: bool = True):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE reports SET status = ? WHERE id = ?",
                ('confirmed' if confirmed else 'rejected', report_id)
            )
            if confirmed:
                report = conn.execute(
                    "SELECT reporter_id FROM reports WHERE id = ?", 
                    (report_id,)
                ).fetchone()
                if report:
                    conn.execute('''
                        UPDATE users SET reports_confirmed = reports_confirmed + 1
                        WHERE user_id = ?
                    ''', (report['reporter_id'],))
            conn.commit()
    
    # === Достижения ===
    
    def check_achievements(self, user_id: int) -> List[str]:
        user = self.get_user(user_id)
        if not user:
            return []
        
        rep = user['rep_positive'] - user['rep_negative']
        new = []
        
        achievements = {
            'first_rep': rep >= 1,
            'rep_50': rep >= 50,
            'rep_100': rep >= 100,
            'rep_500': rep >= 500,
            'rep_1000': rep >= 1000,
            'first_report': user['reports_submitted'] >= 1,
            'reporter_10': user['reports_confirmed'] >= 10,
            'giver_100': user['rep_given_positive'] >= 100,
        }
        
        with self.get_connection() as conn:
            for ach_id, achieved in achievements.items():
                if achieved:
                    existing = conn.execute('''
                        SELECT * FROM achievements 
                        WHERE user_id = ? AND achievement_id = ?
                    ''', (user_id, ach_id)).fetchone()
                    
                    if not existing:
                        conn.execute('''
                            INSERT INTO achievements (user_id, achievement_id, achieved_date)
                            VALUES (?, ?, ?)
                        ''', (user_id, ach_id, datetime.now().isoformat()))
                        new.append(ach_id)
            conn.commit()
        
        return new
    
    def get_achievements(self, user_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT achievement_id, achieved_date FROM achievements
                WHERE user_id = ?
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]
    
    # === Статистика ===
    
    def get_stats(self) -> Dict:
        with self.get_connection() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            
            today = datetime.now().date().isoformat()
            active_today = conn.execute('''
                SELECT COUNT(*) FROM users 
                WHERE date(last_active) = date(?)
            ''', (today,)).fetchone()[0]
            
            total_reports = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            
            avg_rep = conn.execute('''
                SELECT AVG(rep_positive - rep_negative) FROM users
            ''').fetchone()[0] or 0
            
            # По типам шаров
            balloon_stats = {}
            rows = conn.execute('''
                SELECT balloon_type, COUNT(*) as count 
                FROM users 
                GROUP BY balloon_type
            ''').fetchall()
            for row in rows:
                balloon_stats[row['balloon_type']] = row['count']
            
            return {
                'total_users': total_users,
                'active_today': active_today,
                'total_reports': total_reports,
                'avg_rep': round(avg_rep, 2),
                'balloon_stats': balloon_stats
            }
    
    # === Экспорт для WebApp ===
    
    def get_balloons_data(self) -> List[Dict]:
        """Данные для 3D визуализации"""
        users = self.get_all_users()
        result = []
        
        for user in users:
            rep = user['rep_positive'] - user['rep_negative']
            balloon_type = user.get('balloon_type', 'newbie')
            type_config = Config.BALLOON_TYPES.get(balloon_type, Config.BALLOON_TYPES['newbie'])
            
            # Случайная позиция (в реальном проекте - сохранять в БД)
            import random
            angle = random.random() * 3.14159 * 2
            radius = 5 + random.random() * 15
            
            result.append({
                'id': user['user_id'],
                'username': user['username'],
                'first_name': user['first_name'],
                'type': balloon_type,
                'rep': rep,
                'color': type_config['color'],
                'size': type_config['size'],
                'height': type_config['height'],
                'emoji': type_config['emoji'],
                'position': {
                    'x': math.cos(angle) * radius,
                    'z': math.sin(angle) * radius
                },
                'achievements': self.get_achievements(user['user_id'])
            })
        
        return result
    
    def get_connections_data(self) -> List[Dict]:
        """Связи для 3D визуализации"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT user1_id, user2_id, strength 
                FROM connections 
                WHERE strength > 2
                ORDER BY strength DESC 
                LIMIT 50
            ''').fetchall()
            return [dict(row) for row in rows]


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

import math

def emoji(emoji_char: str) -> str:
    """Просто возвращает эмодзи (для простоты)"""
    return emoji_char

def admin_only(func):
    """Декоратор для админа"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != Config.ADMIN_ID:
            if update.message:
                await update.message.reply_text(
                    f"⚠️ <b>Эта команда только для администратора.</b>",
                    parse_mode=ParseMode.HTML
                )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def get_user_emoji(user_id: int, db: Database) -> str:
    """Получить эмодзи пользователя"""
    user = db.get_user(user_id)
    if not user:
        return "🎈"
    balloon_type = user.get('balloon_type', 'newbie')
    return Config.BALLOON_TYPES.get(balloon_type, {}).get('emoji', '🎈')


# ============================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================

# Инициализация БД
db = Database(Config.DATABASE_PATH)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, Config.LOG_LEVEL),
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    try:
        user = update.effective_user
        db.get_or_create_user(user.id, user.username or "", user.first_name)
        
        keyboard = [[
            InlineKeyboardButton(
                "🎈 Открыть небо", 
                web_app={"url": Config.WEBAPP_URL}
            )
        ]]
        
        await update.message.reply_text(
            f"🎈 <b>Привет, {user.first_name}!</b>\n\n"
            f"Я бот для визуализации репутации в виде воздушных шаров.\n"
            f"Чем выше репутация - тем выше летит ваш шар!\n\n"
            f"<b>Команды:</b>\n"
            f"• /и [@user] - посмотреть профиль\n"
            f"• /репорт [причина] - пожаловаться (ответом)\n"
            f"• +реп / -реп - изменить репутацию (ответом)\n\n"
            f"👇 Нажмите кнопку чтобы увидеть небо",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        db.update_last_active(user.id)
        logger.info(f"Start от {user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка в start: {e}", exc_info=True)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /и - профиль"""
    try:
        user = update.effective_user
        message = update.message
        
        # Определяем цель
        target_user = None
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
        elif context.args and context.args[0].startswith('@'):
            username = context.args[0][1:].lower()
            all_users = db.get_all_users()
            for u in all_users:
                if u['username'].lower() == username:
                    try:
                        target_user = await context.bot.get_chat(u['user_id'])
                        break
                    except:
                        pass
        
        if not target_user:
            target_user = user
        
        # Данные
        user_data = db.get_or_create_user(
            target_user.id, 
            target_user.username or "", 
            target_user.first_name
        )
        
        rep_total = user_data['rep_positive'] - user_data['rep_negative']
        balloon_emoji = get_user_emoji(target_user.id, db)
        balloon_type = Config.BALLOON_TYPES.get(user_data['balloon_type'], {})
        
        # Достижения
        achievements = db.get_achievements(target_user.id)
        ach_text = ""
        if achievements:
            ach_list = [Config.ACHIEVEMENTS.get(a['achievement_id'], {}).get('name', a['achievement_id']) 
                       for a in achievements[:3]]
            ach_text = f"\n🏅 <b>Достижения:</b> {', '.join(ach_list)}"
        
        text = (
            f"{balloon_emoji} <b>Профиль {target_user.first_name}</b>\n\n"
            f"<b>🆔 ID:</b> <code>{target_user.id}</code>\n"
            f"<b>📝 Username:</b> @{target_user.username or 'нет'}\n"
            f"<b>🎈 Тип шара:</b> {balloon_type.get('name', 'Новичок')}\n"
            f"<b>📅 В чате с:</b> {user_data['join_date'][:10]}\n\n"
            f"<b>⭐ Репутация:</b> {rep_total}\n"
            f"   Получено: +{user_data['rep_positive']} / -{user_data['rep_negative']}\n"
            f"   Оставлено: +{user_data['rep_given_positive']} / -{user_data['rep_given_negative']}\n\n"
            f"<b>🚨 Репорты:</b>\n"
            f"   Подано: {user_data['reports_submitted']}\n"
            f"   Подтверждено: {user_data['reports_confirmed']}{ach_text}"
        )
        
        keyboard = [[
            InlineKeyboardButton(
                "🎈 Найти в небе",
                web_app={"url": f"{Config.WEBAPP_URL}?user={target_user.id}"}
            )
        ]]
        
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        db.update_last_active(user.id)
        
    except Exception as e:
        logger.error(f"Ошибка в profile: {e}", exc_info=True)

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /репорт"""
    try:
        message = update.message
        
        if not message.reply_to_message:
            await message.reply_text(
                "⚠️ <b>Использование:</b> /репорт [причина] (как ответ на сообщение)",
                parse_mode=ParseMode.HTML
            )
            return
        
        if not context.args:
            await message.reply_text(
                "⚠️ <b>Укажите причину репорта!</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        reporter = update.effective_user
        reported = message.reply_to_message.from_user
        reported_msg = message.reply_to_message
        
        if reporter.id == reported.id:
            await message.reply_text(
                "⚠️ <b>Нельзя репортить самого себя!</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        reason = " ".join(context.args)
        
        # Сохраняем
        report_id = db.add_report(
            reporter.id, 
            reported.id, 
            reason,
            reported_msg.message_id,
            message.chat_id,
            message.chat.username
        )
        
        # Достижения
        new_achievements = db.check_achievements(reporter.id)
        if new_achievements:
            ach_names = [Config.ACHIEVEMENTS.get(a, {}).get('name', a) for a in new_achievements]
            await message.reply_text(
                f"🏆 <b>Новое достижение!</b>\n"
                f"{', '.join(ach_names)}",
                parse_mode=ParseMode.HTML
            )
        
        # Ссылка на сообщение
        if message.chat.username:
            link = f"https://t.me/{message.chat.username}/{reported_msg.message_id}"
        else:
            chat_id = str(message.chat_id)[4:] if str(message.chat_id).startswith('-100') else str(message.chat_id)
            link = f"https://t.me/c/{chat_id}/{reported_msg.message_id}"
        
        # Уведомление админу
        admin_text = (
            f"🚨 <b>НОВЫЙ РЕПОРТ #{report_id}</b>\n\n"
            f"<b>От:</b> @{reporter.username or reporter.first_name}\n"
            f"<b>На:</b> @{reported.username or reported.first_name}\n"
            f"<b>Причина:</b> {reason}\n"
            f"<b>Сообщение:</b> {reported_msg.text[:100]}...\n"
            f"<b>Чат:</b> {message.chat.title or 'личка'}"
        )
        
        keyboard = [[InlineKeyboardButton("🔍 Перейти к сообщению", url=link)]]
        
        await context.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=admin_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        await message.reply_text(
            "✅ <b>Репорт отправлен администратору!</b>",
            parse_mode=ParseMode.HTML
        )
        
        db.update_last_active(reporter.id)
        
    except Exception as e:
        logger.error(f"Ошибка в report: {e}", exc_info=True)

async def reputation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик +реп / -реп"""
    try:
        if not update.message or not update.message.reply_to_message:
            return
        
        text = update.message.text.lower()
        
        if "+реп" not in text and "-реп" not in text:
            return
        
        giver = update.effective_user
        receiver = update.message.reply_to_message.from_user
        
        if giver.id == receiver.id:
            await update.message.reply_text(
                "⚠️ <b>Нельзя менять репутацию самому себе!</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        value = 1 if "+реп" in text else -1
        
        # Добавляем репутацию
        db.add_reputation(giver.id, receiver.id, value)
        db.add_connection(giver.id, receiver.id)
        
        # Достижения
        new_achievements = db.check_achievements(receiver.id)
        
        rep_total = db.get_reputation(receiver.id)
        balloon_emoji = get_user_emoji(receiver.id, db)
        
        await update.message.reply_text(
            f"{balloon_emoji} "
            f"<b>Репутация @{receiver.username or receiver.first_name} изменена!</b>\n\n"
            f"<b>Текущая репутация:</b> {rep_total}",
            parse_mode=ParseMode.HTML
        )
        
        if new_achievements:
            ach_names = [Config.ACHIEVEMENTS.get(a, {}).get('name', a) for a in new_achievements]
            await update.message.reply_text(
                f"🏆 @{receiver.username or receiver.first_name} получил: {', '.join(ach_names)}!",
                parse_mode=ParseMode.HTML
            )
        
        db.update_last_active(giver.id)
        db.update_last_active(receiver.id)
        
    except Exception as e:
        logger.error(f"Ошибка в reputation: {e}", exc_info=True)

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /адм"""
    try:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("🚨 Репорты", callback_data="admin_reports")],
            [InlineKeyboardButton("🏆 Топ", callback_data="admin_top")],
            [InlineKeyboardButton("🎈 Данные", callback_data="admin_data")],
        ]
        
        await update.message.reply_text(
            "👑 <b>Панель администратора</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка в admin: {e}", exc_info=True)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок админки"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "admin_stats":
            stats = db.get_stats()
            
            text = f"📊 <b>Статистика</b>\n\n"
            text += f"👥 Всего: {stats['total_users']}\n"
            text += f"📅 Активных: {stats['active_today']}\n"
            text += f"🚨 Репортов: {stats['total_reports']}\n"
            text += f"⭐ Средняя репа: {stats['avg_rep']}\n\n"
            text += f"<b>Типы шаров:</b>\n"
            
            for t, count in stats['balloon_stats'].items():
                name = Config.BALLOON_TYPES.get(t, {}).get('name', t)
                text += f"• {name}: {count}\n"
            
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
            
        elif query.data == "admin_reports":
            reports = db.get_pending_reports(5)
            
            if not reports:
                await query.edit_message_text("✅ Нет активных репортов", parse_mode=ParseMode.HTML)
                return
            
            text = "🚨 <b>Ожидают проверки:</b>\n\n"
            for r in reports:
                text += f"#{r['id']}: @{r['reporter_id']} → @{r['reported_id']}: {r['reason'][:50]}\n"
            
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
            
        elif query.data == "admin_top":
            top = db.get_top_users(10)
            
            text = "🏆 <b>Топ пользователей</b>\n\n"
            for i, u in enumerate(top, 1):
                rep = u['rep_positive'] - u['rep_negative']
                emoji = get_user_emoji(u['user_id'], db)
                text += f"{i}. {emoji} @{u['username']} - {rep}\n"
            
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
            
        elif query.data == "admin_data":
            # Экспорт данных для WebApp
            data = {
                'balloons': db.get_balloons_data(),
                'connections': db.get_connections_data(),
                'types': Config.BALLOON_TYPES
            }
            
            # Отправляем как файл
            import json
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            with open('webapp_data.json', 'w', encoding='utf-8') as f:
                f.write(json_str)
            
            await query.edit_message_text(
                "✅ Данные экспортированы в webapp_data.json\n"
                "Положите этот файл в папку webapp/",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Ошибка в admin_callback: {e}", exc_info=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик"""
    try:
        if not update.message or not update.message.text:
            return
        
        text = update.message.text.strip()
        
        # Репутация
        if update.message.reply_to_message:
            if "+реп" in text.lower() or "-реп" in text.lower():
                await reputation_handler(update, context)
                return
        
        # Команды
        cmd = text.lower()
        
        if cmd in ["и", "/и"]:
            context.args = []
            await profile_command(update, context)
        elif cmd in ["адм", "/адм"]:
            await admin_command(update, context)
        elif cmd.startswith(("репорт", "/репорт")):
            parts = text.split()
            context.args = parts[1:] if len(parts) > 1 else []
            await report_command(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}", exc_info=True)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=True)


# ============================================================
# ЗАПУСК
# ============================================================

def main():
    """Главная функция"""
    try:
        print("🎈 Запуск AirRep...")
        print(f"📊 WebApp URL: {Config.WEBAPP_URL}")
        print(f"📝 Admin ID: {Config.ADMIN_ID}")
        
        # Создаем приложение
        app = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Добавляем обработчики
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(admin_callback))
        app.add_error_handler(error_handler)
        
        # Сигналы
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        
        print("✅ Бот запущен!")
        print("📝 Команды: и, адм, репорт, +реп/-реп")
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}", exc_info=True)


# ============================================================
# ГЕНЕРАЦИЯ WEBAPP
# ============================================================

def generate_webapp():
    """Создает файл webapp/index.html с 3D визуализацией"""
    
    html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta property="og:title" content="AirRep - Воздушная репутация">
    <meta property="og:description" content="3D визуализация репутации">
    <title>AirRep - Небо репутации</title>
    <style>
        body { margin: 0; overflow: hidden; font-family: 'Segoe UI', sans-serif; }
        #info {
            position: absolute; top: 20px; left: 20px;
            background: rgba(0,0,0,0.7); color: white;
            padding: 15px 25px; border-radius: 40px;
            backdrop-filter: blur(10px); z-index: 10;
        }
        #controls {
            position: absolute; bottom: 30px; left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8); color: white;
            padding: 15px 30px; border-radius: 60px;
            backdrop-filter: blur(10px); z-index: 10;
            display: flex; gap: 20px;
        }
        .control-btn {
            background: rgba(255,255,255,0.1); border: none;
            color: white; padding: 10px 20px; border-radius: 30px;
            cursor: pointer; font-size: 16px;
            transition: all 0.2s;
        }
        .control-btn:hover { background: rgba(255,255,255,0.2); }
        #search {
            position: absolute; top: 20px; right: 20px;
            background: rgba(0,0,0,0.7); backdrop-filter: blur(10px);
            border-radius: 40px; padding: 5px; display: flex;
            z-index: 10;
        }
        #search input {
            background: transparent; border: none;
            padding: 12px 20px; color: white; font-size: 16px;
            width: 250px; outline: none;
        }
        #search button {
            background: rgba(255,255,255,0.1); border: none;
            color: white; padding: 12px 25px; border-radius: 40px;
            cursor: pointer; font-weight: 600;
        }
        #profile-card {
            position: absolute; top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.9); backdrop-filter: blur(20px);
            color: white; padding: 30px; border-radius: 30px;
            z-index: 20; min-width: 300px; display: none;
            border: 1px solid rgba(255,255,255,0.2);
        }
        #profile-card.show { display: block; animation: fadeIn 0.3s; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translate(-50%, -40%); }
            to { opacity: 1; transform: translate(-50%, -50%); }
        }
        #profile-card .close {
            position: absolute; top: 20px; right: 20px;
            background: none; border: none; color: white;
            font-size: 24px; cursor: pointer;
        }
        #stats {
            position: absolute; bottom: 100px; right: 20px;
            background: rgba(0,0,0,0.6); backdrop-filter: blur(10px);
            color: white; padding: 15px; border-radius: 20px;
            font-size: 14px; z-index: 10;
        }
        #loading {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: #0a0a2a; display: flex;
            justify-content: center; align-items: center; z-index: 100;
            transition: opacity 1s;
        }
        .loader {
            width: 60px; height: 60px;
            border: 5px solid rgba(255,255,255,0.1);
            border-top-color: #ffd700; border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 768px) {
            #controls { flex-wrap: wrap; width: 90%; padding: 10px; }
            #search input { width: 150px; }
        }
    </style>
</head>
<body>
    <div id="loading"><div class="loader"></div></div>
    
    <div id="info">
        <h1>🎈 AirRep - Небо репутации</h1>
        <p>Чем выше шар, тем выше репутация</p>
    </div>
    
    <div id="search">
        <input type="text" id="search-input" placeholder="@username">
        <button id="search-btn">🔍 Найти</button>
    </div>
    
    <div id="controls">
        <button class="control-btn" id="zoom-in">➕</button>
        <button class="control-btn" id="zoom-out">➖</button>
        <button class="control-btn" id="reset-view">🔄</button>
        <button class="control-btn" id="toggle-wind">🌬️</button>
    </div>
    
    <div id="stats">
        <div>👥 Всего: <span id="total-users">0</span></div>
        <div>🎈 Выше всех: <span id="top-user">-</span></div>
    </div>
    
    <div id="profile-card">
        <button class="close" id="close-profile-card">×</button>
        <h2 id="profile-name">Загрузка...</h2>
        <div class="profile-info" id="profile-details"></div>
        <button id="close-profile" style="width:100%; padding:12px; margin-top:20px; background:rgba(255,255,255,0.1); border:none; color:white; border-radius:30px; cursor:pointer;">Закрыть</button>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    
    <script>
        // Telegram WebApp
        const tg = window.Telegram?.WebApp;
        if (tg) { tg.expand(); tg.ready(); }
        
        // Состояние
        let scene, camera, renderer, controls;
        let balloons = [];
        let connections = [];
        let windEnabled = true;
        let users = [];
        
        // Загрузка
        window.addEventListener('load', () => {
            setTimeout(() => {
                document.getElementById('loading').style.opacity = '0';
                setTimeout(() => {
                    document.getElementById('loading').style.display = 'none';
                }, 1000);
            }, 1500);
            
            initScene();
            loadData();
        });
        
        function initScene() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x87CEEB);
            
            camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(20, 15, 30);
            camera.lookAt(0, 10, 0);
            
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.shadowMap.enabled = true;
            document.body.appendChild(renderer.domElement);
            
            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.maxPolarAngle = Math.PI / 2.2;
            controls.minDistance = 10;
            controls.maxDistance = 80;
            controls.enableDamping = true;
            
            // Освещение
            const ambientLight = new THREE.AmbientLight(0x404060);
            scene.add(ambientLight);
            
            const dirLight = new THREE.DirectionalLight(0xffffff, 1);
            dirLight.position.set(10, 30, 20);
            dirLight.castShadow = true;
            scene.add(dirLight);
            
            // Облака
            for (let i = 0; i < 20; i++) {
                const cloudGeo = new THREE.SphereGeometry(1, 8, 8);
                const cloudMat = new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.3 });
                const cloud = new THREE.Mesh(cloudGeo, cloudMat);
                const radius = 15 + Math.random() * 20;
                const angle = Math.random() * Math.PI * 2;
                cloud.position.x = Math.cos(angle) * radius;
                cloud.position.z = Math.sin(angle) * radius;
                cloud.position.y = 20 + Math.random() * 15;
                cloud.scale.set(3 + Math.random() * 5, 0.5, 2 + Math.random() * 4);
                scene.add(cloud);
            }
            
            // Земля
            const gridHelper = new THREE.GridHelper(100, 20, 0x88aaff, 0x335588);
            gridHelper.position.y = -1;
            scene.add(gridHelper);
        }
        
        function loadData() {
            // Тестовые данные
            const names = ['alex', 'maria', 'dmitry', 'elena', 'sergey', 'anna', 'pavel', 'olga'];
            const types = ['owner', 'top_moderator', 'moderator', 'veteran', 'active', 'user', 'newbie'];
            const colors = {
                owner: '#FFD700', top_moderator: '#C0C0C0', moderator: '#CD7F32',
                veteran: '#4169E1', active: '#32CD32', user: '#FFA500',
                newbie: '#87CEEB', warning: '#FF4444', banned: '#000000'
            };
            const heights = { owner: 25, top_moderator: 20, moderator: 17, veteran: 14, active: 11, user: 8, newbie: 5 };
            
            for (let i = 0; i < 50; i++) {
                const type = i === 0 ? 'owner' : types[Math.floor(Math.random() * types.length)];
                users.push({
                    id: 1000000 + i,
                    username: names[i % names.length] + (i > 7 ? i : ''),
                    first_name: names[i % names.length],
                    type: type,
                    rep: type === 'owner' ? 1500 : Math.floor(Math.random() * 500),
                    color: colors[type],
                    height: heights[type] || 5,
                    size: type === 'owner' ? 2.0 : type === 'top_moderator' ? 1.8 : type === 'moderator' ? 1.6 : 1.0
                });
            }
            
            document.getElementById('total-users').textContent = users.length;
            
            users.forEach(user => {
                const group = new THREE.Group();
                
                // Шар
                const balloonGeo = new THREE.SphereGeometry(user.size, 32, 32);
                const balloonMat = new THREE.MeshStandardMaterial({ color: user.color });
                const balloon = new THREE.Mesh(balloonGeo, balloonMat);
                balloon.castShadow = true;
                balloon.position.y = 0;
                group.add(balloon);
                
                // Веревка
                const ropeGeo = new THREE.CylinderGeometry(0.03, 0.03, 1.5);
                const ropeMat = new THREE.MeshStandardMaterial({ color: 0x8B4513 });
                const rope = new THREE.Mesh(ropeGeo, ropeMat);
                rope.position.y = -1.2;
                group.add(rope);
                
                // Корзина
                const basketGeo = new THREE.BoxGeometry(0.6, 0.4, 0.6);
                const basketMat = new THREE.MeshStandardMaterial({ color: 0xDEB887 });
                const basket = new THREE.Mesh(basketGeo, basketMat);
                basket.position.y = -2.0;
                basket.castShadow = true;
                group.add(basket);
                
                // Позиция
                const angle = Math.random() * Math.PI * 2;
                const radius = 5 + Math.random() * 15;
                group.position.x = Math.cos(angle) * radius;
                group.position.z = Math.sin(angle) * radius;
                group.position.y = user.height;
                
                group.userData = user;
                
                scene.add(group);
                balloons.push({
                    mesh: group,
                    data: user,
                    offsetX: Math.random() * 100,
                    offsetZ: Math.random() * 100
                });
            });
            
            animate();
        }
        
        function animate() {
            requestAnimationFrame(animate);
            
            if (windEnabled) {
                const time = Date.now() * 0.001;
                balloons.forEach(b => {
                    b.mesh.position.x += Math.sin(time + b.offsetX) * 0.002;
                    b.mesh.position.z += Math.cos(time + b.offsetZ) * 0.002;
                    b.mesh.rotation.y += 0.001;
                });
            }
            
            controls.update();
            renderer.render(scene, camera);
        }
        
        // UI обработчики
        document.getElementById('zoom-in').addEventListener('click', () => {
            camera.position.multiplyScalar(0.8);
        });
        
        document.getElementById('zoom-out').addEventListener('click', () => {
            camera.position.multiplyScalar(1.2);
        });
        
        document.getElementById('reset-view').addEventListener('click', () => {
            camera.position.set(20, 15, 30);
            controls.target.set(0, 10, 0);
        });
        
        document.getElementById('toggle-wind').addEventListener('click', (btn) => {
            windEnabled = !windEnabled;
            btn.target.textContent = windEnabled ? '🌬️' : '💨';
        });
        
        document.getElementById('search-btn').addEventListener('click', () => {
            const query = document.getElementById('search-input').value.toLowerCase();
            const found = balloons.find(b => 
                b.data.username.toLowerCase().includes(query) ||
                b.data.first_name.toLowerCase().includes(query)
            );
            
            if (found) {
                camera.position.set(
                    found.mesh.position.x + 5,
                    found.mesh.position.y + 3,
                    found.mesh.position.z + 5
                );
                controls.target.copy(found.mesh.position);
                
                // Показать профиль
                document.getElementById('profile-name').innerHTML = 
                    `<span style="color:${found.data.color}">🎈</span> ${found.data.first_name} (@${found.data.username})`;
                document.getElementById('profile-details').innerHTML = `
                    <div>⭐ Репутация: ${found.data.rep}</div>
                    <div>🎈 Тип: ${found.data.type}</div>
                    <div>📏 Высота: ${found.data.height}м</div>
                `;
                document.getElementById('profile-card').classList.add('show');
            }
        });
        
        document.getElementById('close-profile-card').addEventListener('click', () => {
            document.getElementById('profile-card').classList.remove('show');
        });
        
        document.getElementById('close-profile').addEventListener('click', () => {
            document.getElementById('profile-card').classList.remove('show');
        });
        
        // Resize
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        // Параметры из URL
        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user');
        if (userId) {
            setTimeout(() => {
                const found = balloons.find(b => b.data.id == userId);
                if (found) {
                    camera.position.set(
                        found.mesh.position.x + 5,
                        found.mesh.position.y + 3,
                        found.mesh.position.z + 5
                    );
                    controls.target.copy(found.mesh.position);
                }
            }, 2000);
        }
    </script>
</body>
</html>"""
    
    # Создаем папку webapp если её нет
    os.makedirs("webapp", exist_ok=True)
    
    # Записываем файл
    with open("webapp/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("✅ WebApp создан: webapp/index.html")


# ============================================================
# ТОЧКА ВХОДА
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-webapp":
        # Генерация HTML файла
        generate_webapp()
    else:
        # Запуск бота
        main()
