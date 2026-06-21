import os
import io
import logging
import random
import string
import asyncio
import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message
)
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# Загрузка токена из .env
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")

if not API_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in .env file!")

logging.basicConfig(level=logging.INFO)

# ================== БАЗА ДАННЫХ ==================
DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ruzopoly.db"

# ================== ПЕРЕВОДЫ ==================
TRANSLATIONS = {
    'en': {
        'welcome': "🎩 Welcome to **RUZOPOLY**!\n\nClassic Monopoly with **Ruzcoin** currency 💰\n\nChoose language:",
        'create_room': "🏠 Create Room",
        'join_by_code': "🚪 Join by Code",
        'browse_rooms': "📋 Browse Rooms",
        'choose_max_players': "👥 Choose max players:",
        'players': "players",
        'password_question': "Max players: {}. Password?",
        'with_password': "🔒 With Password",
        'no_password': "🔓 No Password",
        'enter_password': "🔐 Enter password for the room:",
        'room_info': "🏠 **Ruzopoly Room**\n🔑 Code: `{}`\n🔒 Password: `{}`\n👥 Players: {}/{}\n\n{}\n\nWaiting for players...",
        'none': 'none',
        'add_bot': "🤖 Add Bot",
        'start_game': "🚀 Start Game",
        'refresh': "🔄 Refresh",
        'room_not_found': "Room not found",
        'room_full': "Room is full",
        'bot_added': "Bot {} added!",
        'need_min_players': "Need at least 2 players",
        'game_starting': "🎲 Game starting! Rolling dice...",
        'game_started': "🎲 **Game started!**",
        'player_turn': "🎮 **{}'s TURN**",
        'roll_dice': "🎲 Roll Dice",
        'buy_property': "💵 Buy {} ({}₽)",
        'skip': "❌ Skip",
        'pay_jail': "💰 Pay 50 to exit",
        'not_your_turn': "Not your turn",
        'rolled': "🎲 **{}** rolled: **{} + {} = {}**",
        'passed_start': "💰 {} passed START and received 200 Ruzcoin!",
        'at_start': "🏁 {} at START.",
        'chest_reward': "💎 {} received {} Ruzcoin from Chest!",
        'tax_paid': "💸 {} pays tax {} Ruzcoin.",
        'visiting_jail': "👀 {} just visiting jail.",
        'at_parking': "🅿️ {} resting at parking.",
        'go_to_jail': "🚔 {} goes to JAIL!",
        'rent_paid': "💰 {} pays {} Ruzcoin to **{}** for {}.",
        'own_property': "🏠 {} on their property: {}",
        'free_property': "🏡 Free property: **{}**\n💵 Price: {} Ruzcoin\n🏷️ Rent: {} Ruzcoin\n\n⏰ You have 30 seconds to decide!",
        'not_enough_money': "💸 {} doesn't have enough money to buy {}.",
        'property_bought': "✅ **{}** bought **{}** for {} Ruzcoin!",
        'purchase_declined': "❌ {} declined the purchase.",
        'timeout': "⏰ Time's up! {}'s turn skipped.",
        'jail_doubles': "🎲 {} rolled {}+{} (doubles!) and got out of jail!",
        'jail_no_doubles': "🎲 {} in jail. Rolled {}+{}. Attempts left: {}",
        'jail_pay_forced': "🎲 {} didn't roll doubles for 3 turns. Pays 50 Ruzcoin and exits.",
        'jail_paid_out': "💰 {} paid 50 Ruzcoin and got out of jail!",
        'joined_game': "🎉 **{}** joined the game!",
        'available_rooms': "📋 **Available Rooms:**\n\n",
        'no_rooms': "📋 No available rooms. Create one!",
        'join': "Join {}",
        'back': "« Back",
        'enter_room_code': "🔑 Enter room code:",
        'room_has_password': "🔒 This room is password protected. Enter password:",
        'wrong_password': "❌ Wrong password.",
        'already_in_room': "You're already in this room!",
        'joined_room': "✅ You joined room `{}`!",
        'only_creator_start': "Only room creator can start the game!",
        'not_enough_ruzcoin': "Not enough Ruzcoin",
        'nothing_to_buy': "Nothing to buy",
        'language_selected': "Language set to English! 🇬🇧",
    },
    'ru': {
        'welcome': "🎩 Добро пожаловать в **RUZOPOLY**!\n\nКлассическая Монополия с валютой **Ruzcoin** 💰\n\nВыберите язык:",
        'create_room': "🏠 Создать комнату",
        'join_by_code': "🚪 Присоединиться по коду",
        'browse_rooms': "📋 Список комнат",
        'choose_max_players': "👥 Выберите макс. игроков:",
        'players': "игроков",
        'password_question': "Макс. игроков: {}. Нужен пароль?",
        'with_password': "🔒 С паролем",
        'no_password': "🔓 Без пароля",
        'enter_password': "🔐 Введите пароль для комнаты:",
        'room_info': "🏠 **Комната Ruzopoly**\n🔑 Код: `{}`\n🔒 Пароль: `{}`\n👥 Игроки: {}/{}\n\n{}\n\nОжидаем игроков...",
        'none': 'нет',
        'add_bot': "🤖 Добавить бота",
        'start_game': "🚀 Начать игру",
        'refresh': "🔄 Обновить",
        'room_not_found': "Комната не найдена",
        'room_full': "Комната заполнена",
        'bot_added': "Бот {} добавлен!",
        'need_min_players': "Нужно минимум 2 игрока",
        'game_starting': "🎲 Игра начинается! Бросаем кубики...",
        'game_started': "🎲 **Игра началась!**",
        'player_turn': "🎮 **ХОД ИГРОКА: {}**",
        'roll_dice': "🎲 Бросить кубики",
        'buy_property': "💵 Купить {} ({}₽)",
        'skip': "❌ Пропустить",
        'pay_jail': "💰 Заплатить 50 и выйти",
        'not_your_turn': "Сейчас не ваш ход",
        'rolled': "🎲 **{}** выбросил: **{} + {} = {}**",
        'passed_start': "💰 {} прошёл через СТАРТ и получил 200 Ruzcoin!",
        'at_start': "🏁 {} на СТАРТЕ.",
        'chest_reward': "💎 {} получил {} Ruzcoin из Казны!",
        'tax_paid': "💸 {} платит налог {} Ruzcoin.",
        'visiting_jail': "👀 {} просто навещает тюрьму.",
        'at_parking': "🅿️ {} отдыхает на парковке.",
        'go_to_jail': "🚔 {} отправляется в ТЮРЬМУ!",
        'rent_paid': "💰 {} платит {} Ruzcoin игроку **{}** за {}.",
        'own_property': "🏠 {} на своей территории: {}",
        'free_property': "🏡 Свободная территория: **{}**\n💵 Цена: {} Ruzcoin\n🏷️ Рента: {} Ruzcoin\n\n⏰ У вас 30 секунд на раздумье!",
        'not_enough_money': "💸 У {} недостаточно денег для покупки {}.",
        'property_bought': "✅ **{}** купил **{}** за {} Ruzcoin!",
        'purchase_declined': "❌ {} отказался от покупки.",
        'timeout': "⏰ Время вышло! Ход {} пропущен.",
        'jail_doubles': "🎲 {} выбросил {}+{} (дубль!) и вышел из тюрьмы!",
        'jail_no_doubles': "🎲 {} в тюрьме. Выпало {}+{}. Осталось попыток: {}",
        'jail_pay_forced': "🎲 {} не выбросил дубль за 3 хода. Платит 50 Ruzcoin и выходит.",
        'jail_paid_out': "💰 {} заплатил 50 Ruzcoin и вышел из тюрьмы!",
        'joined_game': "🎉 **{}** присоединился к игре!",
        'available_rooms': "📋 **Доступные комнаты:**\n\n",
        'no_rooms': "📋 Нет доступных комнат. Создайте новую!",
        'join': "Войти {}",
        'back': "« Назад",
        'enter_room_code': "🔑 Введите код комнаты:",
        'room_has_password': "🔒 Эта комната защищена паролем. Введите пароль:",
        'wrong_password': "❌ Неверный пароль.",
        'already_in_room': "Вы уже в этой комнате!",
        'joined_room': "✅ Вы присоединились к комнате `{}`!",
        'only_creator_start': "Только создатель может начать игру!",
        'not_enough_ruzcoin': "Недостаточно Ruzcoin",
        'nothing_to_buy': "Нечего покупать",
        'language_selected': "Язык установлен на Русский! 🇷🇺",
    }
}

