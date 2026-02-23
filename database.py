# database.py
"""
Работа с базой данных SQLite
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с БД"""
    
    def __init__(self, db_path: str = "airrep.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Получить соединение с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализация таблиц"""
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
            
            # Связи между шарами
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
            logger.info("База данных инициализирована")
    
    # ===== ПОЛЬЗОВАТЕЛИ =====
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя по ID"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", 
                (user_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def create_user(self, user_id: int, username: str = "", first_name: str = "") -> Dict:
        """Создать нового пользователя"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO users (
                    user_id, username, first_name, join_date, last_active, balloon_type
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, now, now, 'newbie'))
            conn.commit()
            
            user = self.get_user(user_id)
            logger.info(f"Создан пользователь {user_id} ({username})")
            return user
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """Обновить данные пользователя"""
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
        """Обновить время активности"""
        self.update_user(user_id, last_active=datetime.now().isoformat())
    
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = "") -> Dict:
        """Получить или создать пользователя"""
        user = self.get_user(user_id)
        if not user:
            user = self.create_user(user_id, username, first_name)
        return user
    
    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY rep_positive DESC").fetchall()
            return [dict(row) for row in rows]
    
    def get_top_users(self, limit: int = 10) -> List[Dict]:
        """Топ пользователей по репутации"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT *, (rep_positive - rep_negative) as total_rep 
                FROM users 
                WHERE rep_positive - rep_negative > 0
                ORDER BY total_rep DESC 
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def search_users(self, query: str) -> List[Dict]:
        """Поиск пользователей"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM users 
                WHERE username LIKE ? OR first_name LIKE ? 
                LIMIT 20
            ''', (f'%{query}%', f'%{query}%')).fetchall()
            return [dict(row) for row in rows]
    
    # ===== РЕПУТАЦИЯ =====
    
    def add_reputation(self, from_id: int, to_id: int, value: int) -> bool:
        """Добавить репутацию"""
        field_pos = "rep_positive" if value > 0 else "rep_negative"
        field_given = "rep_given_positive" if value > 0 else "rep_given_negative"
        
        with self.get_connection() as conn:
            # Обновляем получателя
            conn.execute(
                f"UPDATE users SET {field_pos} = {field_pos} + 1 WHERE user_id = ?",
                (to_id,)
            )
            # Обновляем дающего
            conn.execute(
                f"UPDATE users SET {field_given} = {field_given} + 1 WHERE user_id = ?",
                (from_id,)
            )
            # Записываем историю
            conn.execute('''
                INSERT INTO rep_history (from_id, to_id, value, date)
                VALUES (?, ?, ?, ?)
            ''', (from_id, to_id, value, datetime.now().isoformat()))
            conn.commit()
            
            # Обновляем тип шара
            self.update_balloon_type(to_id)
            return True
    
    def get_reputation(self, user_id: int) -> int:
        """Получить общую репутацию"""
        user = self.get_user(user_id)
        if not user:
            return 0
        return user['rep_positive'] - user['rep_negative']
    
    def update_balloon_type(self, user_id: int):
        """Обновить тип шара на основе репутации"""
        from config import BALLOON_TYPES
        
        rep = self.get_reputation(user_id)
        
        for type_name, type_config in BALLOON_TYPES.items():
            if type_config['min_rep'] <= rep <= type_config['max_rep']:
                self.update_user(
                    user_id, 
                    balloon_type=type_name,
                    balloon_color=type_config.get('color'),
                    balloon_size=type_config.get('size', 1.0)
                )
                break
    
    # ===== СВЯЗИ =====
    
    def add_connection(self, user1_id: int, user2_id: int):
        """Добавить или укрепить связь"""
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
    
    def get_connections(self, user_id: int) -> List[Dict]:
        """Получить связи пользователя"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT u.*, c.strength 
                FROM connections c
                JOIN users u ON u.user_id = c.user2_id
                WHERE c.user1_id = ?
                ORDER BY c.strength DESC
                LIMIT 50
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]
    
    # ===== РЕПОРТЫ =====
    
    def add_report(self, reporter_id: int, reported_id: int, reason: str, 
                   message_id: int, chat_id: int) -> int:
        """Добавить репорт"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO reports (reporter_id, reported_id, reason, message_id, chat_id, date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (reporter_id, reported_id, reason, message_id, chat_id, datetime.now().isoformat()))
            
            # Увеличиваем счетчик репортов у пользователя
            conn.execute('''
                UPDATE users SET reports_submitted = reports_submitted + 1
                WHERE user_id = ?
            ''', (reporter_id,))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_reports(self, status: str = 'pending', limit: int = 20) -> List[Dict]:
        """Получить репорты"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM reports 
                WHERE status = ?
                ORDER BY date DESC
                LIMIT ?
            ''', (status, limit)).fetchall()
            return [dict(row) for row in rows]
    
    def resolve_report(self, report_id: int, confirmed: bool = True):
        """Закрыть репорт"""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE reports SET status = ? WHERE id = ?",
                ('confirmed' if confirmed else 'rejected', report_id)
            )
            
            if confirmed:
                # Увеличиваем счетчик подтвержденных репортов
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
    
    # ===== ДОСТИЖЕНИЯ =====
    
    def check_achievements(self, user_id: int) -> List[str]:
        """Проверить и выдать достижения"""
        user = self.get_user(user_id)
        if not user:
            return []
        
        rep = user['rep_positive'] - user['rep_negative']
        new_achievements = []
        
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
                    # Проверяем, есть ли уже
                    existing = conn.execute('''
                        SELECT * FROM achievements 
                        WHERE user_id = ? AND achievement_id = ?
                    ''', (user_id, ach_id)).fetchone()
                    
                    if not existing:
                        conn.execute('''
                            INSERT INTO achievements (user_id, achievement_id, achieved_date)
                            VALUES (?, ?, ?)
                        ''', (user_id, ach_id, datetime.now().isoformat()))
                        new_achievements.append(ach_id)
            
            conn.commit()
        
        return new_achievements
    
    def get_achievements(self, user_id: int) -> List[str]:
        """Получить достижения пользователя"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT achievement_id FROM achievements
                WHERE user_id = ?
            ''', (user_id,)).fetchall()
            return [row['achievement_id'] for row in rows]
    
    # ===== СТАТИСТИКА =====
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить общую статистику"""
        with self.get_connection() as conn:
            # Всего пользователей
            total_users = conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]
            
            # Активные сегодня
            today = datetime.now().date().isoformat()
            active_today = conn.execute('''
                SELECT COUNT(*) FROM users 
                WHERE date(last_active) = date(?)
            ''', (today,)).fetchone()[0]
            
            # Всего репортов
            total_reports = conn.execute(
                "SELECT COUNT(*) FROM reports"
            ).fetchone()[0]
            
            # Средняя репутация
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
