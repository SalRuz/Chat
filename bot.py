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
from typing import Dict, List, Optional, Tuple, Set
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
        'allow_buyout_question': "Allow forced property buyout?",
        'allow_buyout': "✅ Allow Buyout",
        'no_buyout': "❌ No Buyout",
        'choose_turn_time': "⏰ Choose turn time:",
        'seconds_15': "15 seconds",
        'seconds_30': "30 seconds",
        'seconds_60': "1 minute",
        'room_info': "🏠 **Ruzopoly Room**\n🔑 Code: `{}`\n🔒 Password: `{}`\n👥 Players: {}/{}\n💼 Buyout: {}\n⏰ Turn time: {}s\n\n{}\n\nWaiting for players...",
        'enabled': 'Enabled',
        'disabled': 'Disabled',
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
        'buy_property': "💵 Buy {} (${})",
        'buyout_property': "💎 Buyout {} (${})",
        'sell_property': "💰 Sell {}",
        'skip': "❌ Skip",
        'pay_jail': "💰 Pay $150 to exit",
        'not_your_turn': "Not your turn",
        'rolled': "🎲 {} rolled: {} + {} = {}",
        'doubles': "🎲 {} rolled DOUBLES! Can roll again!",
        'third_double': "🎲 {} rolled 3rd DOUBLE! Go to JAIL!",
        'passed_start': "💰 {} passed START and received $200!",
        'at_start': "🏁 {} at START.",
        'chest_reward': "💎 {} received ${} from Chest!",
        'tax_paid': "💸 {} pays tax ${}.",
        'visiting_jail': "👀 {} just visiting jail.",
        'at_parking': "🅿️ {} resting at parking.",
        'go_to_jail': "🚔 {} goes to JAIL!",
        'rent_paid': "💰 {} pays ${} to **{}** for {}.",
        'own_property': "🏠 {} on their property: {}",
        'free_property': "🏡 Free property: **{}**\n💵 Price: ${}\n🏷️ Rent: ${}",
        'not_enough_money': "💸 {} doesn't have enough money.",
        'property_bought': "✅ {} bought {} for ${}!",
        'property_buyout': "💎 {} bought out {} from {} for ${}!",
        'purchase_declined': "❌ {} declined the purchase.",
        'timeout': "⏰ Time's up! {}'s turn skipped.",
        'jail_doubles': "🎲 {} rolled {}+{} (doubles!) and got out of jail!",
        'jail_no_doubles': "🎲 {} in jail. Rolled {}+{}. Attempts left: {}",
        'jail_pay_forced': "🎲 {} didn't roll doubles for 3 turns. Pays $150 and exits.",
        'jail_paid_out': "💰 {} paid $150 and got out of jail!",
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
        'not_enough_ruzcoin': "Not enough money",
        'nothing_to_buy': "Nothing to buy",
        'language_selected': "Language set to English! 🇬🇧",
        'player_eliminated': "💀 {} eliminated from the game!",
        'player_won': "🏆 {} WON THE GAME!",
        'game_over': "🎮 Game Over!",
        'debt_warning': "⚠️ {} in debt! Must sell properties or be eliminated.",
        'property_sold': "💰 {} sold {} for ${}.",
        'all_stations_owned': "🚉 {} owns all stations and wins!",
        'moving_countdown': "⏱️ Moving in {} seconds...",
        'turn_end_countdown': "⏱️ Turn ends in {} seconds...",
        'decision_time': "⏱️ Decision time: {} seconds left",
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
        'allow_buyout_question': "Разрешить принудительный выкуп территорий?",
        'allow_buyout': "✅ Разрешить",
        'no_buyout': "❌ Запретить",
        'choose_turn_time': "⏰ Выберите время на ход:",
        'seconds_15': "15 секунд",
        'seconds_30': "30 секунд",
        'seconds_60': "1 минута",
        'room_info': "🏠 **Комната Ruzopoly**\n🔑 Код: `{}`\n🔒 Пароль: `{}`\n👥 Игроки: {}/{}\n💼 Выкуп: {}\n⏰ Время хода: {}с\n\n{}\n\nОжидаем игроков...",
        'enabled': 'Включен',
        'disabled': 'Выключен',
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
        'buy_property': "💵 Купить {} (${})",
        'buyout_property': "💎 Выкупить {} (${})",
        'sell_property': "💰 Продать {}",
        'skip': "❌ Пропустить",
        'pay_jail': "💰 Заплатить $150 и выйти",
        'not_your_turn': "Сейчас не ваш ход",
        'rolled': "🎲 {} выбросил: {} + {} = {}",
        'doubles': "🎲 {} выбросил ДУБЛЬ! Может бросить снова!",
        'third_double': "🎲 {} выбросил 3-й ДУБЛЬ! Отправляется в ТЮРЬМУ!",
        'passed_start': "💰 {} прошёл через СТАРТ и получил $200!",
        'at_start': "🏁 {} на СТАРТЕ.",
        'chest_reward': "💎 {} получил ${} из Казны!",
        'tax_paid': "💸 {} платит налог ${}.",
        'visiting_jail': "👀 {} просто навещает тюрьму.",
        'at_parking': "🅿️ {} отдыхает на парковке.",
        'go_to_jail': "🚔 {} отправляется в ТЮРЬМУ!",
        'rent_paid': "💰 {} платит ${} игроку **{}** за {}.",
        'own_property': "🏠 {} на своей территории: {}",
        'free_property': "🏡 Свободная территория: **{}**\n💵 Цена: ${}\n🏷️ Рента: ${}",
        'not_enough_money': "💸 У {} недостаточно денег.",
        'property_bought': "✅ {} купил {} за ${}!",
        'property_buyout': "💎 {} выкупил {} у {} за ${}!",
        'purchase_declined': "❌ {} отказался от покупки.",
        'timeout': "⏰ Время вышло! Ход {} пропущен.",
        'jail_doubles': "🎲 {} выбросил {}+{} (дубль!) и вышел из тюрьмы!",
        'jail_no_doubles': "🎲 {} в тюрьме. Выпало {}+{}. Осталось попыток: {}",
        'jail_pay_forced': "🎲 {} не выбросил дубль за 3 хода. Платит $150 и выходит.",
        'jail_paid_out': "💰 {} заплатил $150 и вышел из тюрьмы!",
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
        'not_enough_ruzcoin': "Недостаточно денег",
        'nothing_to_buy': "Нечего покупать",
        'language_selected': "Язык установлен на Русский! 🇷🇺",
        'player_eliminated': "💀 {} выбыл из игры!",
        'player_won': "🏆 {} ПОБЕДИЛ!",
        'game_over': "🎮 Игра окончена!",
        'debt_warning': "⚠️ {} в долгах! Необходимо продать территории или выбыть.",
        'property_sold': "💰 {} продал {} за ${}.",
        'all_stations_owned': "🚉 {} владеет всеми станциями и побеждает!",
        'moving_countdown': "⏱️ Перемещение через {} сек...",
        'turn_end_countdown': "⏱️ Ход завершится через {} сек...",
        'decision_time': "⏱️ Время на решение: {} сек",
    }
}

