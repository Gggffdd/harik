# bot.py
"""
Основной файл бота AirRep
"""

import logging
import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional
from functools import wraps
import json

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

import config
from database import Database

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, config.LOG_LEVEL),
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация БД
db = Database(config.DATABASE_PATH)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def emoji(emoji_id: str, fallback: str = "•") -> str:
    """Создает тег emoji для Telegram"""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def get_emoji_for_user(user_id: int) -> str:
    """Получить эмодзи для пользователя"""
    user = db.get_user(user_id)
    if not user:
        return "•"
    
    balloon_type = user.get('balloon_type', 'newbie')
    emoji_map = {
        'owner': '👑',
        'top_moderator': '⚜️',
        'moderator': '🏆',
        'veteran': '🔵',
        'active': '🟢',
        'user': '🟠',
        'newbie': '🩵',
        'warning': '⚠️',
        'banned': '💔'
    }
    return emoji_map.get(balloon_type, '🎈')

def admin_only(func):
    """Декоратор для админа"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != config.ADMIN_ID:
            if update.message:
                await update.message.reply_text(
                    f"⚠️ <b>Эта команда только для администратора.</b>",
                    parse_mode=ParseMode.HTML
                )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ===== ОБРАБОТЧИКИ КОМАНД =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    try:
        user = update.effective_user
        db.get_or_create_user(user.id, user.username or "", user.first_name)
        
        # Кнопка для открытия WebApp
        keyboard = [[
            InlineKeyboardButton(
                "🎈 Открыть небо", 
                web_app={"url": config.WEBAPP_URL}
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
    """Команда /и - профиль пользователя"""
    try:
        user = update.effective_user
        message = update.message
        
        # Определяем целевого пользователя
        target_user = None
        
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
        elif context.args and context.args[0].startswith('@'):
            username = context.args[0][1:].lower()
            # Ищем в БД
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
        
        # Получаем данные
        user_data = db.get_or_create_user(
            target_user.id, 
            target_user.username or "", 
            target_user.first_name
        )
        
        rep_total = user_data['rep_positive'] - user_data['rep_negative']
        balloon_emoji = get_emoji_for_user(target_user.id)
        
        # Формируем текст
        text = (
            f"{balloon_emoji} <b>Профиль {target_user.first_name}</b>\n\n"
            f"<b>🆔 ID:</b> <code>{target_user.id}</code>\n"
            f"<b>📝 Username:</b> @{target_user.username or 'нет'}\n"
            f"<b>📅 В чате с:</b> {user_data['join_date'][:10]}\n\n"
            f"<b>🎈 Репутация:</b> {rep_total}\n"
            f"   Получено: +{user_data['rep_positive']} / -{user_data['rep_negative']}\n"
            f"   Оставлено: +{user_data['rep_given_positive']} / -{user_data['rep_given_negative']}\n\n"
            f"<b>🚨 Репорты:</b>\n"
            f"   Подано: {user_data['reports_submitted']}\n"
            f"   Подтверждено: {user_data['reports_confirmed']}"
        )
        
        # Кнопка открыть в небе
        keyboard = [[
            InlineKeyboardButton(
                "🎈 Найти в небе",
                web_app={"url": f"{config.WEBAPP_URL}?user={target_user.id}"}
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
        
        # Сохраняем в БД
        report_id = db.add_report(
            reporter.id, 
            reported.id, 
            reason,
            reported_msg.message_id,
            message.chat_id
        )
        
        # Проверяем достижения
        new_achievements = db.check_achievements(reporter.id)
        if new_achievements:
            await message.reply_text(
                f"🏆 <b>Новое достижение!</b>\n"
                f"Вы получили: {', '.join(new_achievements)}