def init_db():
    """Database initialization"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT DEFAULT 'en',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            code TEXT PRIMARY KEY,
            creator_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            max_players INTEGER NOT NULL,
            password TEXT,
            current_turn INTEGER DEFAULT 0,
            is_started BOOLEAN DEFAULT 0,
            last_message_id INTEGER,
            chance_deck TEXT,
            risk_deck TEXT,
            awaiting_buy INTEGER,
            language TEXT DEFAULT 'en',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            room_code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            money INTEGER DEFAULT 1500,
            position INTEGER DEFAULT 0,
            color TEXT NOT NULL,
            is_bot BOOLEAN DEFAULT 0,
            in_jail BOOLEAN DEFAULT 0,
            jail_turns INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            PRIMARY KEY (room_code, user_id),
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ownership (
            room_code TEXT NOT NULL,
            cell_idx INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            PRIMARY KEY (room_code, cell_idx),
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_room (
            user_id INTEGER PRIMARY KEY,
            room_code TEXT NOT NULL,
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DB_PATH}")

init_db()

# ================== ДАННЫЕ ПОЛЯ ==================
GROUP_COLORS_HEX = {
    "brown": "#8B4513", "lightblue": "#87CEEB", "pink": "#FF69B4",
    "orange": "#FFA500", "red": "#FF3030", "yellow": "#FFD700",
    "green": "#2E8B57", "darkblue": "#1E3A8A",
}

BOARD = [
    {"name": "START", "type": "go"},
    {"name": "Bread St.", "type": "property", "group": "brown", "price": 60, "rent": 4, "house": 50},
    {"name": "Chest", "type": "chest"},
    {"name": "Bakery", "type": "property", "group": "brown", "price": 60, "rent": 4, "house": 50},
    {"name": "Tax", "type": "tax", "amount": 200},
    {"name": "North Station", "type": "property", "group": "station", "price": 200, "rent": 25},
    {"name": "Alley", "type": "property", "group": "lightblue", "price": 100, "rent": 6, "house": 50},
    {"name": "Chance", "type": "chance"},
    {"name": "Square", "type": "property", "group": "lightblue", "price": 100, "rent": 6, "house": 50},
    {"name": "Boulevard", "type": "property", "group": "lightblue", "price": 120, "rent": 8, "house": 50},
    {"name": "JAIL", "type": "jail"},
    {"name": "Waterfront", "type": "property", "group": "pink", "price": 140, "rent": 10, "house": 100},
    {"name": "Electric Co.", "type": "property", "group": "utility", "price": 150, "rent": 20},
    {"name": "Park", "type": "property", "group": "pink", "price": 140, "rent": 10, "house": 100},
    {"name": "Garden", "type": "property", "group": "pink", "price": 160, "rent": 12, "house": 100},
    {"name": "South Station", "type": "property", "group": "station", "price": 200, "rent": 25},
    {"name": "Peace St.", "type": "property", "group": "orange", "price": 180, "rent": 14, "house": 100},
    {"name": "Risk", "type": "risk"},
    {"name": "Lane", "type": "property", "group": "orange", "price": 180, "rent": 14, "house": 100},
    {"name": "Avenue", "type": "property", "group": "orange", "price": 200, "rent": 16, "house": 100},
    {"name": "PARKING", "type": "free_parking"},
    {"name": "Theater St.", "type": "property", "group": "red", "price": 220, "rent": 18, "house": 150},
    {"name": "Chance", "type": "chance"},
    {"name": "Holy Sq.", "type": "property", "group": "red", "price": 220, "rent": 18, "house": 150},
    {"name": "Kremlin", "type": "property", "group": "red", "price": 240, "rent": 20, "house": 150},
    {"name": "West Station", "type": "property", "group": "station", "price": 200, "rent": 25},
    {"name": "Rostov St.", "type": "property", "group": "yellow", "price": 260, "rent": 22, "house": 150},
    {"name": "Samara St.", "type": "property", "group": "yellow", "price": 260, "rent": 22, "house": 150},
    {"name": "Water Co.", "type": "property", "group": "utility", "price": 150, "rent": 20},
    {"name": "Omsk St.", "type": "property", "group": "yellow", "price": 280, "rent": 24, "house": 150},
    {"name": "GO TO JAIL", "type": "go_to_jail"},
    {"name": "Forest St.", "type": "property", "group": "green", "price": 300, "rent": 26, "house": 200},
    {"name": "River St.", "type": "property", "group": "green", "price": 300, "rent": 26, "house": 200},
    {"name": "Chest", "type": "chest"},
    {"name": "Pine St.", "type": "property", "group": "green", "price": 320, "rent": 28, "house": 200},
    {"name": "East Station", "type": "property", "group": "station", "price": 200, "rent": 25},
    {"name": "Chance", "type": "chance"},
    {"name": "Elite St.", "type": "property", "group": "darkblue", "price": 350, "rent": 35, "house": 200},
    {"name": "Luxury Tax", "type": "tax", "amount": 100},
    {"name": "Palace St.", "type": "property", "group": "darkblue", "price": 400, "rent": 50, "house": 200},
]

CHANCE_CARDS = [
    {"text": "🎉 You won the lottery! +200 Ruzcoin", "text_ru": "🎉 Вы выиграли в лотерею! +200 Ruzcoin", "effect": 200},
    {"text": "🚗 Parking fine. -50 Ruzcoin", "text_ru": "🚗 Штраф за парковку. -50 Ruzcoin", "effect": -50},
    {"text": "🏦 Bank dividends +100 Ruzcoin", "text_ru": "🏦 Банковские дивиденды +100 Ruzcoin", "effect": 100},
    {"text": "🚓 Traffic fine. -100 Ruzcoin", "text_ru": "🚓 Штраф ГИБДД. -100 Ruzcoin", "effect": -100},
    {"text": "🎂 Birthday! Each player pays you 50 Ruzcoin", "text_ru": "🎂 День рождения! Каждый игрок платит вам по 50 Ruzcoin", "effect": "birthday"},
    {"text": "🏃 Go to START. +200 Ruzcoin", "text_ru": "🏃 Переход на СТАРТ. +200 Ruzcoin", "effect": 200, "move_to": 0},
    {"text": "📈 Stocks went up. +150 Ruzcoin", "text_ru": "📈 Акции выросли. +150 Ruzcoin", "effect": 150},
    {"text": "🔧 Property repairs. -100 Ruzcoin", "text_ru": "🔧 Ремонт имущества. -100 Ruzcoin", "effect": -100},
]

RISK_CARDS = [
    {"text": "💸 Luxury tax. -150 Ruzcoin", "text_ru": "💸 Налог на роскошь. -150 Ruzcoin", "effect": -150},
    {"text": "🎁 Gift from uncle. +100 Ruzcoin", "text_ru": "🎁 Подарок от дяди. +100 Ruzcoin", "effect": 100},
    {"text": "🏥 Hospital payment. -100 Ruzcoin", "text_ru": "🏥 Оплата больницы. -100 Ruzcoin", "effect": -100},
    {"text": "💼 Work bonus. +200 Ruzcoin", "text_ru": "💼 Премия на работе. +200 Ruzcoin", "effect": 200},
    {"text": "📚 Education payment. -50 Ruzcoin", "text_ru": "📚 Оплата обучения. -50 Ruzcoin", "effect": -50},
    {"text": "🎰 Casino win. +250 Ruzcoin", "text_ru": "🎰 Выигрыш в казино. +250 Ruzcoin", "effect": 250},
]

PLAYER_COLORS = [
    "#E74C3C", "#3498DB", "#2ECC71", "#F1C40F",
    "#9B59B6", "#E67E22", "#1ABC9C", "#FF69B4",
]

# ================== КЛАССЫ ==================
@dataclass
class Player:
    user_id: int
    name: str
    money: int = 1500
    position: int = 0
    color: str = "#FFFFFF"
    is_bot: bool = False
    in_jail: bool = False
    jail_turns: int = 0
    is_active: bool = True

    def pay(self, amount: int):
        self.money -= amount
        if self.money < 0:
            self.is_active = False
            self.money = 0

    def receive(self, amount: int):
        self.money += amount


@dataclass
class Room:
    code: str
    creator_id: int
    chat_id: int
    max_players: int
    password: Optional[str] = None
    players: Dict[int, Player] = field(default_factory=dict)
    ownership: Dict[int, int] = field(default_factory=dict)
    current_turn: int = 0
    is_started: bool = False
    last_message_id: Optional[int] = None
    chance_deck: list = field(default_factory=lambda: CHANCE_CARDS.copy())
    risk_deck: list = field(default_factory=lambda: RISK_CARDS.copy())
    awaiting_buy: Optional[int] = None
    turn_timer_task: Optional[asyncio.Task] = None
    language: str = 'en'

    def active_players(self) -> List[Player]:
        return [p for p in self.players.values() if p.is_active]

    def current_player(self) -> Optional[Player]:
        active = self.active_players()
        if not active:
            return None
        return active[self.current_turn % len(active)]

    def next_turn(self):
        active = self.active_players()
        if not active:
            return
        self.current_turn = (self.current_turn + 1) % len(active)


# ================== РАБОТА С БД ==================
class Database:
    @staticmethod
    def save_user(user_id: int, username: str, language: str = 'en'):
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM users WHERE id = ?", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            conn.execute("UPDATE users SET username = ? WHERE id = ?", (username, user_id))
        else:
            conn.execute(
                "INSERT INTO users (id, username, language) VALUES (?, ?, ?)",
                (user_id, username, language)
            )
        conn.commit()
        conn.close()

    @staticmethod
    def get_user_language(user_id: int) -> str:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 'en'

    @staticmethod
    def set_user_language(user_id: int, language: str):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("UPDATE users SET language = ? WHERE id = ?", (language, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def create_room(room: Room) -> bool:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                """INSERT INTO rooms 
                   (code, creator_id, chat_id, max_players, password, 
                    current_turn, is_started, last_message_id, 
                    chance_deck, risk_deck, awaiting_buy, language)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (room.code, room.creator_id, room.chat_id, room.max_players,
                 room.password, room.current_turn, room.is_started,
                 room.last_message_id, json.dumps(room.chance_deck),
                 json.dumps(room.risk_deck), room.awaiting_buy, room.language)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    @staticmethod
    def get_room(code: str) -> Optional[Room]:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rooms WHERE code = ?", (code,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        room = Room(
            code=row[0], creator_id=row[1], chat_id=row[2],
            max_players=row[3], password=row[4], current_turn=row[5],
            is_started=bool(row[6]), last_message_id=row[7],
            chance_deck=json.loads(row[8]) if row[8] else CHANCE_CARDS.copy(),
            risk_deck=json.loads(row[9]) if row[9] else RISK_CARDS.copy(),
            awaiting_buy=row[10], language=row[11] if len(row) > 11 else 'en'
        )

        cursor.execute("SELECT * FROM players WHERE room_code = ?", (code,))
        for p_row in cursor.fetchall():
            room.players[p_row[1]] = Player(
                user_id=p_row[1], name=p_row[2], money=p_row[3],
                position=p_row[4], color=p_row[5], is_bot=bool(p_row[6]),
                in_jail=bool(p_row[7]), jail_turns=p_row[8], is_active=bool(p_row[9])
            )

        cursor.execute("SELECT cell_idx, owner_id FROM ownership WHERE room_code = ?", (code,))
        for o_row in cursor.fetchall():
            room.ownership[o_row[0]] = o_row[1]

        conn.close()
        return room

    @staticmethod
    def update_room(room: Room):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            """UPDATE rooms SET 
               current_turn=?, is_started=?, last_message_id=?,
               chance_deck=?, risk_deck=?, awaiting_buy=?, language=?
               WHERE code=?""",
            (room.current_turn, room.is_started, room.last_message_id,
             json.dumps(room.chance_deck), json.dumps(room.risk_deck),
             room.awaiting_buy, room.language, room.code)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def add_player(room_code: str, player: Player) -> bool:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                """INSERT INTO players 
                   (room_code, user_id, name, money, position, color, 
                    is_bot, in_jail, jail_turns, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (room_code, player.user_id, player.name, player.money,
                 player.position, player.color, player.is_bot,
                 player.in_jail, player.jail_turns, player.is_active)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    @staticmethod
    def update_player(room_code: str, player: Player):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            """UPDATE players SET 
               money=?, position=?, in_jail=?, jail_turns=?, is_active=?
               WHERE room_code=? AND user_id=?""",
            (player.money, player.position, player.in_jail,
             player.jail_turns, player.is_active, room_code, player.user_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def set_ownership(room_code: str, cell_idx: int, owner_id: int):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT OR REPLACE INTO ownership (room_code, cell_idx, owner_id) VALUES (?, ?, ?)",
            (room_code, cell_idx, owner_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def set_user_room(user_id: int, room_code: str):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT OR REPLACE INTO user_room (user_id, room_code) VALUES (?, ?)",
            (user_id, room_code)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_user_room(user_id: int) -> Optional[str]:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT room_code FROM user_room WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    
    @staticmethod
    def get_all_rooms() -> List[Dict]:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT code, password, max_players FROM rooms WHERE is_started = 0")
        rooms = []
        for row in cursor.fetchall():
            cursor.execute("SELECT COUNT(*) FROM players WHERE room_code = ?", (row[0],))
            player_count = cursor.fetchone()[0]
            rooms.append({
                'code': row[0],
                'has_password': bool(row[1]),
                'max_players': row[2],
                'current_players': player_count
            })
        conn.close()
        return rooms


db = Database()

# ================== УТИЛИТЫ ==================
def generate_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_available_color(room: Room) -> str:
    used = {p.color for p in room.players.values()}
    available = [c for c in PLAYER_COLORS if c not in used]
    return random.choice(available) if available else "#FFFFFF"

def t(key: str, lang: str = 'en', **kwargs) -> str:
    """Translate key to language"""
    text = TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)
    if kwargs:
        return text.format(*[kwargs[k] for k in sorted(kwargs.keys())])
    return text


# ================== РЕНДЕР ПОЛЯ ==================
def render_board(room: Room) -> bytes:
    size = 900
    img = Image.new('RGB', (size, size), "#F5E9D3")
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_title = ImageFont.load_default()

    draw.text((size // 2 - 80, 20), "RUZOPOLY", fill="#2C3E50", font=font_title)

    cell = size / 11
    for idx in range(40):
        c = BOARD[idx]
        x1, y1, x2, y2 = _cell_rect(idx, cell)

        # Базовый цвет клетки
        bg = "#FFF8DC"
        if c["type"] == "go": bg = "#FFE4B5"
        elif c["type"] == "jail": bg = "#FFDAB9"
        elif c["type"] == "free_parking": bg = "#D3D3D3"
        elif c["type"] == "go_to_jail": bg = "#FFB6C1"
        elif c["type"] == "chance": bg = "#FFFACD"
        elif c["type"] == "risk": bg = "#FFE4E1"
        elif c["type"] == "chest": bg = "#E0FFFF"
        elif c["type"] == "tax": bg = "#F0E68C"

        # Если есть владелец, закрашиваем клетку его цветом с прозрачностью
        if idx in room.ownership:
            owner = room.players.get(room.ownership[idx])
            if owner:
                # Смешиваем цвет владельца с базовым цветом
                bg = owner.color

        draw.rectangle([x1, y1, x2, y2], fill=bg, outline="#333", width=2)

        # Рисуем полоску группы ПОВЕРХ цвета игрока
        if c["type"] == "property" and c.get("group") in GROUP_COLORS_HEX:
            group_col = GROUP_COLORS_HEX[c["group"]]
            if idx <= 10:
                draw.rectangle([x1 + 2, y2 - 14, x2 - 2, y2 - 2], fill=group_col)
            elif idx <= 20:
                draw.rectangle([x2 - 14, y1 + 2, x2 - 2, y2 - 2], fill=group_col)
            elif idx <= 30:
                draw.rectangle([x1 + 2, y1 + 2, x2 - 2, y1 + 14], fill=group_col)
            else:
                draw.rectangle([x1 + 2, y1 + 2, x1 + 14, y2 - 2], fill=group_col)

        draw.text((x1 + 4, y1 + 4), c["name"], fill="#000", font=font_big)
        if c["type"] == "property":
            draw.text((x1 + 4, y1 + 18), f"${c['price']}", fill="#555", font=font_small)

    # Рисуем фишки игроков
    active = room.active_players()
    for i, p in enumerate(active):
        x1, y1, x2, y2 = _cell_rect(p.position, cell)
        cx = x1 + 10 + (i % 3) * 14
        cy = y1 + 35 + (i // 3) * 14
        r = 8
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=p.color, outline="#000", width=2)
        draw.text((cx - 3, cy - 5), str(i + 1), fill="#FFF", font=font_small)

    # Центральная информация
    cx, cy = size // 2, size // 2
    draw.rectangle([cx - 150, cy - 80, cx + 150, cy + 80], fill="#FFF8DC", outline="#333", width=2)
    draw.text((cx - 140, cy - 70), "RUZOPOLY", fill="#2C3E50", font=font_title)

    cur = room.current_player()
    if cur and room.is_started:
        draw.text((cx - 140, cy - 30), f"Turn: {cur.name}", fill="#000", font=font_big)
        draw.text((cx - 140, cy - 10), f"Ruzcoin: {cur.money}", fill="#DAA520", font=font_big)
        draw.text((cx - 140, cy + 15), f"Position: {BOARD[cur.position]['name']}", fill="#000", font=font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def _cell_rect(idx: int, cell: float):
    if idx <= 10:
        col = 10 - idx
        row = 10
    elif idx <= 20:
        col = 0
        row = 10 - (idx - 10)
    elif idx <= 30:
        col = idx - 20
        row = 0
    else:
        col = 10
        row = idx - 30
    return col * cell, row * cell, (col + 1) * cell, (row + 1) * cell


# ================== FSM ==================
class CreateRoom(StatesGroup):
    wait_max = State()
    wait_password = State()


class JoinRoom(StatesGroup):
    wait_code = State()
    wait_password = State()


# ================== БОТ ==================
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)


# ================== ТАЙМЕР ХОДА ==================
async def turn_timeout(room_code: str):
    """Автоматический переход хода через 30 секунд"""
    await asyncio.sleep(30)
    room = db.get_room(room_code)
    if not room or not room.is_started:
        return
    
    cur = room.current_player()
    if cur and room.awaiting_buy is not None:
        await send_message(room, t('timeout', room.language).format(cur.name))
        await end_turn(room)


# ================== ОТПРАВКА ПОЛЯ ==================
async def send_board(room: Room, extra_text: str = ""):
    img_bytes = render_board(room)
    photo = BufferedInputFile(img_bytes, filename="board.png")

    cur = room.current_player()
    text = f"🎲 **RUZOPOLY** | Room: `{room.code}`\n"
    if cur:
        text += f"👤 Turn: **{cur.name}** ({cur.money} Ruzcoin)\n"
        text += f"📍 Position: {BOARD[cur.position]['name']}\n"
    if extra_text:
        text += f"\n{extra_text}"

    text += "\n\n💰 **Players:**\n"
    for p in room.players.values():
        marker = "👑" if p.user_id == (cur.user_id if cur else None) else "  "
        bot_mark = "🤖" if p.is_bot else "👤"
        active_mark = "" if p.is_active else " ❌"
        text += f"{marker} {bot_mark} {p.name}: {p.money} Ruzcoin{active_mark}\n"

    kb_buttons = []
    if cur and room.is_started:
        if not cur.is_bot:
            kb_buttons.append([InlineKeyboardButton(text=t('roll_dice', room.language), callback_data=f"roll_{room.code}")])
            if room.awaiting_buy is not None:
                cell = BOARD[room.awaiting_buy]
                kb_buttons.append([InlineKeyboardButton(
                    text=t('buy_property', room.language).format(cell['name'], cell['price']),
                    callback_data=f"buy_{room.code}")])
                kb_buttons.append([InlineKeyboardButton(text=t('skip', room.language), callback_data=f"skipbuy_{room.code}")])
            if cur.in_jail:
                kb_buttons.append([InlineKeyboardButton(text=t('pay_jail', room.language), callback_data=f"payjail_{room.code}")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons) if kb_buttons else None

    try:
        # Всегда отправляем новое сообщение вместо редактирования
        msg = await bot.send_photo(
            chat_id=room.chat_id, photo=photo, caption=text, parse_mode="Markdown", reply_markup=kb
        )
        room.last_message_id = msg.message_id
        db.update_room(room)
    except Exception as e:
        logging.error(f"Error sending board: {e}")


async def send_message(room: Room, text: str, reply_markup=None):
    return await bot.send_message(room.chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")


# ================== КОМАНДЫ ==================
@router.message(CommandStart())
async def cmd_start(message: Message):
    lang = db.get_user_language(message.from_user.id)
    db.save_user(message.from_user.id, message.from_user.username or message.from_user.full_name, lang)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
         InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
    ])
    await message.answer(t('welcome', lang), reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("lang_"))
async def cb_set_language(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    db.set_user_language(callback.from_user.id, lang)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('create_room', lang), callback_data="create_room")],
        [InlineKeyboardButton(text=t('join_by_code', lang), callback_data="join_room")],
        [InlineKeyboardButton(text=t('browse_rooms', lang), callback_data="browse_rooms")],
    ])
    await callback.message.edit_text(
        t('language_selected', lang),
        reply_markup=kb, parse_mode="Markdown"
    )


@router.callback_query(F.data == "browse_rooms")
async def cb_browse_rooms(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    rooms = db.get_all_rooms()
    if not rooms:
        await callback.message.edit_text(t('no_rooms', lang), 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t('create_room', lang), callback_data="create_room")],
                [InlineKeyboardButton(text=t('back', lang), callback_data="back_to_menu")]
            ]))
        return
    
    text = t('available_rooms', lang)
    kb_buttons = []
    
    for room in rooms:
        lock = "🔒" if room['has_password'] else "🔓"
        text += f"{lock} `{room['code']}` - {room['current_players']}/{room['max_players']} {t('players', lang)}\n"
        if not room['has_password']:
            kb_buttons.append([InlineKeyboardButton(
                text=t('join', lang).format(room['code']), 
                callback_data=f"quickjoin_{room['code']}")])
    
    kb_buttons.append([InlineKeyboardButton(text=t('refresh', lang), callback_data="browse_rooms")])
    kb_buttons.append([InlineKeyboardButton(text=t('back', lang), callback_data="back_to_menu")])
    
    await callback.message.edit_text(text, 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
        parse_mode="Markdown")


@router.callback_query(F.data.startswith("quickjoin_"))
async def cb_quick_join(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    
    if room.password:
        await callback.answer(t('room_has_password', lang), show_alert=True)
        return
    
    if len(room.players) >= room.max_players:
        await callback.answer(t('room_full', lang), show_alert=True)
        return
    
    if callback.from_user.id in room.players:
        await callback.answer(t('already_in_room', lang), show_alert=True)
        return
    
    color = get_available_color(room)
    player = Player(user_id=callback.from_user.id, name=callback.from_user.full_name, color=color)
    
    if not db.add_player(room.code, player):
        await callback.answer(t('room_full', lang), show_alert=True)
        return
    
    room.players[player.user_id] = player
    db.set_user_room(callback.from_user.id, room.code)
    
    await callback.answer(t('joined_room', lang).format(room.code))
    await send_message(room, t('joined_game', room.language).format(callback.from_user.full_name))
    await show_lobby(callback, room)


@router.callback_query(F.data == "back_to_menu")
async def cb_back_menu(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('create_room', lang), callback_data="create_room")],
        [InlineKeyboardButton(text=t('join_by_code', lang), callback_data="join_room")],
        [InlineKeyboardButton(text=t('browse_rooms', lang), callback_data="browse_rooms")],
    ])
    await callback.message.edit_text(
        t('welcome', lang),
        reply_markup=kb, parse_mode="Markdown"
    )


@router.callback_query(F.data == "create_room")
async def cb_create_room(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"2 {t('players', lang)}", callback_data="max_2"),
         InlineKeyboardButton(text=f"3 {t('players', lang)}", callback_data="max_3")],
        [InlineKeyboardButton(text=f"4 {t('players', lang)}", callback_data="max_4"),
         InlineKeyboardButton(text=f"6 {t('players', lang)}", callback_data="max_6")],
        [InlineKeyboardButton(text=f"8 {t('players', lang)}", callback_data="max_8")],
    ])
    await callback.message.edit_text(t('choose_max_players', lang), reply_markup=kb)
    await state.set_state(CreateRoom.wait_max)


@router.callback_query(F.data.startswith("max_"), StateFilter(CreateRoom.wait_max))
async def cb_max_players(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    max_p = int(callback.data.split("_")[1])
    await state.update_data(max_players=max_p)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('with_password', lang), callback_data="pass_yes")],
        [InlineKeyboardButton(text=t('no_password', lang), callback_data="pass_no")],
    ])
    await callback.message.edit_text(t('password_question', lang).format(max_p), reply_markup=kb)
    await state.set_state(CreateRoom.wait_password)


@router.callback_query(F.data == "pass_no", StateFilter(CreateRoom.wait_password))
async def cb_no_password(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await finalize_room(callback, None, data['max_players'], state)


@router.callback_query(F.data == "pass_yes", StateFilter(CreateRoom.wait_password))
async def cb_ask_password(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    await callback.message.edit_text(t('enter_password', lang))


@router.message(StateFilter(CreateRoom.wait_password))
async def msg_password(message: Message, state: FSMContext):
    data = await state.get_data()
    password = message.text.strip()
    await finalize_room_from_message(message, password, data['max_players'], state)


async def finalize_room(callback: CallbackQuery, password: Optional[str], max_players: int, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    code = generate_code()
    room = Room(
        code=code, creator_id=callback.from_user.id,
        chat_id=callback.message.chat.id, max_players=max_players,
        password=password, language=lang
    )
    color = get_available_color(room)
    player = Player(user_id=callback.from_user.id, name=callback.from_user.full_name, color=color)
    room.players[player.user_id] = player
    
    if not db.create_room(room):
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    
    db.add_player(code, player)
    db.set_user_room(callback.from_user.id, code)
    
    await state.clear()
    await show_lobby(callback.message, room)


async def finalize_room_from_message(message: Message, password: Optional[str], max_players: int, state: FSMContext):
    lang = db.get_user_language(message.from_user.id)
    code = generate_code()
    room = Room(
        code=code, creator_id=message.from_user.id,
        chat_id=message.chat.id, max_players=max_players,
        password=password, language=lang
    )
    
    color = get_available_color(room)
    player = Player(user_id=message.from_user.id, name=message.from_user.full_name, color=color)
    room.players[player.user_id] = player
    
    if not db.create_room(room):
        await message.answer(t('room_not_found', lang))
        return
    
    db.add_player(code, player)
    db.set_user_room(message.from_user.id, code)
    
    await state.clear()
    await show_lobby(message, room)


async def show_lobby(message_or_cb, room: Room):
    players_text = "\n".join([
        f"{'🤖' if p.is_bot else '👤'} {p.name}" for p in room.players.values()
    ])
    text = t('room_info', room.language).format(
        room.code,
        room.password or t('none', room.language),
        len(room.players),
        room.max_players,
        players_text
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('add_bot', room.language), callback_data=f"addbot_{room.code}")],
        [InlineKeyboardButton(text=t('start_game', room.language), callback_data=f"start_{room.code}")],
        [InlineKeyboardButton(text=t('refresh', room.language), callback_data=f"lobby_{room.code}")],
    ])
    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message_or_cb.answer(text, reply_markup=kb, parse_mode="Markdown")


# ================== ЛОББИ ==================
@router.callback_query(F.data.startswith("lobby_"))
async def cb_lobby(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    await show_lobby(callback, room)


@router.callback_query(F.data.startswith("addbot_"))
async def cb_add_bot(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    
    if len(room.players) >= room.max_players:
        await callback.answer(t('room_full', lang), show_alert=True)
        return
    
    bot_names = ["Alpha-Bot", "Beta-Bot", "Gamma-Bot", "Delta-Bot", "Epsilon-Bot"]
    name = random.choice(bot_names)
    color = get_available_color(room)
    bot_user_id = -random.randint(1000, 9999)
    
    player = Player(user_id=bot_user_id, name=f"🤖 {name}", color=color, is_bot=True)
    
    if not db.add_player(code, player):
        await callback.answer(t('room_full', lang), show_alert=True)
        return
    
    room.players[bot_user_id] = player
    await callback.answer(t('bot_added', lang).format(name))
    await show_lobby(callback, room)


@router.callback_query(F.data.startswith("start_"))
async def cb_start_game(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    
    # Проверка: только создатель может начать игру
    if callback.from_user.id != room.creator_id:
        await callback.answer(t('only_creator_start', lang), show_alert=True)
        return
    
    if len(room.players) < 2:
        await callback.answer(t('need_min_players', lang), show_alert=True)
        return
    
    room.is_started = True
    db.update_room(room)
    await callback.message.edit_text(t('game_starting', room.language))
    
    cur = room.current_player()
    if cur:
        await send_message(room, t('player_turn', room.language).format(cur.name))
    
    await send_board(room, t('game_started', room.language))
    await maybe_bot_turn(room)


# ================== ПРИСОЕДИНЕНИЕ ==================
@router.callback_query(F.data == "join_room")
async def cb_join_menu(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    await callback.message.edit_text(t('enter_room_code', lang))
    await state.set_state(JoinRoom.wait_code)


@router.message(Command("join"))
async def cmd_join(message: Message, state: FSMContext):
    lang = db.get_user_language(message.from_user.id)
    await message.answer(t('enter_room_code', lang))
    await state.set_state(JoinRoom.wait_code)


@router.message(StateFilter(JoinRoom.wait_code))
async def msg_join_code(message: Message, state: FSMContext):
    lang = db.get_user_language(message.from_user.id)
    code = message.text.strip().upper()
    room = db.get_room(code)
    if not room:
        await message.answer(t('room_not_found', lang))
        await state.clear()
        return
    
    if room.password:
        await state.update_data(join_code=code)
        await message.answer(t('room_has_password', lang))
        await state.set_state(JoinRoom.wait_password)
        return
    
    await do_join(message, room, state)


@router.message(StateFilter(JoinRoom.wait_password))
async def msg_join_password(message: Message, state: FSMContext):
    lang = db.get_user_language(message.from_user.id)
    data = await state.get_data()
    code = data.get("join_code")
    if not code:
        await state.clear()
        return
    
    room = db.get_room(code)
    if not room:
        await message.answer(t('room_not_found', lang))
        await state.clear()
        return
    
    if message.text.strip() != room.password:
        await message.answer(t('wrong_password', lang))
        return
    
    await do_join(message, room, state)


async def do_join(message: Message, room: Room, state: FSMContext):
    lang = db.get_user_language(message.from_user.id)
    
    if message.from_user.id in room.players:
        await message.answer(t('already_in_room', lang))
        await state.clear()
        return
    
    if len(room.players) >= room.max_players:
        await message.answer(t('room_full', lang))
        await state.clear()
        return
    
    color = get_available_color(room)
    player = Player(user_id=message.from_user.id, name=message.from_user.full_name, color=color)
    
    if not db.add_player(room.code, player):
        await message.answer(t('room_full', lang))
        await state.clear()
        return
    
    room.players[player.user_id] = player
    db.set_user_room(message.from_user.id, room.code)
    
    await state.clear()
    await message.answer(t('joined_room', lang).format(room.code), parse_mode="Markdown")
    await send_message(room, t('joined_game', room.language).format(message.from_user.full_name))
    await show_lobby(message, room)


# ================== ИГРОВАЯ ЛОГИКА ==================
@router.callback_query(F.data.startswith("roll_"))
async def cb_roll(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room or not room.is_started:
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != callback.from_user.id:
        await callback.answer(t('not_your_turn', lang), show_alert=True)
        return
    
    await callback.answer()
    await do_roll(room)


@router.message(Command("roll"))
async def cmd_roll(message: Message):
    lang = db.get_user_language(message.from_user.id)
    room_code = db.get_user_room(message.from_user.id)
    if not room_code:
        await message.answer("You're not in a game.")
        return
    
    room = db.get_room(room_code)
    if not room or not room.is_started:
        await message.answer("Game not started.")
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != message.from_user.id:
        await message.answer(t('not_your_turn', lang))
        return
    
    await do_roll(room)


async def do_roll(room: Room):
    cur = room.current_player()
    if not cur:
        return

    # Отменяем предыдущий таймер если есть
    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()

    if cur.in_jail:
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        if d1 == d2:
            cur.in_jail = False
            cur.jail_turns = 0
            db.update_player(room.code, cur)
            await send_message(room, t('jail_doubles', room.language).format(cur.name, d1, d2))
            await move_player(room, cur, d1 + d2)
        else:
            cur.jail_turns += 1
            db.update_player(room.code, cur)
            if cur.jail_turns >= 3:
                cur.pay(50)
                cur.in_jail = False
                cur.jail_turns = 0
                db.update_player(room.code, cur)
                await send_message(room, t('jail_pay_forced', room.language).format(cur.name))
                await move_player(room, cur, d1 + d2)
            else:
                await send_message(room, t('jail_no_doubles', room.language).format(cur.name, d1, d2, 3 - cur.jail_turns))
                room.next_turn()
                db.update_room(room)
                
                # Отправляем обновленное поле
                next_player = room.current_player()
                if next_player:
                    await send_message(room, t('player_turn', room.language).format(next_player.name))
                await send_board(room)
                await maybe_bot_turn(room)
        return

    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    await send_message(room, t('rolled', room.language).format(cur.name, d1, d2, total))
    await move_player(room, cur, total)


async def move_player(room: Room, player: Player, steps: int):
    old_pos = player.position
    new_pos = (player.position + steps) % 40

    if new_pos < old_pos and new_pos != 0:
        player.receive(200)
        db.update_player(room.code, player)
        await send_message(room, t('passed_start', room.language).format(player.name))

    player.position = new_pos
    db.update_player(room.code, player)
    
    # Обновляем поле после перемещения
    await send_board(room)
    await process_cell(room, player)


async def process_cell(room: Room, player: Player):
    cell = BOARD[player.position]
    ctype = cell["type"]

    if ctype == "go":
        await send_message(room, t('at_start', room.language).format(player.name))
        await end_turn(room)
    elif ctype == "property":
        await handle_property(room, player, cell)
    elif ctype == "chance":
        card = random.choice(room.chance_deck)
        await apply_card(room, player, card, "🎲 CHANCE")
    elif ctype == "risk":
        card = random.choice(room.risk_deck)
        await apply_card(room, player, card, "⚠️ RISK")
    elif ctype == "chest":
        amount = random.choice([50, 100, 150, 200])
        player.receive(amount)
        db.update_player(room.code, player)
        await send_message(room, t('chest_reward', room.language).format(player.name, amount))
        await send_board(room)
        await end_turn(room)
    elif ctype == "tax":
        player.pay(cell["amount"])
        db.update_player(room.code, player)
        await send_message(room, t('tax_paid', room.language).format(player.name, cell["amount"]))
        await send_board(room)
        await end_turn(room)
    elif ctype == "jail":
        await send_message(room, t('visiting_jail', room.language).format(player.name))
        await end_turn(room)
    elif ctype == "free_parking":
        await send_message(room, t('at_parking', room.language).format(player.name))
        await end_turn(room)
    elif ctype == "go_to_jail":
        player.position = 10
        player.in_jail = True
        player.jail_turns = 0
        db.update_player(room.code, player)
        await send_message(room, t('go_to_jail', room.language).format(player.name))
        await send_board(room)
        await end_turn(room)


async def handle_property(room: Room, player: Player, cell):
    idx = player.position
    if idx in room.ownership:
        owner_id = room.ownership[idx]
        if owner_id == player.user_id:
            await send_message(room, t('own_property', room.language).format(player.name, cell['name']))
            await end_turn(room)
        else:
            owner = room.players[owner_id]
            rent = cell["rent"]
            player.pay(rent)
            owner.receive(rent)
            db.update_player(room.code, player)
            db.update_player(room.code, owner)
            await send_message(room, t('rent_paid', room.language).format(player.name, rent, owner.name, cell['name']))
            await send_board(room)
            await end_turn(room)
    else:
        if player.money >= cell["price"]:
            room.awaiting_buy = idx
            db.update_room(room)
            await send_message(room, t('free_property', room.language).format(cell['name'], cell['price'], cell['rent']))
            await send_board(room)
            
            # Запускаем таймер на 30 секунд для всех игроков
            room.turn_timer_task = asyncio.create_task(turn_timeout(room.code))
            
            if player.is_bot:
                await asyncio.sleep(1.5)
                player.pay(cell["price"])
                room.ownership[idx] = player.user_id
                db.set_ownership(room.code, idx, player.user_id)
                room.awaiting_buy = None
                db.update_room(room)
                db.update_player(room.code, player)
                await send_message(room, t('property_bought', room.language).format(player.name, cell['name'], cell['price']))
                await send_board(room)
                await end_turn(room)
        else:
            await send_message(room, t('not_enough_money', room.language).format(player.name, cell['name']))
            await end_turn(room)


async def apply_card(room: Room, player: Player, card, title: str):
    # Отправляем текст карты как сообщение, а не на картинке
    card_text = card.get('text_ru' if room.language == 'ru' else 'text', card['text'])
    text = f"{title}: {card_text}"
    
    effect = card["effect"]
    if isinstance(effect, int):
        if effect > 0:
            player.receive(effect)
        else:
            player.pay(abs(effect))
        db.update_player(room.code, player)
    elif effect == "birthday":
        for p in room.active_players():
            if p.user_id != player.user_id:
                p.pay(50)
                player.receive(50)
                db.update_player(room.code, p)
        db.update_player(room.code, player)

    await send_message(room, text)
    await send_board(room)
    await end_turn(room)


async def end_turn(room: Room):
    # Отменяем таймер
    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()
    
    room.awaiting_buy = None
    room.next_turn()
    db.update_room(room)
    
    # Сообщаем о новом ходе
    cur = room.current_player()
    if cur:
        await send_message(room, t('player_turn', room.language).format(cur.name))
    
    await send_board(room)
    asyncio.create_task(maybe_bot_turn(room))


async def maybe_bot_turn(room: Room):
    for _ in range(len(room.players)):
        cur = room.current_player()
        if not cur:
            return
        if not cur.is_active:
            room.next_turn()
            db.update_room(room)
            continue
        if cur.is_bot and room.is_started:
            await asyncio.sleep(2)
            await do_roll(room)
            return
        break


@router.callback_query(F.data.startswith("buy_"))
async def cb_buy(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != callback.from_user.id:
        await callback.answer(t('not_your_turn', lang), show_alert=True)
        return
    
    if room.awaiting_buy is None:
        await callback.answer(t('nothing_to_buy', lang), show_alert=True)
        return
    
    idx = room.awaiting_buy
    cell = BOARD[idx]
    if cur.money < cell["price"]:
        await callback.answer(t('not_enough_ruzcoin', lang), show_alert=True)
        return
    
    cur.pay(cell["price"])
    room.ownership[idx] = cur.user_id
    db.set_ownership(room.code, idx, cur.user_id)
    room.awaiting_buy = None
    db.update_room(room)
    db.update_player(room.code, cur)
    
    await callback.answer()
    await send_message(room, t('property_bought', room.language).format(cur.name, cell['name'], cell['price']))
    await send_board(room)
    await end_turn(room)


@router.callback_query(F.data.startswith("skipbuy_"))
async def cb_skip_buy(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != callback.from_user.id:
        await callback.answer(t('not_your_turn', room.language), show_alert=True)
        return
    
    room.awaiting_buy = None
    db.update_room(room)
    await callback.answer()
    await send_message(room, t('purchase_declined', room.language).format(callback.from_user.full_name))
    await end_turn(room)


@router.callback_query(F.data.startswith("payjail_"))
async def cb_pay_jail(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != callback.from_user.id:
        await callback.answer(t('not_your_turn', lang), show_alert=True)
        return
    
    if cur.money < 50:
        await callback.answer(t('not_enough_ruzcoin', lang), show_alert=True)
        return
    
    cur.pay(50)
    cur.in_jail = False
    cur.jail_turns = 0
    db.update_player(room.code, cur)
    
    await callback.answer()
    await send_message(room, t('jail_paid_out', room.language).format(cur.name))
    await send_board(room)
    await do_roll(room)


@router.message(Command("buyout"))
async def cmd_buyout(message: Message):
    room_code = db.get_user_room(message.from_user.id)
    lang = db.get_user_language(message.from_user.id)
    if not room_code:
        await message.answer("You're not in a game.")
        return
    
    room = db.get_room(room_code)
    if not room or not room.is_started:
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != message.from_user.id:
        await message.answer(t('not_your_turn', lang))
        return
    
    if room.awaiting_buy is None:
        await message.answer(t('nothing_to_buy', lang))
        return
    
    idx = room.awaiting_buy
    cell = BOARD[idx]
    price = cell["price"] * 2
    
    if cur.money < price:
        await message.answer(f"{t('not_enough_ruzcoin', lang)}. Need: {price}")
        return
    
    owner_id = room.ownership.get(idx)
    if owner_id == cur.user_id:
        await message.answer(t('own_property', lang).format("This", "your property"))
        return
    
    if owner_id:
        owner = room.players.get(owner_id)
        if owner:
            owner.receive(price)
            db.update_player(room.code, owner)
    
    cur.pay(price)
    room.ownership[idx] = cur.user_id
    db.set_ownership(room.code, idx, cur.user_id)
    room.awaiting_buy = None
    db.update_room(room)
    db.update_player(room.code, cur)
    
    await send_message(room, f"💼 **{cur.name}** forcibly bought **{cell['name']}** for {price} Ruzcoin!")
    await send_board(room)
    await end_turn(room)


# ================== ИНФО ==================
@router.message(Command("room"))
async def cmd_room(message: Message):
    room_code = db.get_user_room(message.from_user.id)
    if not room_code:
        await message.answer("You're not in a room. Use /create or /join")
        return
    
    room = db.get_room(room_code)
    if not room:
        await message.answer("Room not found.")
        return
    
    await show_lobby(message, room)


@router.message(Command("board"))
async def cmd_board(message: Message):
    room_code = db.get_user_room(message.from_user.id)
    if not room_code:
        await message.answer("You're not in a game.")
        return
    
    room = db.get_room(room_code)
    if not room:
        await message.answer("Room not found.")
        return
    
    await send_board(room)


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = db.get_user_language(message.from_user.id)
    text = (
        "🎩 **RUZOPOLY - Commands**\n\n"
        "/start - Start\n"
        "/create - Create room\n"
        "/join - Join by code\n"
        "/room - Room info\n"
        "/board - Show board\n"
        "/roll - Roll dice\n"
        "/buyout - Force buyout property\n"
        "/help - This help\n\n"
        "💰 Currency: **Ruzcoin**\n"
        "🎲 Rules like classic Monopoly!"
    )
    await message.answer(text, parse_mode="Markdown")


# ================== ЗАПУСК ==================
async def main():
    print("🚀 Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