def init_db():
    """Database initialization with migration support"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    users_exists = cursor.fetchone() is not None
    
    if users_exists:
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'language' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en'")
            print("✅ Added 'language' column to users table")
    else:
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'en',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Created users table")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
    rooms_exists = cursor.fetchone() is not None
    
    if rooms_exists:
        cursor.execute("PRAGMA table_info(rooms)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'language' not in columns:
            cursor.execute("ALTER TABLE rooms ADD COLUMN language TEXT DEFAULT 'en'")
        if 'player_ids' not in columns:
            cursor.execute("ALTER TABLE rooms ADD COLUMN player_ids TEXT DEFAULT '[]'")
        if 'allow_buyout' not in columns:
            cursor.execute("ALTER TABLE rooms ADD COLUMN allow_buyout BOOLEAN DEFAULT 1")
        if 'turn_time' not in columns:
            cursor.execute("ALTER TABLE rooms ADD COLUMN turn_time INTEGER DEFAULT 30")
    else:
        cursor.execute('''
            CREATE TABLE rooms (
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
                player_ids TEXT DEFAULT '[]',
                allow_buyout BOOLEAN DEFAULT 1,
                turn_time INTEGER DEFAULT 30,
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
            doubles_count INTEGER DEFAULT 0,
            PRIMARY KEY (room_code, user_id),
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
    
    # Добавляем колонку doubles_count если её нет
    cursor.execute("PRAGMA table_info(players)")
    player_columns = [column[1] for column in cursor.fetchall()]
    if 'doubles_count' not in player_columns:
        cursor.execute("ALTER TABLE players ADD COLUMN doubles_count INTEGER DEFAULT 0")
        print("✅ Added 'doubles_count' column to players table")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ownership (
            room_code TEXT NOT NULL,
            cell_idx INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            houses INTEGER DEFAULT 0,
            PRIMARY KEY (room_code, cell_idx),
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
    
    cursor.execute("PRAGMA table_info(ownership)")
    ownership_columns = [column[1] for column in cursor.fetchall()]
    if 'houses' not in ownership_columns:
        cursor.execute("ALTER TABLE ownership ADD COLUMN houses INTEGER DEFAULT 0")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_room (
            user_id INTEGER PRIMARY KEY,
            room_code TEXT NOT NULL,
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_messages (
            room_code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            PRIMARY KEY (room_code, user_id),
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DB_PATH}")

init_db()

# ================== ДАННЫЕ ПОЛЯ (оригинальные цены Monopoly) ==================
GROUP_COLORS_HEX = {
    "brown": "#8B4513", "lightblue": "#87CEEB", "pink": "#FF69B4",
    "orange": "#FFA500", "red": "#FF3030", "yellow": "#FFD700",
    "green": "#2E8B57", "darkblue": "#1E3A8A",
}

BOARD = [
    {"name": "START", "type": "go"},
    {"name": "Mediterranean Ave", "type": "property", "group": "brown", "price": 60, "rent": [2, 10, 30, 90, 160, 250], "house": 50},
    {"name": "Chest", "type": "chest"},
    {"name": "Baltic Ave", "type": "property", "group": "brown", "price": 60, "rent": [4, 20, 60, 180, 320, 450], "house": 50},
    {"name": "Income Tax", "type": "tax", "amount": 200},
    {"name": "Reading Railroad", "type": "property", "group": "station", "price": 200, "rent": [25, 50, 100, 200]},
    {"name": "Oriental Ave", "type": "property", "group": "lightblue", "price": 100, "rent": [6, 30, 90, 270, 400, 550], "house": 50},
    {"name": "Chance", "type": "chance"},
    {"name": "Vermont Ave", "type": "property", "group": "lightblue", "price": 100, "rent": [6, 30, 90, 270, 400, 550], "house": 50},
    {"name": "Connecticut Ave", "type": "property", "group": "lightblue", "price": 120, "rent": [8, 40, 100, 300, 450, 600], "house": 50},
    {"name": "JAIL", "type": "jail"},
    {"name": "St. Charles Place", "type": "property", "group": "pink", "price": 140, "rent": [10, 50, 150, 450, 625, 750], "house": 100},
    {"name": "Electric Company", "type": "property", "group": "utility", "price": 150, "rent": [4, 10]},
    {"name": "States Ave", "type": "property", "group": "pink", "price": 140, "rent": [10, 50, 150, 450, 625, 750], "house": 100},
    {"name": "Virginia Ave", "type": "property", "group": "pink", "price": 160, "rent": [12, 60, 180, 500, 700, 900], "house": 100},
    {"name": "Pennsylvania Railroad", "type": "property", "group": "station", "price": 200, "rent": [25, 50, 100, 200]},
    {"name": "St. James Place", "type": "property", "group": "orange", "price": 180, "rent": [14, 70, 200, 550, 750, 950], "house": 100},
    {"name": "Risk", "type": "risk"},
    {"name": "Tennessee Ave", "type": "property", "group": "orange", "price": 180, "rent": [14, 70, 200, 550, 750, 950], "house": 100},
    {"name": "New York Ave", "type": "property", "group": "orange", "price": 200, "rent": [16, 80, 220, 600, 800, 1000], "house": 100},
    {"name": "PARKING", "type": "free_parking"},
    {"name": "Kentucky Ave", "type": "property", "group": "red", "price": 220, "rent": [18, 90, 250, 700, 875, 1050], "house": 150},
    {"name": "Chance", "type": "chance"},
    {"name": "Indiana Ave", "type": "property", "group": "red", "price": 220, "rent": [18, 90, 250, 700, 875, 1050], "house": 150},
    {"name": "Illinois Ave", "type": "property", "group": "red", "price": 240, "rent": [20, 100, 300, 750, 925, 1100], "house": 150},
    {"name": "B&O Railroad", "type": "property", "group": "station", "price": 200, "rent": [25, 50, 100, 200]},
    {"name": "Atlantic Ave", "type": "property", "group": "yellow", "price": 260, "rent": [22, 110, 330, 800, 975, 1150], "house": 150},
    {"name": "Ventnor Ave", "type": "property", "group": "yellow", "price": 260, "rent": [22, 110, 330, 800, 975, 1150], "house": 150},
    {"name": "Water Works", "type": "property", "group": "utility", "price": 150, "rent": [4, 10]},
    {"name": "Marvin Gardens", "type": "property", "group": "yellow", "price": 280, "rent": [24, 120, 360, 850, 1025, 1200], "house": 150},
    {"name": "GO TO JAIL", "type": "go_to_jail"},
    {"name": "Pacific Ave", "type": "property", "group": "green", "price": 300, "rent": [26, 130, 390, 900, 1100, 1275], "house": 200},
    {"name": "North Carolina Ave", "type": "property", "group": "green", "price": 300, "rent": [26, 130, 390, 900, 1100, 1275], "house": 200},
    {"name": "Chest", "type": "chest"},
    {"name": "Pennsylvania Ave", "type": "property", "group": "green", "price": 320, "rent": [28, 150, 450, 1000, 1200, 1400], "house": 200},
    {"name": "Short Line Railroad", "type": "property", "group": "station", "price": 200, "rent": [25, 50, 100, 200]},
    {"name": "Chance", "type": "chance"},
    {"name": "Park Place", "type": "property", "group": "darkblue", "price": 350, "rent": [35, 175, 500, 1100, 1300, 1500], "house": 200},
    {"name": "Luxury Tax", "type": "tax", "amount": 100},
    {"name": "Boardwalk", "type": "property", "group": "darkblue", "price": 400, "rent": [50, 200, 600, 1400, 1700, 2000], "house": 200},
]

CHANCE_CARDS = [
    {"text": "🎉 You won the lottery! +$200", "text_ru": "🎉 Вы выиграли в лотерею! +$200", "effect": 200},
    {"text": "🚗 Parking fine. -$50", "text_ru": "🚗 Штраф за парковку. -$50", "effect": -50},
    {"text": "🏦 Bank dividends +$100", "text_ru": "🏦 Банковские дивиденды +$100", "effect": 100},
    {"text": "🚓 Traffic fine. -$100", "text_ru": "🚓 Штраф ГИБДД. -$100", "effect": -100},
    {"text": "🎂 Birthday! Each player pays you $50", "text_ru": "🎂 День рождения! Каждый игрок платит вам по $50", "effect": "birthday"},
    {"text": "🏃 Go to START. +$200", "text_ru": "🏃 Переход на СТАРТ. +$200", "effect": 200, "move_to": 0},
    {"text": "📈 Stocks went up. +$150", "text_ru": "📈 Акции выросли. +$150", "effect": 150},
    {"text": "🔧 Property repairs. -$100", "text_ru": "🔧 Ремонт имущества. -$100", "effect": -100},
]

RISK_CARDS = [
    {"text": "💸 Luxury tax. -$150", "text_ru": "💸 Налог на роскошь. -$150", "effect": -150},
    {"text": "🎁 Gift from uncle. +$100", "text_ru": "🎁 Подарок от дяди. +$100", "effect": 100},
    {"text": "🏥 Hospital payment. -$100", "text_ru": "🏥 Оплата больницы. -$100", "effect": -100},
    {"text": "💼 Work bonus. +$200", "text_ru": "💼 Премия на работе. +$200", "effect": 200},
    {"text": "📚 Education payment. -$50", "text_ru": "📚 Оплата обучения. -$50", "effect": -50},
    {"text": "🎰 Casino win. +$250", "text_ru": "🎰 Выигрыш в казино. +$250", "effect": 250},
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
    doubles_count: int = 0

    def pay(self, amount: int):
        self.money -= amount

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
    ownership: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    current_turn: int = 0
    is_started: bool = False
    last_message_id: Optional[int] = None
    chance_deck: list = field(default_factory=lambda: CHANCE_CARDS.copy())
    risk_deck: list = field(default_factory=lambda: RISK_CARDS.copy())
    awaiting_buy: Optional[int] = None
    awaiting_buyout: bool = False
    turn_timer_task: Optional[asyncio.Task] = None
    language: str = 'en'
    player_ids: Set[int] = field(default_factory=set)
    allow_buyout: bool = True
    turn_time: int = 30
    event_log: List[str] = field(default_factory=list)
    player_message_ids: Dict[int, int] = field(default_factory=dict)
    countdown_seconds: int = 0
    is_moving: bool = False
    can_roll: bool = True

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

    def add_event(self, event: str):
        self.event_log.append(event)
        if len(self.event_log) > 10:
            self.event_log.pop(0)


# ================== РАБОТА С БД (сокращенная версия для экономии места) ==================
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
            conn.execute("INSERT INTO users (id, username, language) VALUES (?, ?, ?)", (user_id, username, language))
        conn.commit()
        conn.close()

    @staticmethod
    def get_user_language(user_id: int) -> str:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT language FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 'en'
        except:
            return 'en'
        finally:
            conn.close()

    @staticmethod
    def set_user_language(user_id: int, language: str):
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute("UPDATE users SET language = ? WHERE id = ?", (language, user_id))
            conn.commit()
        except:
            pass
        finally:
            conn.close()

    @staticmethod
    def create_room(room: Room) -> bool:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                """INSERT INTO rooms 
                   (code, creator_id, chat_id, max_players, password, current_turn, is_started, last_message_id, 
                    chance_deck, risk_deck, awaiting_buy, language, player_ids, allow_buyout, turn_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (room.code, room.creator_id, room.chat_id, room.max_players, room.password, room.current_turn, room.is_started,
                 room.last_message_id, json.dumps(room.chance_deck), json.dumps(room.risk_deck), room.awaiting_buy, room.language,
                 json.dumps(list(room.player_ids)), room.allow_buyout, room.turn_time)
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
            code=row[0], creator_id=row[1], chat_id=row[2], max_players=row[3], password=row[4], current_turn=row[5],
            is_started=bool(row[6]), last_message_id=row[7],
            chance_deck=json.loads(row[8]) if row[8] else CHANCE_CARDS.copy(),
            risk_deck=json.loads(row[9]) if row[9] else RISK_CARDS.copy(),
            awaiting_buy=row[10], language=row[11] if len(row) > 11 else 'en',
            player_ids=set(json.loads(row[12])) if len(row) > 12 else set(),
            allow_buyout=bool(row[13]) if len(row) > 13 else True,
            turn_time=row[14] if len(row) > 14 else 30
        )

        cursor.execute("SELECT * FROM players WHERE room_code = ?", (code,))
        for p_row in cursor.fetchall():
            room.players[p_row[1]] = Player(
                user_id=p_row[1], name=p_row[2], money=p_row[3], position=p_row[4], color=p_row[5], is_bot=bool(p_row[6]),
                in_jail=bool(p_row[7]), jail_turns=p_row[8], is_active=bool(p_row[9]),
                doubles_count=p_row[10] if len(p_row) > 10 else 0
            )
            room.player_ids.add(p_row[1])

        cursor.execute("SELECT cell_idx, owner_id, houses FROM ownership WHERE room_code = ?", (code,))
        for o_row in cursor.fetchall():
            houses = o_row[2] if len(o_row) > 2 else 0
            room.ownership[o_row[0]] = (o_row[1], houses)

        cursor.execute("SELECT user_id, message_id FROM player_messages WHERE room_code = ?", (code,))
        for msg_row in cursor.fetchall():
            room.player_message_ids[msg_row[0]] = msg_row[1]

        conn.close()
        return room

    @staticmethod
    def update_room(room: Room):
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                """UPDATE rooms SET current_turn=?, is_started=?, last_message_id=?,
                   chance_deck=?, risk_deck=?, awaiting_buy=?, language=?, player_ids=?, allow_buyout=?, turn_time=?
                   WHERE code=?""",
                (room.current_turn, room.is_started, room.last_message_id, json.dumps(room.chance_deck), json.dumps(room.risk_deck),
                 room.awaiting_buy, room.language, json.dumps(list(room.player_ids)), room.allow_buyout, room.turn_time, room.code)
            )
            conn.commit()
        except:
            pass
        finally:
            conn.close()

    @staticmethod
    def add_player(room_code: str, player: Player) -> bool:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                """INSERT INTO players (room_code, user_id, name, money, position, color, is_bot, in_jail, jail_turns, is_active, doubles_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (room_code, player.user_id, player.name, player.money, player.position, player.color, player.is_bot,
                 player.in_jail, player.jail_turns, player.is_active, player.doubles_count)
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
            """UPDATE players SET money=?, position=?, in_jail=?, jail_turns=?, is_active=?, doubles_count=?
               WHERE room_code=? AND user_id=?""",
            (player.money, player.position, player.in_jail, player.jail_turns, player.is_active, player.doubles_count, room_code, player.user_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def set_ownership(room_code: str, cell_idx: int, owner_id: int, houses: int = 0):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("INSERT OR REPLACE INTO ownership (room_code, cell_idx, owner_id, houses) VALUES (?, ?, ?, ?)",
                    (room_code, cell_idx, owner_id, houses))
        conn.commit()
        conn.close()

    @staticmethod
    def remove_ownership(room_code: str, cell_idx: int):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("DELETE FROM ownership WHERE room_code = ? AND cell_idx = ?", (room_code, cell_idx))
        conn.commit()
        conn.close()

    @staticmethod
    def set_user_room(user_id: int, room_code: str):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("INSERT OR REPLACE INTO user_room (user_id, room_code) VALUES (?, ?)", (user_id, room_code))
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
            rooms.append({'code': row[0], 'has_password': bool(row[1]), 'max_players': row[2], 'current_players': player_count})
        conn.close()
        return rooms

    @staticmethod
    def set_player_message_id(room_code: str, user_id: int, message_id: int):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("INSERT OR REPLACE INTO player_messages (room_code, user_id, message_id) VALUES (?, ?, ?)",
                    (room_code, user_id, message_id))
        conn.commit()
        conn.close()


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
        try:
            return text.format(*[kwargs[k] for k in sorted(kwargs.keys())])
        except:
            return text
    return text

def calculate_rent(cell: dict, houses: int, owner_stations_count: int = 1, dice_sum: int = 0) -> int:
    """Расчёт ренты по правилам оригинальной Monopoly"""
    if cell.get("group") == "station":
        return cell["rent"][min(owner_stations_count - 1, 3)]
    elif cell.get("group") == "utility":
        multiplier = cell["rent"][0] if owner_stations_count == 1 else cell["rent"][1]
        return multiplier * dice_sum
    else:
        # Обычная территория
        return cell["rent"][min(houses, 5)]

def calculate_buyout_price(cell: dict, houses: int) -> int:
    """Расчёт цены выкупа территории"""
    base_price = cell.get("price", 0)
    house_value = houses * cell.get("house", 50)
    return int(base_price * 1.5 + house_value)

def calculate_sell_price(cell: dict, houses: int) -> int:
    """Расчёт цены продажи территории"""
    base_price = cell.get("price", 0)
    house_value = houses * cell.get("house", 50) * 0.5
    return int(base_price * 0.5 + house_value)

def get_player_properties(room: Room, player_id: int) -> List[Tuple[int, dict, int]]:
    """Получить все территории игрока"""
    properties = []
    for cell_idx, (owner_id, houses) in room.ownership.items():
        if owner_id == player_id:
            cell = BOARD[cell_idx]
            if cell["type"] == "property":
                properties.append((cell_idx, cell, houses))
    return properties

def count_owned_stations(room: Room, player_id: int) -> int:
    """Подсчет количества станций игрока"""
    stations = [i for i, cell in enumerate(BOARD) if cell.get("group") == "station"]
    return sum(1 for idx in stations if idx in room.ownership and room.ownership[idx][0] == player_id)

def count_owned_utilities(room: Room, player_id: int) -> int:
    """Подсчет количества коммунальных служб игрока"""
    utilities = [i for i, cell in enumerate(BOARD) if cell.get("group") == "utility"]
    return sum(1 for idx in utilities if idx in room.ownership and room.ownership[idx][0] == player_id)

def check_all_stations_owned(room: Room, player_id: int) -> bool:
    """Проверка владения всеми станциями"""
    stations = [i for i, cell in enumerate(BOARD) if cell.get("group") == "station"]
    owned_stations = sum(1 for idx in stations if idx in room.ownership and room.ownership[idx][0] == player_id)
    return owned_stations == len(stations)
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

    cell_size = size / 11
    for idx in range(40):
        c = BOARD[idx]
        x1, y1, x2, y2 = _cell_rect(idx, cell_size)

        bg = "#FFF8DC"
        if c["type"] == "go": bg = "#FFE4B5"
        elif c["type"] == "jail": bg = "#FFDAB9"
        elif c["type"] == "free_parking": bg = "#D3D3D3"
        elif c["type"] == "go_to_jail": bg = "#FFB6C1"
        elif c["type"] == "chance": bg = "#FFFACD"
        elif c["type"] == "risk": bg = "#FFE4E1"
        elif c["type"] == "chest": bg = "#E0FFFF"
        elif c["type"] == "tax": bg = "#F0E68C"

        if idx in room.ownership:
            owner_id, houses = room.ownership[idx]
            owner = room.players.get(owner_id)
            if owner:
                bg = owner.color

        draw.rectangle([x1, y1, x2, y2], fill=bg, outline="#333", width=2)

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

        if idx in room.ownership:
            owner_id, houses = room.ownership[idx]
            if houses > 0:
                house_text = "🏠" * min(houses, 4) if houses < 5 else "🏨"
                draw.text((x1 + 4, y1 + 30), house_text, fill="#000", font=font_small)

        draw.text((x1 + 4, y1 + 4), c["name"], fill="#000", font=font_big)
        if c["type"] == "property":
            draw.text((x1 + 4, y1 + 18), f"${c['price']}", fill="#555", font=font_small)

    active = room.active_players()
    for i, p in enumerate(active):
        x1, y1, x2, y2 = _cell_rect(p.position, cell_size)
        cx = x1 + 10 + (i % 3) * 14
        cy = y1 + 35 + (i // 3) * 14
        r = 8
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=p.color, outline="#000", width=2)
        draw.text((cx - 3, cy - 5), str(i + 1), fill="#FFF", font=font_small)

    cx, cy = size // 2, size // 2
    draw.rectangle([cx - 150, cy - 80, cx + 150, cy + 80], fill="#FFF8DC", outline="#333", width=2)
    draw.text((cx - 140, cy - 70), "RUZOPOLY", fill="#2C3E50", font=font_title)

    cur = room.current_player()
    if cur and room.is_started:
        draw.text((cx - 140, cy - 30), f"Turn: {cur.name}", fill="#000", font=font_big)
        draw.text((cx - 140, cy - 10), f"Money: ${cur.money}", fill="#DAA520", font=font_big)
        draw.text((cx - 140, cy + 15), f"Pos: {BOARD[cur.position]['name']}", fill="#000", font=font_small)

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
    wait_buyout = State()
    wait_turn_time = State()


class JoinRoom(StatesGroup):
    wait_code = State()
    wait_password = State()


# ================== БОТ ==================
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)


# ================== ТАЙМЕРЫ ==================
async def turn_timeout(room_code: str):
    """Автоматический переход хода через заданное время"""
    room = db.get_room(room_code)
    if not room:
        return
    
    for remaining in range(room.turn_time, 0, -1):
        await asyncio.sleep(1)
        room = db.get_room(room_code)
        if not room or not room.is_started or room.awaiting_buy is None:
            return
        
        room.countdown_seconds = remaining
        await send_board_to_all(room)
    
    room = db.get_room(room_code)
    if room and room.awaiting_buy is not None:
        cur = room.current_player()
        if cur:
            room.add_event(t('timeout', room.language).format(cur.name))
            await end_turn(room)


async def movement_delay(room_code: str, seconds: int):
    """Задержка перед перемещением с обратным отсчетом"""
    for remaining in range(seconds, 0, -1):
        room = db.get_room(room_code)
        if not room:
            return
        room.countdown_seconds = remaining
        room.add_event(t('moving_countdown', room.language).format(remaining))
        await send_board_to_all(room)
        await asyncio.sleep(1)


async def turn_end_delay(room_code: str, seconds: int):
    """Задержка перед передачей хода с обратным отсчетом"""
    for remaining in range(seconds, 0, -1):
        room = db.get_room(room_code)
        if not room:
            return
        room.countdown_seconds = remaining
        room.add_event(t('turn_end_countdown', room.language).format(remaining))
        await send_board_to_all(room)
        await asyncio.sleep(1)


# ================== ОТПРАВКА ПОЛЯ ==================
async def send_board_to_all(room: Room, force_update: bool = False):
    """Редактирует одно сообщение для каждого игрока"""
    img_bytes = render_board(room)
    photo = BufferedInputFile(img_bytes, filename="board.png")

    cur = room.current_player()
    
    events_text = ""
    if room.event_log:
        events_text = "\n".join(room.event_log[-3:]) + "\n\n"
    
    text = events_text
    text += f"🎲 **RUZOPOLY** | Room: `{room.code}`\n"
    if cur:
        text += f"👤 Turn: **{cur.name}** (${cur.money})\n"
        text += f"📍 Position: {BOARD[cur.position]['name']}\n"

    text += "\n💰 **Players:**\n"
    for p in room.players.values():
        marker = "👑" if p.user_id == (cur.user_id if cur else None) else "  "
        bot_mark = "🤖" if p.is_bot else "👤"
        active_mark = "" if p.is_active else " ❌"
        text += f"{marker} {bot_mark} {p.name}: ${p.money}{active_mark}\n"

    for user_id in room.player_ids:
        if user_id < 0:
            continue
            
        kb_buttons = []
        if cur and room.is_started and user_id == cur.user_id and not room.is_moving:
            # Кнопка броска кубиков только если можно бросать
            if room.can_roll and not room.awaiting_buy:
                kb_buttons.append([InlineKeyboardButton(text=t('roll_dice', room.language), callback_data=f"roll_{room.code}")])
            
            if room.awaiting_buy is not None:
                cell = BOARD[room.awaiting_buy]
                
                if room.awaiting_buyout:
                    owner_id, houses = room.ownership[room.awaiting_buy]
                    buyout_price = calculate_buyout_price(cell, houses)
                    kb_buttons.append([InlineKeyboardButton(
                        text=t('buyout_property', room.language).format(cell['name'], buyout_price),
                        callback_data=f"buyout_{room.code}")])
                    kb_buttons.append([InlineKeyboardButton(text=t('skip', room.language), callback_data=f"skipbuy_{room.code}")])
                else:
                    kb_buttons.append([InlineKeyboardButton(
                        text=t('buy_property', room.language).format(cell['name'], cell['price']),
                        callback_data=f"buy_{room.code}")])
                    kb_buttons.append([InlineKeyboardButton(text=t('skip', room.language), callback_data=f"skipbuy_{room.code}")])
            
            if cur.in_jail and not room.awaiting_buy:
                kb_buttons.append([InlineKeyboardButton(text=t('pay_jail', room.language), callback_data=f"payjail_{room.code}")])
            
            if cur.money < 0:
                properties = get_player_properties(room, cur.user_id)
                if properties:
                    for prop_idx, prop_cell, houses in properties[:3]:
                        sell_price = calculate_sell_price(prop_cell, houses)
                        kb_buttons.append([InlineKeyboardButton(
                            text=t('sell_property', room.language).format(prop_cell['name']),
                            callback_data=f"sell_{room.code}_{prop_idx}")])

        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons) if kb_buttons else None

        try:
            if user_id in room.player_message_ids:
                try:
                    await bot.edit_message_media(
                        chat_id=user_id,
                        message_id=room.player_message_ids[user_id],
                        media=types.InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
                        reply_markup=kb
                    )
                except Exception as e:
                    logging.error(f"Error editing message for user {user_id}: {e}")
                    msg = await bot.send_photo(
                        chat_id=user_id, photo=photo, caption=text, parse_mode="Markdown", reply_markup=kb
                    )
                    room.player_message_ids[user_id] = msg.message_id
                    db.set_player_message_id(room.code, user_id, msg.message_id)
            else:
                msg = await bot.send_photo(
                    chat_id=user_id, photo=photo, caption=text, parse_mode="Markdown", reply_markup=kb
                )
                room.player_message_ids[user_id] = msg.message_id
                db.set_player_message_id(room.code, user_id, msg.message_id)
        except Exception as e:
            logging.error(f"Error sending board to user {user_id}: {e}")


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
    room.player_ids.add(player.user_id)
    db.set_user_room(callback.from_user.id, room.code)
    db.update_room(room)
    
    await callback.answer(t('joined_room', lang).format(room.code))
    await show_lobby(callback.message, room)


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
    lang = db.get_user_language(callback.from_user.id)
    await state.update_data(password=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('allow_buyout', lang), callback_data="buyout_yes")],
        [InlineKeyboardButton(text=t('no_buyout', lang), callback_data="buyout_no")],
    ])
    await callback.message.edit_text(t('allow_buyout_question', lang), reply_markup=kb)
    await state.set_state(CreateRoom.wait_buyout)


@router.callback_query(F.data == "pass_yes", StateFilter(CreateRoom.wait_password))
async def cb_ask_password(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    await callback.message.edit_text(t('enter_password', lang))


@router.message(StateFilter(CreateRoom.wait_password))
async def msg_password(message: Message, state: FSMContext):
    lang = db.get_user_language(message.from_user.id)
    password = message.text.strip()
    await state.update_data(password=password)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('allow_buyout', lang), callback_data="buyout_yes")],
        [InlineKeyboardButton(text=t('no_buyout', lang), callback_data="buyout_no")],
    ])
    await message.answer(t('allow_buyout_question', lang), reply_markup=kb)
    await state.set_state(CreateRoom.wait_buyout)


@router.callback_query(F.data.startswith("buyout_"), StateFilter(CreateRoom.wait_buyout))
async def cb_buyout_choice(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    allow_buyout = callback.data == "buyout_yes"
    await state.update_data(allow_buyout=allow_buyout)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏰ {t('seconds_15', lang)}", callback_data="time_15")],
        [InlineKeyboardButton(text=f"⏰ {t('seconds_30', lang)}", callback_data="time_30")],
        [InlineKeyboardButton(text=f"⏰ {t('seconds_60', lang)}", callback_data="time_60")],
    ])
    await callback.message.edit_text(t('choose_turn_time', lang), reply_markup=kb)
    await state.set_state(CreateRoom.wait_turn_time)


@router.callback_query(F.data.startswith("time_"), StateFilter(CreateRoom.wait_turn_time))
async def cb_turn_time_choice(callback: CallbackQuery, state: FSMContext):
    turn_time = int(callback.data.split("_")[1])
    data = await state.get_data()
    await finalize_room(callback, data.get('password'), data['max_players'], data['allow_buyout'], turn_time, state)


async def finalize_room(callback: CallbackQuery, password: Optional[str], max_players: int, allow_buyout: bool, turn_time: int, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    code = generate_code()
    room = Room(
        code=code, creator_id=callback.from_user.id,
        chat_id=callback.from_user.id, max_players=max_players,
        password=password, language=lang, allow_buyout=allow_buyout,
        turn_time=turn_time
    )
    color = get_available_color(room)
    player = Player(user_id=callback.from_user.id, name=callback.from_user.full_name, color=color)
    room.players[player.user_id] = player
    room.player_ids.add(player.user_id)
    
    if not db.create_room(room):
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    
    db.add_player(code, player)
    db.set_user_room(callback.from_user.id, code)
    
    await state.clear()
    await show_lobby(callback.message, room)


async def show_lobby(message_or_cb, room: Room):
    players_text = "\n".join([
        f"{'🤖' if p.is_bot else '👤'} {p.name}" for p in room.players.values()
    ])
    
    buyout_status = t('enabled', room.language) if room.allow_buyout else t('disabled', room.language)
    
    text = t('room_info', room.language).format(
        room.code,
        room.password or t('none', room.language),
        len(room.players),
        room.max_players,
        buyout_status,
        room.turn_time,
        players_text
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('add_bot', room.language), callback_data=f"addbot_{room.code}")],
        [InlineKeyboardButton(text=t('start_game', room.language), callback_data=f"start_{room.code}")],
        [InlineKeyboardButton(text=t('refresh', room.language), callback_data=f"lobby_{room.code}")],
    ])
    
    if isinstance(message_or_cb, CallbackQuery):
        try:
            await message_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await message_or_cb.answer()
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
    room.player_ids.add(bot_user_id)
    db.update_room(room)
    
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
    
    if callback.from_user.id != room.creator_id:
        await callback.answer(t('only_creator_start', lang), show_alert=True)
        return
    
    if len(room.players) < 2:
        await callback.answer(t('need_min_players', lang), show_alert=True)
        return
    
    room.is_started = True
    room.can_roll = True
    db.update_room(room)
    
    await callback.message.edit_text(t('game_starting', room.language))
    
    cur = room.current_player()
    if cur:
        room.add_event(t('player_turn', room.language).format(cur.name))
    
    room.add_event(t('game_started', room.language))
    await send_board_to_all(room, force_update=True)
    await maybe_bot_turn(room)


# ================== ПРИСОЕДИНЕНИЕ ==================
@router.callback_query(F.data == "join_room")
async def cb_join_menu(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_language(callback.from_user.id)
    await callback.message.edit_text(t('enter_room_code', lang))
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
    room.player_ids.add(player.user_id)
    db.set_user_room(message.from_user.id, room.code)
    db.update_room(room)
    
    await state.clear()
    await message.answer(t('joined_room', lang).format(room.code), parse_mode="Markdown")
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
    
    if not room.can_roll:
        await callback.answer("Please wait...", show_alert=True)
        return
    
    await callback.answer()
    await do_roll(room)


async def do_roll(room: Room):
    cur = room.current_player()
    if not cur:
        return

    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()

    # Убираем кнопку броска
    room.can_roll = False
    db.update_room(room)
    await send_board_to_all(room)

    if cur.in_jail:
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        if d1 == d2:
            cur.in_jail = False
            cur.jail_turns = 0
            cur.doubles_count = 0
            db.update_player(room.code, cur)
            room.add_event(t('jail_doubles', room.language).format(cur.name, d1, d2))
            await send_board_to_all(room)
            
            await movement_delay(room.code, 5)
            await move_player(room, cur, d1 + d2, d1 + d2)
        else:
            cur.jail_turns += 1
            db.update_player(room.code, cur)
            if cur.jail_turns >= 3:
                cur.pay(150)
                cur.in_jail = False
                cur.jail_turns = 0
                cur.doubles_count = 0
                db.update_player(room.code, cur)
                room.add_event(t('jail_pay_forced', room.language).format(cur.name))
                await send_board_to_all(room)
                
                await movement_delay(room.code, 5)
                await move_player(room, cur, d1 + d2, d1 + d2)
            else:
                room.add_event(t('jail_no_doubles', room.language).format(cur.name, d1, d2, 3 - cur.jail_turns))
                
                await turn_end_delay(room.code, 10)
                
                room.next_turn()
                cur.doubles_count = 0
                db.update_player(room.code, cur)
                db.update_room(room)
                
                next_player = room.current_player()
                if next_player:
                    room.add_event(t('player_turn', room.language).format(next_player.name))
                
                room.can_roll = True
                db.update_room(room)
                await send_board_to_all(room)
                await maybe_bot_turn(room)
        return

    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    is_double = d1 == d2
    
    room.add_event(t('rolled', room.language).format(cur.name, d1, d2, total))
    
    if is_double:
        cur.doubles_count += 1
        if cur.doubles_count >= 3:
            room.add_event(t('third_double', room.language).format(cur.name))
            cur.position = 10
            cur.in_jail = True
            cur.jail_turns = 0
            cur.doubles_count = 0
            db.update_player(room.code, cur)
            await send_board_to_all(room)
            
            await turn_end_delay(room.code, 10)
            
            room.next_turn()
            room.can_roll = True
            db.update_room(room)
            
            next_player = room.current_player()
            if next_player:
                room.add_event(t('player_turn', room.language).format(next_player.name))
            
            await send_board_to_all(room)
            await maybe_bot_turn(room)
            return
        else:
            room.add_event(t('doubles', room.language).format(cur.name))
    
    await send_board_to_all(room)
    
    await movement_delay(room.code, 5)
    await move_player(room, cur, total, total, is_double)


async def move_player(room: Room, player: Player, steps: int, dice_sum: int, is_double: bool = False):
    room.is_moving = True
    db.update_room(room)
    
    old_pos = player.position
    new_pos = (player.position + steps) % 40

    if new_pos < old_pos and new_pos != 0:
        player.receive(200)
        db.update_player(room.code, player)
        room.add_event(t('passed_start', room.language).format(player.name))

    player.position = new_pos
    db.update_player(room.code, player)
    
    room.is_moving = False
    db.update_room(room)
    
    await process_cell(room, player, dice_sum, is_double)


async def process_cell(room: Room, player: Player, dice_sum: int, is_double: bool = False):
    cell = BOARD[player.position]
    ctype = cell["type"]

    if ctype == "go":
        room.add_event(t('at_start', room.language).format(player.name))
        await send_board_to_all(room)
        
        if is_double:
            room.can_roll = True
            db.update_room(room)
            await send_board_to_all(room)
        else:
            await turn_end_delay(room.code, 10)
            await end_turn(room)
            
    elif ctype == "property":
        await handle_property(room, player, cell, dice_sum, is_double)
    elif ctype == "chance":
        card = random.choice(room.chance_deck)
        await apply_card(room, player, card, "🎲 CHANCE", is_double)
    elif ctype == "risk":
        card = random.choice(room.risk_deck)
        await apply_card(room, player, card, "⚠️ RISK", is_double)
    elif ctype == "chest":
        amount = random.choice([50, 100, 150, 200])
        player.receive(amount)
        db.update_player(room.code, player)
        room.add_event(t('chest_reward', room.language).format(player.name, amount))
        await send_board_to_all(room)
        
        if is_double:
            room.can_roll = True
            db.update_room(room)
            await send_board_to_all(room)
        else:
            await turn_end_delay(room.code, 10)
            await end_turn(room)
            
    elif ctype == "tax":
        player.pay(cell["amount"])
        db.update_player(room.code, player)
        room.add_event(t('tax_paid', room.language).format(player.name, cell["amount"]))
        await check_player_debt(room, player)
        await send_board_to_all(room)
        
        if is_double:
            room.can_roll = True
            db.update_room(room)
            await send_board_to_all(room)
        else:
            await turn_end_delay(room.code, 10)
            await end_turn(room)
            
    elif ctype == "jail":
        room.add_event(t('visiting_jail', room.language).format(player.name))
        await send_board_to_all(room)
        
        if is_double:
            room.can_roll = True
            db.update_room(room)
            await send_board_to_all(room)
        else:
            await turn_end_delay(room.code, 10)
            await end_turn(room)
            
    elif ctype == "free_parking":
        room.add_event(t('at_parking', room.language).format(player.name))
        await send_board_to_all(room)
        
        if is_double:
            room.can_roll = True
            db.update_room(room)
            await send_board_to_all(room)
        else:
            await turn_end_delay(room.code, 10)
            await end_turn(room)
            
    elif ctype == "go_to_jail":
        player.position = 10
        player.in_jail = True
        player.jail_turns = 0
        player.doubles_count = 0
        db.update_player(room.code, player)
        room.add_event(t('go_to_jail', room.language).format(player.name))
        await send_board_to_all(room)
        
        await turn_end_delay(room.code, 10)
        await end_turn(room)
        
# Добавьте эти функции перед handle_property

def can_build_houses(room: Room, player_id: int, cell_idx: int) -> bool:
    """Проверка возможности строительства домов"""
    cell = BOARD[cell_idx]
    if cell.get("type") != "property":
        return False
    if cell.get("group") in ["station", "utility"]:
        return False
    
    # Проверяем владение всей группой
    group = cell.get("group")
    group_cells = [i for i, c in enumerate(BOARD) if c.get("group") == group]
    
    for idx in group_cells:
        if idx not in room.ownership or room.ownership[idx][0] != player_id:
            return False
    
    return True


def get_house_price(cell_idx: int) -> int:
    """Получить цену дома для территории"""
    cell = BOARD[cell_idx]
    return cell.get("house", 50)


def can_build_hotel(room: Room, cell_idx: int) -> bool:
    """Проверка возможности строительства отеля"""
    if cell_idx not in room.ownership:
        return False
    
    _, houses = room.ownership[cell_idx]
    return houses == 4


# Замените функцию handle_property на эту:

async def handle_property(room: Room, player: Player, cell, dice_sum: int, is_double: bool = False):
    idx = player.position
    if idx in room.ownership:
        owner_id, houses = room.ownership[idx]
        if owner_id == player.user_id:
            room.add_event(t('own_property', room.language).format(player.name, cell['name']))
            
            # Предлагаем построить дом/отель
            if can_build_houses(room, player.user_id, idx):
                house_price = get_house_price(idx)
                
                if houses < 4 and player.money >= house_price:
                    # Можем построить дом
                    room.awaiting_buy = idx
                    room.awaiting_buyout = False
                    db.update_room(room)
                    
                    room.add_event(f"🏗️ Build house on {cell['name']} for ${house_price}? ({houses}/4 houses)")
                    await send_board_to_all(room)
                    room.turn_timer_task = asyncio.create_task(turn_timeout(room.code))
                    return
                    
                elif houses == 4 and player.money >= house_price:
                    # Можем построить отель
                    room.awaiting_buy = idx
                    room.awaiting_buyout = False
                    db.update_room(room)
                    
                    room.add_event(f"🏨 Build HOTEL on {cell['name']} for ${house_price}?")
                    await send_board_to_all(room)
                    room.turn_timer_task = asyncio.create_task(turn_timeout(room.code))
                    return
            
            await send_board_to_all(room)
            
            if is_double:
                room.can_roll = True
                db.update_room(room)
                await send_board_to_all(room)
            else:
                await turn_end_delay(room.code, 10)
                await end_turn(room)
        else:
            owner = room.players[owner_id]
            
            # Расчет ренты по правилам
            if cell.get("group") == "station":
                station_count = count_owned_stations(room, owner_id)
                rent = calculate_rent(cell, houses, station_count, dice_sum)
            elif cell.get("group") == "utility":
                utility_count = count_owned_utilities(room, owner_id)
                rent = calculate_rent(cell, houses, utility_count, dice_sum)
            else:
                rent = calculate_rent(cell, houses, 1, dice_sum)
            
            player.pay(rent)
            owner.receive(rent)
            db.update_player(room.code, player)
            db.update_player(room.code, owner)
            room.add_event(t('rent_paid', room.language).format(player.name, rent, owner.name, cell['name']))
            
            await check_player_debt(room, player)
            
            if room.allow_buyout and cell.get("group") not in ["station", "utility"]:
                room.awaiting_buy = idx
                room.awaiting_buyout = True
                db.update_room(room)
                room.turn_timer_task = asyncio.create_task(turn_timeout(room.code))
            
            await send_board_to_all(room)
            
            if not room.allow_buyout or cell.get("group") in ["station", "utility"]:
                if is_double:
                    room.can_roll = True
                    db.update_room(room)
                    await send_board_to_all(room)
                else:
                    await turn_end_delay(room.code, 10)
                    await end_turn(room)
    else:
        if player.money >= cell["price"]:
            room.awaiting_buy = idx
            room.awaiting_buyout = False
            db.update_room(room)
            room.add_event(t('free_property', room.language).format(cell['name'], cell['price'], cell['rent'][0]))
            await send_board_to_all(room)
            
            room.turn_timer_task = asyncio.create_task(turn_timeout(room.code))
            
            if player.is_bot:
                await asyncio.sleep(1.5)
                player.pay(cell["price"])
                room.ownership[idx] = (player.user_id, 0)
                db.set_ownership(room.code, idx, player.user_id, 0)
                room.awaiting_buy = None
                room.awaiting_buyout = False
                db.update_room(room)
                db.update_player(room.code, player)
                room.add_event(t('property_bought', room.language).format(player.name, cell['name'], cell['price']))
                
                if check_all_stations_owned(room, player.user_id):
                    await end_game(room, player, 'stations')
                    return
                
                await send_board_to_all(room)
                
                if is_double:
                    room.can_roll = True
                    db.update_room(room)
                    await send_board_to_all(room)
                else:
                    await turn_end_delay(room.code, 10)
                    await end_turn(room)
        else:
            room.add_event(t('not_enough_money', room.language).format(player.name))
            await send_board_to_all(room)
            
            if is_double:
                room.can_roll = True
                db.update_room(room)
                await send_board_to_all(room)
            else:
                await turn_end_delay(room.code, 10)
                await end_turn(room)


# Обновите функцию send_board_to_all (часть с кнопками):

# Найдите эту часть и замените:
        kb_buttons = []
        if cur and room.is_started and user_id == cur.user_id and not room.is_moving:
            # Кнопка броска кубиков только если можно бросать
            if room.can_roll and not room.awaiting_buy:
                kb_buttons.append([InlineKeyboardButton(text=t('roll_dice', room.language), callback_data=f"roll_{room.code}")])
            
            if room.awaiting_buy is not None:
                cell = BOARD[room.awaiting_buy]
                
                # Проверяем, это строительство дома/отеля или покупка/выкуп
                if room.awaiting_buy in room.ownership and room.ownership[room.awaiting_buy][0] == cur.user_id:
                    # Строительство дома/отеля на своей территории
                    _, houses = room.ownership[room.awaiting_buy]
                    house_price = get_house_price(room.awaiting_buy)
                    
                    if houses < 4:
                        kb_buttons.append([InlineKeyboardButton(
                            text=f"🏗️ Build House (${house_price})",
                            callback_data=f"buildhouse_{room.code}")])
                    elif houses == 4:
                        kb_buttons.append([InlineKeyboardButton(
                            text=f"🏨 Build Hotel (${house_price})",
                            callback_data=f"buildhotel_{room.code}")])
                    
                    kb_buttons.append([InlineKeyboardButton(text=t('skip', room.language), callback_data=f"skipbuy_{room.code}")])
                
                elif room.awaiting_buyout:
                    # Выкуп чужой территории
                    owner_id, houses = room.ownership[room.awaiting_buy]
                    buyout_price = calculate_buyout_price(cell, houses)
                    kb_buttons.append([InlineKeyboardButton(
                        text=t('buyout_property', room.language).format(cell['name'], buyout_price),
                        callback_data=f"buyout_{room.code}")])
                    kb_buttons.append([InlineKeyboardButton(text=t('skip', room.language), callback_data=f"skipbuy_{room.code}")])
                else:
                    # Покупка свободной территории
                    kb_buttons.append([InlineKeyboardButton(
                        text=t('buy_property', room.language).format(cell['name'], cell['price']),
                        callback_data=f"buy_{room.code}")])
                    kb_buttons.append([InlineKeyboardButton(text=t('skip', room.language), callback_data=f"skipbuy_{room.code}")])
            
            if cur.in_jail and not room.awaiting_buy:
                kb_buttons.append([InlineKeyboardButton(text=t('pay_jail', room.language), callback_data=f"payjail_{room.code}")])
            
            if cur.money < 0:
                properties = get_player_properties(room, cur.user_id)
                if properties:
                    for prop_idx, prop_cell, houses in properties[:3]:
                        sell_price = calculate_sell_price(prop_cell, houses)
                        kb_buttons.append([InlineKeyboardButton(
                            text=t('sell_property', room.language).format(prop_cell['name']),
                            callback_data=f"sell_{room.code}_{prop_idx}")])


# Добавьте новые обработчики для строительства:

@router.callback_query(F.data.startswith("buildhouse_"))
async def cb_build_house(callback: CallbackQuery):
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
        await callback.answer("Nothing to build", show_alert=True)
        return
    
    idx = room.awaiting_buy
    cell = BOARD[idx]
    
    if idx not in room.ownership or room.ownership[idx][0] != cur.user_id:
        await callback.answer("Not your property", show_alert=True)
        return
    
    _, houses = room.ownership[idx]
    house_price = get_house_price(idx)
    
    if houses >= 4:
        await callback.answer("Maximum houses already built", show_alert=True)
        return
    
    if cur.money < house_price:
        await callback.answer(t('not_enough_ruzcoin', lang), show_alert=True)
        return
    
    # Строим дом
    cur.pay(house_price)
    room.ownership[idx] = (cur.user_id, houses + 1)
    db.set_ownership(room.code, idx, cur.user_id, houses + 1)
    db.update_player(room.code, cur)
    
    room.awaiting_buy = None
    
    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()
    
    db.update_room(room)
    
    await callback.answer()
    room.add_event(f"🏗️ {cur.name} built house on {cell['name']}! ({houses + 1}/4)")
    
    await send_board_to_all(room)
    
    if cur.doubles_count > 0:
        room.can_roll = True
        db.update_room(room)
        await send_board_to_all(room)
    else:
        await turn_end_delay(room.code, 10)
        await end_turn(room)


@router.callback_query(F.data.startswith("buildhotel_"))
async def cb_build_hotel(callback: CallbackQuery):
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
        await callback.answer("Nothing to build", show_alert=True)
        return
    
    idx = room.awaiting_buy
    cell = BOARD[idx]
    
    if idx not in room.ownership or room.ownership[idx][0] != cur.user_id:
        await callback.answer("Not your property", show_alert=True)
        return
    
    _, houses = room.ownership[idx]
    house_price = get_house_price(idx)
    
    if houses != 4:
        await callback.answer("Need 4 houses first", show_alert=True)
        return
    
    if cur.money < house_price:
        await callback.answer(t('not_enough_ruzcoin', lang), show_alert=True)
        return
    
    # Строим отель (5 = отель)
    cur.pay(house_price)
    room.ownership[idx] = (cur.user_id, 5)
    db.set_ownership(room.code, idx, cur.user_id, 5)
    db.update_player(room.code, cur)
    
    room.awaiting_buy = None
    
    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()
    
    db.update_room(room)
    
    await callback.answer()
    room.add_event(f"🏨 {cur.name} built HOTEL on {cell['name']}!")
    
    await send_board_to_all(room)
    
    if cur.doubles_count > 0:
        room.can_roll = True
        db.update_room(room)
        await send_board_to_all(room)
    else:
        await turn_end_delay(room.code, 10)
        await end_turn(room)

async def handle_property(room: Room, player: Player, cell, dice_sum: int, is_double: bool = False):
    idx = player.position
    if idx in room.ownership:
        owner_id, houses = room.ownership[idx]
        if owner_id == player.user_id:
            room.add_event(t('own_property', room.language).format(player.name, cell['name']))
            await send_board_to_all(room)
            
            if is_double:
                room.can_roll = True
                db.update_room(room)
                await send_board_to_all(room)
            else:
                await turn_end_delay(room.code, 10)
                await end_turn(room)
        else:
            owner = room.players[owner_id]
            
            # Расчет ренты по правилам
            if cell.get("group") == "station":
                station_count = count_owned_stations(room, owner_id)
                rent = calculate_rent(cell, houses, station_count, dice_sum)
            elif cell.get("group") == "utility":
                utility_count = count_owned_utilities(room, owner_id)
                rent = calculate_rent(cell, houses, utility_count, dice_sum)
            else:
                rent = calculate_rent(cell, houses, 1, dice_sum)
            
            player.pay(rent)
            owner.receive(rent)
            db.update_player(room.code, player)
            db.update_player(room.code, owner)
            room.add_event(t('rent_paid', room.language).format(player.name, rent, owner.name, cell['name']))
            
            await check_player_debt(room, player)
            
            if room.allow_buyout and cell.get("group") != "station":
                room.awaiting_buy = idx
                room.awaiting_buyout = True
                db.update_room(room)
                room.turn_timer_task = asyncio.create_task(turn_timeout(room.code))
            
            await send_board_to_all(room)
            
            if not room.allow_buyout or cell.get("group") == "station":
                if is_double:
                    room.can_roll = True
                    db.update_room(room)
                    await send_board_to_all(room)
                else:
                    await turn_end_delay(room.code, 10)
                    await end_turn(room)
    else:
        if player.money >= cell["price"]:
            room.awaiting_buy = idx
            room.awaiting_buyout = False
            db.update_room(room)
            room.add_event(t('free_property', room.language).format(cell['name'], cell['price'], cell['rent'][0]))
            await send_board_to_all(room)
            
            room.turn_timer_task = asyncio.create_task(turn_timeout(room.code))
            
            if player.is_bot:
                await asyncio.sleep(1.5)
                player.pay(cell["price"])
                room.ownership[idx] = (player.user_id, 0)
                db.set_ownership(room.code, idx, player.user_id, 0)
                room.awaiting_buy = None
                room.awaiting_buyout = False
                db.update_room(room)
                db.update_player(room.code, player)
                room.add_event(t('property_bought', room.language).format(player.name, cell['name'], cell['price']))
                
                if check_all_stations_owned(room, player.user_id):
                    await end_game(room, player, 'stations')
                    return
                
                await send_board_to_all(room)
                
                if is_double:
                    room.can_roll = True
                    db.update_room(room)
                    await send_board_to_all(room)
                else:
                    await turn_end_delay(room.code, 10)
                    await end_turn(room)
        else:
            room.add_event(t('not_enough_money', room.language).format(player.name))
            await send_board_to_all(room)
            
            if is_double:
                room.can_roll = True
                db.update_room(room)
                await send_board_to_all(room)
            else:
                await turn_end_delay(room.code, 10)
                await end_turn(room)


async def apply_card(room: Room, player: Player, card, title: str, is_double: bool = False):
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

    room.add_event(text)
    await check_player_debt(room, player)
    await send_board_to_all(room)
    
    if is_double:
        room.can_roll = True
        db.update_room(room)
        await send_board_to_all(room)
    else:
        await turn_end_delay(room.code, 10)
        await end_turn(room)


async def check_player_debt(room: Room, player: Player):
    """Проверка долга игрока"""
    if player.money < 0:
        properties = get_player_properties(room, player.user_id)
        total_sell_value = sum(calculate_sell_price(cell, houses) for _, cell, houses in properties)
        
        if total_sell_value + player.money < 0:
            player.is_active = False
            db.update_player(room.code, player)
            room.add_event(t('player_eliminated', room.language).format(player.name))
            
            for prop_idx, _, _ in properties:
                del room.ownership[prop_idx]
                db.remove_ownership(room.code, prop_idx)
            
            await check_game_end(room)
        else:
            room.add_event(t('debt_warning', room.language).format(player.name))


async def check_game_end(room: Room):
    """Проверка окончания игры"""
    active = room.active_players()
    if len(active) == 1:
        winner = active[0]
        await end_game(room, winner, 'last_standing')


async def end_game(room: Room, winner: Player, reason: str):
    """Завершение игры"""
    if reason == 'stations':
        room.add_event(t('all_stations_owned', room.language).format(winner.name))
    
    room.add_event(t('player_won', room.language).format(winner.name))
    room.add_event(t('game_over', room.language))
    room.is_started = False
    db.update_room(room)
    
    await send_board_to_all(room)


async def end_turn(room: Room):
    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()
    
    cur = room.current_player()
    if cur:
        cur.doubles_count = 0
        db.update_player(room.code, cur)
    
    room.awaiting_buy = None
    room.awaiting_buyout = False
    room.next_turn()
    room.can_roll = True
    db.update_room(room)
    
    cur = room.current_player()
    if cur:
        room.add_event(t('player_turn', room.language).format(cur.name))
    
    await send_board_to_all(room)
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
    
    if room.awaiting_buy is None or room.awaiting_buyout:
        await callback.answer(t('nothing_to_buy', lang), show_alert=True)
        return
    
    idx = room.awaiting_buy
    cell = BOARD[idx]
    if cur.money < cell["price"]:
        await callback.answer(t('not_enough_ruzcoin', lang), show_alert=True)
        return
    
    cur.pay(cell["price"])
    room.ownership[idx] = (cur.user_id, 0)
    db.set_ownership(room.code, idx, cur.user_id, 0)
    room.awaiting_buy = None
    room.awaiting_buyout = False
    
    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()
    
    db.update_room(room)
    db.update_player(room.code, cur)
    
    await callback.answer()
    room.add_event(t('property_bought', room.language).format(cur.name, cell['name'], cell['price']))
    
    if check_all_stations_owned(room, cur.user_id):
        await end_game(room, cur, 'stations')
        return
    
    await send_board_to_all(room)
    
    # Проверяем, есть ли дубль
    if cur.doubles_count > 0:
        room.can_roll = True
        db.update_room(room)
        await send_board_to_all(room)
    else:
        await turn_end_delay(room.code, 10)
        await end_turn(room)


@router.callback_query(F.data.startswith("buyout_"))
async def cb_buyout(callback: CallbackQuery):
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
    
    if room.awaiting_buy is None or not room.awaiting_buyout:
        await callback.answer(t('nothing_to_buy', lang), show_alert=True)
        return
    
    idx = room.awaiting_buy
    cell = BOARD[idx]
    
    if idx not in room.ownership:
        await callback.answer(t('nothing_to_buy', lang), show_alert=True)
        return
    
    owner_id, houses = room.ownership[idx]
    buyout_price = calculate_buyout_price(cell, houses)
    
    if cur.money < buyout_price:
        await callback.answer(t('not_enough_ruzcoin', lang), show_alert=True)
        return
    
    owner = room.players[owner_id]
    cur.pay(buyout_price)
    owner.receive(buyout_price)
    room.ownership[idx] = (cur.user_id, houses)
    db.set_ownership(room.code, idx, cur.user_id, houses)
    room.awaiting_buy = None
    room.awaiting_buyout = False
    
    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()
    
    db.update_room(room)
    db.update_player(room.code, cur)
    db.update_player(room.code, owner)
    
    await callback.answer()
    room.add_event(t('property_buyout', room.language).format(cur.name, cell['name'], owner.name, buyout_price))
    
    await send_board_to_all(room)
    
    if cur.doubles_count > 0:
        room.can_roll = True
        db.update_room(room)
        await send_board_to_all(room)
    else:
        await turn_end_delay(room.code, 10)
        await end_turn(room)


@router.callback_query(F.data.startswith("sell_"))
async def cb_sell(callback: CallbackQuery):
    lang = db.get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    code = parts[1]
    prop_idx = int(parts[2])
    
    room = db.get_room(code)
    if not room:
        await callback.answer(t('room_not_found', lang), show_alert=True)
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != callback.from_user.id:
        await callback.answer(t('not_your_turn', lang), show_alert=True)
        return
    
    if prop_idx not in room.ownership:
        await callback.answer("Property not found", show_alert=True)
        return
    
    owner_id, houses = room.ownership[prop_idx]
    if owner_id != cur.user_id:
        await callback.answer("Not your property", show_alert=True)
        return
    
    cell = BOARD[prop_idx]
    sell_price = calculate_sell_price(cell, houses)
    
    cur.receive(sell_price)
    del room.ownership[prop_idx]
    db.remove_ownership(room.code, prop_idx)
    db.update_player(room.code, cur)
    
    await callback.answer()
    room.add_event(t('property_sold', room.language).format(cur.name, cell['name'], sell_price))
    
    if cur.money >= 0:
        await send_board_to_all(room)
        
        if cur.doubles_count > 0:
            room.can_roll = True
            db.update_room(room)
            await send_board_to_all(room)
        else:
            await turn_end_delay(room.code, 10)
            await end_turn(room)
    else:
        await check_player_debt(room, cur)
        await send_board_to_all(room)


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
    room.awaiting_buyout = False
    
    if room.turn_timer_task and not room.turn_timer_task.done():
        room.turn_timer_task.cancel()
    
    db.update_room(room)
    await callback.answer()
    room.add_event(t('purchase_declined', room.language).format(callback.from_user.full_name))
    
    if cur.doubles_count > 0:
        room.can_roll = True
        db.update_room(room)
        await send_board_to_all(room)
    else:
        await turn_end_delay(room.code, 10)
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
    
    if cur.money < 150:
        await callback.answer(t('not_enough_ruzcoin', lang), show_alert=True)
        return
    
    cur.pay(150)
    cur.in_jail = False
    cur.jail_turns = 0
    cur.doubles_count = 0
    db.update_player(room.code, cur)
    
    await callback.answer()
    room.add_event(t('jail_paid_out', room.language).format(cur.name))
    room.can_roll = True
    db.update_room(room)
    await send_board_to_all(room)


# ================== ЗАПУСК ==================
async def main():
    print("🚀 Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
