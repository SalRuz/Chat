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
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

logging.basicConfig(level=logging.INFO)

# ================== БАЗА ДАННЫХ ==================
DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ruzopoly.db"

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP        )
    ''')
    
    # Таблица комнат
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица игроков в комнатах
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
    
    # Таблица владения территориями
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ownership (
            room_code TEXT NOT NULL,
            cell_idx INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            PRIMARY KEY (room_code, cell_idx),
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
        # Таблица связи пользователь-комната
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_room (
            user_id INTEGER PRIMARY KEY,
            room_code TEXT NOT NULL,
            FOREIGN KEY (room_code) REFERENCES rooms(code)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ База данных инициализирована: {DB_PATH}")

init_db()

# ================== ДАННЫЕ ПОЛЯ ==================
GROUP_COLORS_HEX = {
    "brown": "#8B4513", "lightblue": "#87CEEB", "pink": "#FF69B4",
    "orange": "#FFA500", "red": "#FF3030", "yellow": "#FFD700",
    "green": "#2E8B57", "darkblue": "#1E3A8A",
}

BOARD = [
    {"name": "СТАРТ", "type": "go"},
    {"name": "Хлебная", "type": "property", "group": "brown", "price": 60, "rent": 4, "house": 50},
    {"name": "Казна", "type": "chest"},
    {"name": "Пекарня", "type": "property", "group": "brown", "price": 60, "rent": 4, "house": 50},
    {"name": "Налог", "type": "tax", "amount": 200},
    {"name": "Вокзал Север", "type": "property", "group": "station", "price": 200, "rent": 25},
    {"name": "Аллея", "type": "property", "group": "lightblue", "price": 100, "rent": 6, "house": 50},
    {"name": "Шанс", "type": "chance"},
    {"name": "Площадь", "type": "property", "group": "lightblue", "price": 100, "rent": 6, "house": 50},
    {"name": "Бульвар", "type": "property", "group": "lightblue", "price": 120, "rent": 8, "house": 50},
    {"name": "ТЮРЬМА", "type": "jail"},
    {"name": "Набережная", "type": "property", "group": "pink", "price": 140, "rent": 10, "house": 100},
    {"name": "Электрост.", "type": "property", "group": "utility", "price": 150, "rent": 20},
    {"name": "Парк", "type": "property", "group": "pink", "price": 140, "rent": 10, "house": 100},
    {"name": "Сквер", "type": "property", "group": "pink", "price": 160, "rent": 12, "house": 100},
    {"name": "Вокзал Юг", "type": "property", "group": "station", "price": 200, "rent": 25},
    {"name": "Улица Мира", "type": "property", "group": "orange", "price": 180, "rent": 14, "house": 100},
    {"name": "Риск", "type": "risk"},
    {"name": "Переулок", "type": "property", "group": "orange", "price": 180, "rent": 14, "house": 100},
    {"name": "Проспект", "type": "property", "group": "orange", "price": 200, "rent": 16, "house": 100},
    {"name": "ПАРКОВКА", "type": "free_parking"},
    {"name": "Театральная", "type": "property", "group": "red", "price": 220, "rent": 18, "house": 150},
    {"name": "Шанс", "type": "chance"},
    {"name": "Площадь Св.", "type": "property", "group": "red", "price": 220, "rent": 18, "house": 150},
    {"name": "Кремль", "type": "property", "group": "red", "price": 240, "rent": 20, "house": 150},
    {"name": "Вокзал Запад", "type": "property", "group": "station", "price": 200, "rent": 25},
    {"name": "Ростовская", "type": "property", "group": "yellow", "price": 260, "rent": 22, "house": 150},    {"name": "Самарская", "type": "property", "group": "yellow", "price": 260, "rent": 22, "house": 150},
    {"name": "Водоканал", "type": "property", "group": "utility", "price": 150, "rent": 20},
    {"name": "Омская", "type": "property", "group": "yellow", "price": 280, "rent": 24, "house": 150},
    {"name": "В ТЮРЬМУ", "type": "go_to_jail"},
    {"name": "Лесная", "type": "property", "group": "green", "price": 300, "rent": 26, "house": 200},
    {"name": "Речная", "type": "property", "group": "green", "price": 300, "rent": 26, "house": 200},
    {"name": "Казна", "type": "chest"},
    {"name": "Сосновая", "type": "property", "group": "green", "price": 320, "rent": 28, "house": 200},
    {"name": "Вокзал Вост.", "type": "property", "group": "station", "price": 200, "rent": 25},
    {"name": "Шанс", "type": "chance"},
    {"name": "Элитная", "type": "property", "group": "darkblue", "price": 350, "rent": 35, "house": 200},
    {"name": "Налог Люкс", "type": "tax", "amount": 100},
    {"name": "Дворцовая", "type": "property", "group": "darkblue", "price": 400, "rent": 50, "house": 200},
]

CHANCE_CARDS = [
    {"text": "🎉 Вы выиграли в лотерею! +200 Ruzcoin", "effect": 200},
    {"text": "🚗 Штраф за парковку. -50 Ruzcoin", "effect": -50},
    {"text": "🏦 Банковские дивиденды +100 Ruzcoin", "effect": 100},
    {"text": "🚓 Штраф ГИБДД. -100 Ruzcoin", "effect": -100},
    {"text": "🎂 День рождения! Каждый игрок платит вам по 50 Ruzcoin", "effect": "birthday"},
    {"text": "🏃 Переход на СТАРТ. +200 Ruzcoin", "effect": 200, "move_to": 0},
    {"text": "📈 Акции выросли. +150 Ruzcoin", "effect": 150},
    {"text": "🔧 Ремонт имущества. -100 Ruzcoin", "effect": -100},
]

RISK_CARDS = [
    {"text": "💸 Налог на роскошь. -150 Ruzcoin", "effect": -150},
    {"text": "🎁 Подарок от дяди. +100 Ruzcoin", "effect": 100},
    {"text": "🏥 Оплата больницы. -100 Ruzcoin", "effect": -100},
    {"text": "💼 Премия на работе. +200 Ruzcoin", "effect": 200},
    {"text": "📚 Оплата обучения. -50 Ruzcoin", "effect": -50},
    {"text": "🎰 Выигрыш в казино. +250 Ruzcoin", "effect": 250},
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
    in_jail: bool = False    jail_turns: int = 0
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
    def save_user(user_id: int, username: str):
        conn = sqlite3.connect(str(DB_PATH))        conn.execute(
            "INSERT OR REPLACE INTO users (id, username) VALUES (?, ?)",
            (user_id, username)
        )
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
                    chance_deck, risk_deck, awaiting_buy)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (room.code, room.creator_id, room.chat_id, room.max_players,
                 room.password, room.current_turn, room.is_started,
                 room.last_message_id, json.dumps(room.chance_deck),
                 json.dumps(room.risk_deck), room.awaiting_buy)
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
            awaiting_buy=row[10]
        )

        # Загрузка игроков
        cursor.execute("SELECT * FROM players WHERE room_code = ?", (code,))        for p_row in cursor.fetchall():
            room.players[p_row[1]] = Player(
                user_id=p_row[1], name=p_row[2], money=p_row[3],
                position=p_row[4], color=p_row[5], is_bot=bool(p_row[6]),
                in_jail=bool(p_row[7]), jail_turns=p_row[8], is_active=bool(p_row[9])
            )

        # Загрузка владения
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
               chance_deck=?, risk_deck=?, awaiting_buy=?
               WHERE code=?""",
            (room.current_turn, room.is_started, room.last_message_id,
             json.dumps(room.chance_deck), json.dumps(room.risk_deck),
             room.awaiting_buy, room.code)
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


db = Database()

# ================== УТИЛИТЫ ==================
def generate_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_available_color(room: Room) -> str:
    used = {p.color for p in room.players.values()}
    available = [c for c in PLAYER_COLORS if c not in used]
    return random.choice(available) if available else "#FFFFFF"


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

        bg = "#FFF8DC"
        if c["type"] == "go": bg = "#FFE4B5"
        elif c["type"] == "jail": bg = "#FFDAB9"
        elif c["type"] == "free_parking": bg = "#D3D3D3"
        elif c["type"] == "go_to_jail": bg = "#FFB6C1"
        elif c["type"] == "chance": bg = "#FFFACD"
        elif c["type"] == "risk": bg = "#FFE4E1"
        elif c["type"] == "chest": bg = "#E0FFFF"
        elif c["type"] == "tax": bg = "#F0E68C"

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
            owner = room.players.get(room.ownership[idx])
            if owner:
                overlay = Image.new('RGBA', (int(cell), int(cell)), owner.color + "80")
                img.paste(Image.alpha_composite(
                    Image.new('RGBA', (int(cell), int(cell)), (0, 0, 0, 0)), overlay
                ).convert('RGB'), (int(x1), int(y1)))
                draw.rectangle([x1, y1, x2, y2], outline=owner.color, width=3)

        draw.text((x1 + 4, y1 + 4), c["name"], fill="#000", font=font_big)
        if c["type"] == "property":
            draw.text((x1 + 4, y1 + 18), f"${c['price']}", fill="#555", font=font_small)

    active = room.active_players()
    for i, p in enumerate(active):
        x1, y1, x2, y2 = _cell_rect(p.position, cell)
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
        draw.text((cx - 140, cy - 30), f"Ход: {cur.name}", fill="#000", font=font_big)
        draw.text((cx - 140, cy - 10), f"Ruzcoin: {cur.money}", fill="#DAA520", font=font_big)
        draw.text((cx - 140, cy + 15), f"Позиция: {BOARD[cur.position]['name']}", fill="#000", font=font_small)

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
    else:        col = 10
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


# ================== ОТПРАВКА ПОЛЯ ==================
async def send_board(room: Room, extra_text: str = ""):
    img_bytes = render_board(room)
    photo = BufferedInputFile(img_bytes, filename="board.png")

    cur = room.current_player()
    text = f"🎲 **RUZOPOLY** | Комната: `{room.code}`\n"
    if cur:
        text += f"👤 Ход: **{cur.name}** ({cur.money} Ruzcoin)\n"
        text += f"📍 Позиция: {BOARD[cur.position]['name']}\n"
    if extra_text:
        text += f"\n{extra_text}"

    text += "\n\n💰 **Игроки:**\n"
    for p in room.players.values():
        marker = "👑" if p.user_id == (cur.user_id if cur else None) else "  "
        bot_mark = "🤖" if p.is_bot else "👤"
        active_mark = "" if p.is_active else " ❌"
        text += f"{marker} {bot_mark} {p.name}: {p.money} Ruzcoin{active_mark}\n"

    kb_buttons = []
    if cur and room.is_started:
        if not cur.is_bot:
            kb_buttons.append([InlineKeyboardButton(text="🎲 Бросить кубики", callback_data=f"roll_{room.code}")])
            if room.awaiting_buy is not None:
                cell = BOARD[room.awaiting_buy]                kb_buttons.append([InlineKeyboardButton(
                    text=f"💵 Купить {cell['name']} ({cell['price']}₽)",
                    callback_data=f"buy_{room.code}")])
                kb_buttons.append([InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skipbuy_{room.code}")])
            if cur.in_jail:
                kb_buttons.append([InlineKeyboardButton(text="💰 Заплатить 50 и выйти", callback_data=f"payjail_{room.code}")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons) if kb_buttons else None

    if room.last_message_id:
        try:
            await bot.edit_message_caption(
                chat_id=room.chat_id, message_id=room.last_message_id, caption=text, parse_mode="Markdown"
            )
            await bot.edit_message_reply_markup(
                chat_id=room.chat_id, message_id=room.last_message_id, reply_markup=kb
            )
            db.update_room(room)
            return
        except Exception:
            pass

    msg = await bot.send_photo(
        chat_id=room.chat_id, photo=photo, caption=text, parse_mode="Markdown", reply_markup=kb
    )
    room.last_message_id = msg.message_id
    db.update_room(room)


async def send_message(room: Room, text: str, reply_markup=None):
    return await bot.send_message(room.chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")


# ================== КОМАНДЫ ==================
@router.message(CommandStart())
async def cmd_start(message: Message):
    db.save_user(message.from_user.id, message.from_user.username or message.from_user.full_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Создать комнату", callback_data="create_room")],
        [InlineKeyboardButton(text="🚪 Присоединиться по коду", callback_data="join_room")],
    ])
    await message.answer(
        "🎩 Добро пожаловать в **RUZOPOLY**!\n\n"
        "Классическая Монополия с валютой **Ruzcoin** 💰\n\n"
        "Выберите действие:",
        reply_markup=kb, parse_mode="Markdown"
    )


@router.callback_query(F.data == "create_room")async def cb_create_room(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="2 игрока", callback_data="max_2"),
         InlineKeyboardButton(text="3 игрока", callback_data="max_3")],
        [InlineKeyboardButton(text="4 игрока", callback_data="max_4"),
         InlineKeyboardButton(text="6 игроков", callback_data="max_6")],
        [InlineKeyboardButton(text="8 игроков", callback_data="max_8")],
    ])
    await callback.message.edit_text("👥 Выберите максимальное количество игроков:", reply_markup=kb)
    await state.set_state(CreateRoom.wait_max)


@router.callback_query(F.data.startswith("max_"), StateFilter(CreateRoom.wait_max))
async def cb_max_players(callback: CallbackQuery, state: FSMContext):
    max_p = int(callback.data.split("_")[1])
    await state.update_data(max_players=max_p)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 С паролем", callback_data="pass_yes")],
        [InlineKeyboardButton(text="🔓 Без пароля", callback_data="pass_no")],
    ])
    await callback.message.edit_text(f"Макс. игроков: {max_p}. Нужен пароль?", reply_markup=kb)
    await state.set_state(CreateRoom.wait_password)


@router.callback_query(F.data == "pass_no", StateFilter(CreateRoom.wait_password))
async def cb_no_password(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await finalize_room(callback, None, data['max_players'], state)


@router.callback_query(F.data == "pass_yes", StateFilter(CreateRoom.wait_password))
async def cb_ask_password(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔐 Введите пароль для комнаты (одним сообщением):")


@router.message(StateFilter(CreateRoom.wait_password))
async def msg_password(message: Message, state: FSMContext):
    data = await state.get_data()
    password = message.text.strip()
    await finalize_room_from_message(message, password, data['max_players'], state)


async def finalize_room(callback: CallbackQuery, password: Optional[str], max_players: int, state: FSMContext):
    code = generate_code()
    room = Room(
        code=code, creator_id=callback.from_user.id,
        chat_id=callback.message.chat.id, max_players=max_players,
        password=password
    )
        color = get_available_color(room)
    player = Player(user_id=callback.from_user.id, name=callback.from_user.full_name, color=color)
    room.players[player.user_id] = player
    
    if not db.create_room(room):
        await callback.answer("Ошибка создания комнаты", show_alert=True)
        return
    
    db.add_player(code, player)
    db.set_user_room(callback.from_user.id, code)
    
    await state.clear()
    await show_lobby(callback.message, room)


async def finalize_room_from_message(message: Message, password: Optional[str], max_players: int, state: FSMContext):
    code = generate_code()
    room = Room(
        code=code, creator_id=message.from_user.id,
        chat_id=message.chat.id, max_players=max_players,
        password=password
    )
    
    color = get_available_color(room)
    player = Player(user_id=message.from_user.id, name=message.from_user.full_name, color=color)
    room.players[player.user_id] = player
    
    if not db.create_room(room):
        await message.answer("Ошибка создания комнаты")
        return
    
    db.add_player(code, player)
    db.set_user_room(message.from_user.id, code)
    
    await state.clear()
    await show_lobby(message, room)


async def show_lobby(message_or_cb, room: Room):
    players_text = "\n".join([
        f"{'🤖' if p.is_bot else '👤'} {p.name}" for p in room.players.values()
    ])
    text = (
        f"🏠 **Комната Ruzopoly**\n"
        f"🔑 Код: `{room.code}`\n"
        f"🔒 Пароль: `{room.password or 'нет'}`\n"
        f"👥 Игроки: {len(room.players)}/{room.max_players}\n\n"
        f"{players_text}\n\n"
        f"Ожидаем игроков..."
    )    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Добавить бота", callback_data=f"addbot_{room.code}")],
        [InlineKeyboardButton(text="🚀 Начать игру", callback_data=f"start_{room.code}")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"lobby_{room.code}")],
    ])
    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message_or_cb.answer(text, reply_markup=kb, parse_mode="Markdown")


# Продолжение следует в следующем сообщении из-за ограничения длины...
    # ================== ЛОББИ ==================
@router.callback_query(F.data.startswith("lobby_"))
async def cb_lobby(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer("Комната не найдена", show_alert=True)
        return
    await show_lobby(callback, room)


@router.callback_query(F.data.startswith("addbot_"))
async def cb_add_bot(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer("Комната не найдена", show_alert=True)
        return
    
    bot_names = ["Альфа-Бот", "Бета-Бот", "Гамма-Бот", "Дельта-Бот", "Эпсилон-Бот"]
    name = random.choice(bot_names)
    color = get_available_color(room)
    bot_user_id = -random.randint(1000, 9999)
    
    player = Player(user_id=bot_user_id, name=f"🤖 {name}", color=color, is_bot=True)
    
    if not db.add_player(code, player):
        await callback.answer("Комната заполнена", show_alert=True)
        return
    
    room.players[bot_user_id] = player
    await callback.answer(f"Бот {name} добавлен!")
    await show_lobby(callback, room)


@router.callback_query(F.data.startswith("start_"))
async def cb_start_game(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer("Комната не найдена", show_alert=True)
        return
    
    if len(room.players) < 2:
        await callback.answer("Нужно минимум 2 игрока", show_alert=True)
        return
    
    room.is_started = True
    db.update_room(room)
        await callback.message.edit_text("🎲 Игра начинается! Бросаем кубики...")
    await send_board(room, "🎲 **Игра началась!** Первый ход:")
    await maybe_bot_turn(room)


# ================== ПРИСОЕДИНЕНИЕ ==================
@router.callback_query(F.data == "join_room")
async def cb_join_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔑 Введите код комнаты:")
    await state.set_state(JoinRoom.wait_code)


@router.message(Command("join"))
async def cmd_join(message: Message, state: FSMContext):
    await message.answer("🔑 Введите код комнаты:")
    await state.set_state(JoinRoom.wait_code)


@router.message(StateFilter(JoinRoom.wait_code))
async def msg_join_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    room = db.get_room(code)
    if not room:
        await message.answer("❌ Комната не найдена. Проверьте код.")
        await state.clear()
        return
    
    if room.password:
        await state.update_data(join_code=code)
        await message.answer("🔒 Эта комната защищена паролем. Введите пароль:")
        return
    
    await do_join(message, room, state)


@router.message(StateFilter(JoinRoom.wait_password))
async def msg_join_password(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("join_code")
    if not code:
        await state.clear()
        return
    
    room = db.get_room(code)
    if not room:
        await message.answer("❌ Комната не найдена.")
        await state.clear()
        return
    
    if message.text.strip() != room.password:        await message.answer("❌ Неверный пароль.")
        return
    
    await do_join(message, room, state)


async def do_join(message: Message, room: Room, state: FSMContext):
    if message.from_user.id in room.players:
        await message.answer("Вы уже в этой комнате!")
        await state.clear()
        return
    
    color = get_available_color(room)
    player = Player(user_id=message.from_user.id, name=message.from_user.full_name, color=color)
    
    if not db.add_player(room.code, player):
        await message.answer("❌ Комната заполнена.")
        await state.clear()
        return
    
    room.players[player.user_id] = player
    db.set_user_room(message.from_user.id, room.code)
    
    await state.clear()
    await message.answer(f"✅ Вы присоединились к комнате `{room.code}`!", parse_mode="Markdown")
    await send_message(room, f"🎉 **{message.from_user.full_name}** присоединился к игре!")
    await show_lobby(message, room)


# ================== ИГРОВАЯ ЛОГИКА ==================
@router.callback_query(F.data.startswith("roll_"))
async def cb_roll(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room or not room.is_started:
        await callback.answer("Игра не идёт", show_alert=True)
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != callback.from_user.id:
        await callback.answer("Сейчас не ваш ход", show_alert=True)
        return
    
    await callback.answer()
    await do_roll(room)


@router.message(Command("roll"))
async def cmd_roll(message: Message):
    room_code = db.get_user_room(message.from_user.id)    if not room_code:
        await message.answer("Вы не в игре.")
        return
    
    room = db.get_room(room_code)
    if not room or not room.is_started:
        await message.answer("Игра не начата.")
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != message.from_user.id:
        await message.answer("Сейчас не ваш ход.")
        return
    
    await do_roll(room)


async def do_roll(room: Room):
    cur = room.current_player()
    if not cur:
        return

    if cur.in_jail:
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        if d1 == d2:
            cur.in_jail = False
            cur.jail_turns = 0
            db.update_player(room.code, cur)
            await send_message(room, f"🎲 {cur.name} выбросил {d1}+{d2} (дубль!) и вышел из тюрьмы!")
            await move_player(room, cur, d1 + d2)
        else:
            cur.jail_turns += 1
            db.update_player(room.code, cur)
            if cur.jail_turns >= 3:
                cur.pay(50)
                cur.in_jail = False
                cur.jail_turns = 0
                db.update_player(room.code, cur)
                await send_message(room, f"🎲 {cur.name} не выбросил дубль 3 хода. Платит 50 Ruzcoin и выходит.")
                await move_player(room, cur, d1 + d2)
            else:
                await send_message(room, f"🎲 {cur.name} в тюрьме. Выпало {d1}+{d2}. Осталось попыток: {3 - cur.jail_turns}")
                room.next_turn()
                db.update_room(room)
                await send_board(room, f"🔒 {cur.name} остаётся в тюрьме.")
                await maybe_bot_turn(room)
        return

    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2    await send_message(room, f"🎲 **{cur.name}** бросил кубики: **{d1} + {d2} = {total}**")
    await move_player(room, cur, total)


async def move_player(room: Room, player: Player, steps: int):
    old_pos = player.position
    new_pos = (player.position + steps) % 40

    if new_pos < old_pos and new_pos != 0:
        player.receive(200)
        db.update_player(room.code, player)
        await send_message(room, f"💰 {player.name} прошёл через СТАРТ и получил 200 Ruzcoin!")

    player.position = new_pos
    db.update_player(room.code, player)
    await process_cell(room, player)


async def process_cell(room: Room, player: Player):
    cell = BOARD[player.position]
    ctype = cell["type"]

    if ctype == "go":
        await send_board(room, f"🏁 {player.name} на СТАРТЕ.")
        await end_turn(room)
    elif ctype == "property":
        await handle_property(room, player, cell)
    elif ctype == "chance":
        card = random.choice(room.chance_deck)
        await apply_card(room, player, card, "🎲 ШАНС")
    elif ctype == "risk":
        card = random.choice(room.risk_deck)
        await apply_card(room, player, card, "⚠️ РИСК")
    elif ctype == "chest":
        amount = random.choice([50, 100, 150, 200])
        player.receive(amount)
        db.update_player(room.code, player)
        await send_board(room, f"💎 {player.name} получил {amount} Ruzcoin из Казны!")
        await end_turn(room)
    elif ctype == "tax":
        player.pay(cell["amount"])
        db.update_player(room.code, player)
        await send_board(room, f"💸 {player.name} платит налог {cell['amount']} Ruzcoin.")
        await end_turn(room)
    elif ctype == "jail":
        await send_board(room, f"👀 {player.name} просто навещает тюрьму.")
        await end_turn(room)
    elif ctype == "free_parking":
        await send_board(room, f"🅿️ {player.name} отдыхает на парковке.")
        await end_turn(room)    elif ctype == "go_to_jail":
        player.position = 10
        player.in_jail = True
        player.jail_turns = 0
        db.update_player(room.code, player)
        await send_board(room, f"🚔 {player.name} отправляется в ТЮРЬМУ!")
        await end_turn(room)


async def handle_property(room: Room, player: Player, cell):
    idx = player.position
    if idx in room.ownership:
        owner_id = room.ownership[idx]
        if owner_id == player.user_id:
            await send_board(room, f"🏠 {player.name} на своей территории: {cell['name']}")
            await end_turn(room)
        else:
            owner = room.players[owner_id]
            rent = cell["rent"]
            player.pay(rent)
            owner.receive(rent)
            db.update_player(room.code, player)
            db.update_player(room.code, owner)
            await send_board(room,
                f"💰 {player.name} платит {rent} Ruzcoin игроку **{owner.name}** за {cell['name']}.\n\n"
                f"💡 Хотите выкупить территорию? (Введите /buyout)")
            if player.is_active and player.money >= cell["price"] * 2:
                room.awaiting_buy = idx
                db.update_room(room)
                await send_board(room,
                    f"💼 {player.name} может принудительно выкупить {cell['name']} за {cell['price'] * 2} Ruzcoin!")
            await end_turn(room)
    else:
        if player.money >= cell["price"]:
            room.awaiting_buy = idx
            db.update_room(room)
            await send_board(room,
                f"🏡 Свободная территория: **{cell['name']}**\n"
                f"💵 Цена: {cell['price']} Ruzcoin\n"
                f"🏷️ Рента: {cell['rent']} Ruzcoin\n\n"
                f"Нажмите кнопку, чтобы купить!")
            if player.is_bot:
                await asyncio.sleep(1.5)
                player.pay(cell["price"])
                room.ownership[idx] = player.user_id
                db.set_ownership(room.code, idx, player.user_id)
                room.awaiting_buy = None
                db.update_room(room)
                db.update_player(room.code, player)
                await send_board(room, f"✅ {player.name} купил {cell['name']} за {cell['price']} Ruzcoin!")                await end_turn(room)
        else:
            await send_board(room, f"💸 У {player.name} недостаточно денег для покупки {cell['name']}.")
            await end_turn(room)


async def apply_card(room: Room, player: Player, card, title: str):
    text = f"{title}: {card['text']}"
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

    await send_board(room, text)
    await end_turn(room)


async def end_turn(room: Room):
    room.awaiting_buy = None
    room.next_turn()
    db.update_room(room)
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
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        await callback.answer("Комната не найдена", show_alert=True)
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != callback.from_user.id:
        await callback.answer("Не ваш ход", show_alert=True)
        return
    
    if room.awaiting_buy is None:
        await callback.answer("Нечего покупать", show_alert=True)
        return
    
    idx = room.awaiting_buy
    cell = BOARD[idx]
    if cur.money < cell["price"]:
        await callback.answer("Недостаточно Ruzcoin", show_alert=True)
        return
    
    cur.pay(cell["price"])
    room.ownership[idx] = cur.user_id
    db.set_ownership(room.code, idx, cur.user_id)
    room.awaiting_buy = None
    db.update_room(room)
    db.update_player(room.code, cur)
    
    await callback.answer(f"Куплено: {cell['name']}!")
    await send_board(room, f"✅ **{cur.name}** купил **{cell['name']}** за {cell['price']} Ruzcoin!")
    await end_turn(room)


@router.callback_query(F.data.startswith("skipbuy_"))
async def cb_skip_buy(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        return
    
    room.awaiting_buy = None
    db.update_room(room)
    await callback.answer()
    await send_board(room, f"❌ {callback.from_user.full_name} отказался от покупки.")
    await end_turn(room)


@router.callback_query(F.data.startswith("payjail_"))async def cb_pay_jail(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    room = db.get_room(code)
    if not room:
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != callback.from_user.id:
        await callback.answer("Не ваш ход", show_alert=True)
        return
    
    if cur.money < 50:
        await callback.answer("Недостаточно Ruzcoin", show_alert=True)
        return
    
    cur.pay(50)
    cur.in_jail = False
    cur.jail_turns = 0
    db.update_player(room.code, cur)
    
    await callback.answer()
    await send_board(room, f"💰 {cur.name} заплатил 50 Ruzcoin и вышел из тюрьмы!")
    await do_roll(room)


@router.message(Command("buyout"))
async def cmd_buyout(message: Message):
    room_code = db.get_user_room(message.from_user.id)
    if not room_code:
        await message.answer("Вы не в игре.")
        return
    
    room = db.get_room(room_code)
    if not room or not room.is_started:
        return
    
    cur = room.current_player()
    if not cur or cur.user_id != message.from_user.id:
        await message.answer("Сейчас не ваш ход.")
        return
    
    if room.awaiting_buy is None:
        await message.answer("Сейчас нет возможности выкупа.")
        return
    
    idx = room.awaiting_buy
    cell = BOARD[idx]
    price = cell["price"] * 2
    
    if cur.money < price:        await message.answer(f"Недостаточно Ruzcoin. Нужно: {price}")
        return
    
    owner_id = room.ownership.get(idx)
    if owner_id == cur.user_id:
        await message.answer("Это уже ваша территория.")
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
    
    await send_board(room, f"💼 **{cur.name}** принудительно выкупил **{cell['name']}** за {price} Ruzcoin!")
    await end_turn(room)


# ================== ИНФО ==================
@router.message(Command("room"))
async def cmd_room(message: Message):
    room_code = db.get_user_room(message.from_user.id)
    if not room_code:
        await message.answer("Вы не в комнате. Используйте /create или /join")
        return
    
    room = db.get_room(room_code)
    if not room:
        await message.answer("Комната не найдена.")
        return
    
    await show_lobby(message, room)


@router.message(Command("board"))
async def cmd_board(message: Message):
    room_code = db.get_user_room(message.from_user.id)
    if not room_code:
        await message.answer("Вы не в игре.")
        return
    
    room = db.get_room(room_code)
    if not room:        await message.answer("Комната не найдена.")
        return
    
    await send_board(room)


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "🎩 **RUZOPOLY - Команды**\n\n"
        "/start - Начать\n"
        "/create - Создать комнату\n"
        "/join - Присоединиться по коду\n"
        "/room - Информация о комнате\n"
        "/board - Показать поле\n"
        "/roll - Бросить кубики\n"
        "/buyout - Принудительный выкуп территории\n"
        "/help - Эта справка\n\n"
        "💰 Валюта: **Ruzcoin**\n"
        "🎲 Правила как в классической Монополии!"
    )
    await message.answer(text, parse_mode="Markdown")


# ================== ЗАПУСК ==================
async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
