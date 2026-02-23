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
                f"Вы получили: {', '.join(new_achievements)}",
                parse_mode=ParseMode.HTML
            )
        
        # Уведомление админу
        admin_text = (
            f"🚨 <b>НОВЫЙ РЕПОРТ #{report_id}</b>\n\n"
            f"<b>От:</b> @{reporter.username or reporter.first_name}\n"
            f"<b>На:</b> @{reported.username or reported.first_name}\n"
            f"<b>Причина:</b> {reason}\n"
            f"<b>Сообщение:</b> {reported_msg.text[:100]}...\n"
            f"<b>Чат:</b> {message.chat.title or 'личка'}"
        )
        
        # Кнопка перехода к сообщению
        if message.chat.username:
            link = f"https://t.me/{message.chat.username}/{reported_msg.message_id}"
        else:
            chat_id = str(message.chat_id)[4:] if str(message.chat_id).startswith('-100') else str(message.chat_id)
            link = f"https://t.me/c/{chat_id}/{reported_msg.message_id}"
        
        keyboard = [[InlineKeyboardButton("🔍 Перейти к сообщению", url=link)]]
        
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
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
        
        # Проверяем кулдаун (в реальном проекте - в БД)
        
        value = 1 if "+реп" in text else -1
        
        # Добавляем репутацию
        db.add_reputation(giver.id, receiver.id, value)
        
        # Добавляем связь
        db.add_connection(giver.id, receiver.id)
        
        # Проверяем достижения
        new_achievements = db.check_achievements(receiver.id)
        
        rep_total = db.get_reputation(receiver.id)
        balloon_emoji = get_emoji_for_user(receiver.id)
        
        await update.message.reply_text(
            f"{balloon_emoji} "
            f"<b>Репутация @{receiver.username or receiver.first_name} изменена!</b>\n\n"
            f"<b>Текущая репутация:</b> {rep_total}",
            parse_mode=ParseMode.HTML
        )
        
        if new_achievements:
            await update.message.reply_text(
                f"🏆 @{receiver.username or receiver.first_name} получил достижение: {', '.join(new_achievements)}!",
                parse_mode=ParseMode.HTML
            )
        
        db.update_last_active(giver.id)
        db.update_last_active(receiver.id)
        
    except Exception as e:
        logger.error(f"Ошибка в reputation: {e}", exc_info=True)

# ===== АДМИН-КОМАНДЫ =====

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /адм - панель администратора"""
    try:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("🚨 Репорты", callback_data="admin_reports")],
            [InlineKeyboardButton("🎈 Управление шарами", callback_data="admin_balloons")],
            [InlineKeyboardButton("📋 Топ пользователей", callback_data="admin_top")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")]
        ]
        
        await update.message.reply_text(
            "👑 <b>Панель администратора</b>\n\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка в admin: {e}", exc_info=True)

@admin_only
async def balloon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление шарами"""
    try:
        args = context.args
        if not args:
            await update.message.reply_text(
                "🎈 <b>Управление шарами</b>\n\n"
                "Команды:\n"
                "/шар создать @user - создать шар\n"
                "/шар поднять @user - повысить\n"
                "/шар опустить @user - понизить\n"
                "/шар цвет @user #FF0000 - сменить цвет\n"
                "/шар имя @user Название - дать имя\n"
                "/шар лопнуть @user - забанить\n"
                "/шар типы - список типов",
                parse_mode=ParseMode.HTML
            )
            return
        
        subcmd = args[0].lower()
        
        if subcmd == "типы":
            from config import BALLOON_TYPES
            text = "🎈 <b>Типы шаров:</b>\n\n"
            for key, data in BALLOON_TYPES.items():
                text += f"• {data['name']}: {data['min_rep']}-{data['max_rep']} реп\n"
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            
        elif subcmd == "создать" and len(args) >= 2:
            username = args[1].lstrip('@')
            # Поиск пользователя
            all_users = db.get_all_users()
            for u in all_users:
                if u['username'].lower() == username.lower():
                    await update.message.reply_text(
                        f"✅ Шар для @{username} уже существует!",
                        parse_mode=ParseMode.HTML
                    )
                    return
            
            await update.message.reply_text(
                f"❌ Пользователь @{username} не найден в БД.\n"
                f"Попросите его написать /start",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Ошибка в balloon: {e}", exc_info=True)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок админ-панели"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "admin_stats":
            stats = db.get_stats()
            
            text = (
                f"📊 <b>Статистика</b>\n\n"
                f"👥 Всего пользователей: {stats['total_users']}\n"
                f"📅 Активных сегодня: {stats['active_today']}\n"
                f"🚨 Всего репортов: {stats['total_reports']}\n"
                f"⭐ Средняя репутация: {stats['avg_rep']}\n\n"
                f"<b>Типы шаров:</b>\n"
            )
            
            for type_name, count in stats['balloon_stats'].items():
                text += f"• {type_name}: {count}\n"
            
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
            
        elif query.data == "admin_reports":
            reports = db.get_reports(limit=5)
            
            if not reports:
                await query.edit_message_text(
                    "✅ Нет активных репортов",
                    parse_mode=ParseMode.HTML
                )
                return
            
            text = "🚨 <b>Последние репорты:</b>\n\n"
            for r in reports:
                text += f"#{r['id']}: @{r['reporter_id']} на @{r['reported_id']} - {r['reason'][:50]}\n"
            
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
            
        elif query.data == "admin_top":
            top_users = db.get_top_users(10)
            
            text = "🏆 <b>Топ пользователей</b>\n\n"
            for i, u in enumerate(top_users, 1):
                rep = u['rep_positive'] - u['rep_negative']
                text += f"{i}. @{u['username']} - {rep} реп\n"
            
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
            
    except Exception as e:
        logger.error(f"Ошибка в admin_callback: {e}", exc_info=True)

# ===== ОСНОВНОЙ ОБРАБОТЧИК =====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех сообщений"""
    try:
        if not update.message or not update.message.text:
            return
        
        text = update.message.text.strip()
        
        # Проверяем репутацию (ответы)
        if update.message.reply_to_message:
            if "+реп" in text.lower() or "-реп" in text.lower():
                await reputation_handler(update, context)
                return
        
        # Проверяем команды
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
        elif cmd.startswith(("шар", "/шар")):
            parts = text.split()
            context.args = parts[1:] if len(parts) > 1 else []
            await balloon_command(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}", exc_info=True)

# ===== ЗАПУСК =====

def main():
    """Запуск бота"""
    try:
        print("🎈 Запуск AirRep...")
        
        app = Application.builder().token(config.BOT_TOKEN).build()
        
        # Добавляем обработчики
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(admin_callback))
        
        # Обработка сигналов
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        
        print("✅ Бот запущен!")
        print("📝 Команды: и, адм, репорт, +реп/-реп")
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}", exc_info=True)

if __name__ == "__main__":
    main()
