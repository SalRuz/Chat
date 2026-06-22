import os
import io
import re
import logging
import random
import string
import asyncio
import sqlite3
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message
)
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise ValueError("BOT_TOKEN not found!")

logging.basicConfig(level=logging.INFO)

DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ruzopoly.db"

LAST_EDIT: Dict[int, float] = {}
MIN_EDIT_INTERVAL = 2.0

TRANSLATIONS = {
    'en': {
        'welcome': "🎩 Welcome to **RUZOPOLY**!\n\nMonopoly with **Ruzcoin** 💰\n\nChoose language:",
        'create_room': "🏠 Create Room", 'join_by_code': "🚪 Join by Code",
        'browse_rooms': "📋 Browse Rooms", 'choose_max_players': "👥 Max players:",
        'players': "players", 'password_question': "Max: {}. Password?",
        'with_password': "🔒 With Password", 'no_password': "🔓 No Password",
        'enter_password': "🔐 Enter password:", 'allow_buyout_question': "Allow buyout?",
        'allow_buyout': "✅ Allow", 'no_buyout': "❌ No",
        'choose_turn_time': "⏰ Turn time:", 'seconds_15': "15s", 'seconds_30': "30s", 'seconds_60': "60s",
        'room_info': "🏠 **Ruzopoly**\n🔑 `{}`\n🔒 `{}`\n👥 {}/{}\n💼 Buyout: {}\n⏰ {}s\n\n{}\n\nWaiting...",
        'enabled': 'On', 'disabled': 'Off', 'none': 'none',
        'add_bot': "🤖 Add Bot", 'start_game': "🚀 Start", 'refresh': "🔄 Refresh",
        'room_not_found': "Not found", 'room_full': "Full",
        'bot_added': "Bot {} added!", 'need_min_players': "Need 2+",
        'game_starting': "🎲 Starting!", 'game_started': "🎲 **Started!**",
        'player_turn': "🎮 **{}'s TURN**", 'roll_dice': "🎲 Roll Dice",
        'buy_property': "💵 Buy {} (${})", 'buyout_property': "💎 Buyout {} (${})",
        'sell_property': "💰 Sell {} (${})", 'build_house': "🏠 Build on {} (${})",
        'skip': "❌ Skip", 'pay_jail': "💰 Pay $150",
        'not_your_turn': "Not your turn",
        'rolled': "🎲 {} rolled: {}+{}={}", 'doubles': "🎲 {} DOUBLES!",
        'third_double': "🎲 {} 3rd DOUBLE! JAIL!",
        'passed_start': "💰 {} passed START +$200", 'at_start': "🏁 {} on START +$200",
        'chest_reward': "💎 {} +${} Chest!", 'tax_paid': "💸 {} -${}",
        'visiting_jail': "👀 {} visiting jail", 'at_parking': "🅿️ {} parking",
        'go_to_jail': "🚔 {} JAIL!", 'rent_paid': "💰 {} -${} → {} ({})",
        'own_property': "🏠 {} on own: {}", 'free_property': "🏡 Free: **{}** ${} (rent ${})",
        'not_enough_money': "💸 {} broke", 'property_bought': "✅ {} bought {} ${}!",
        'property_buyout': "💎 {} bought {} from {} ${}!",
        'purchase_declined': "❌ {} skipped", 'timeout': "⏰ {} timeout",
        'jail_doubles': "🎲 {} {}+{} free!", 'jail_no_doubles': "🎲 {} jail {}+{} left:{}",
        'jail_pay_forced': "🎲 {} pays $150 out", 'jail_paid_out': "💰 {} $150 free!",
        'available_rooms': "📋 **Rooms:**\n\n", 'no_rooms': "📋 No rooms",
        'join': "Join {}", 'back': "« Back", 'enter_room_code': "🔑 Code:",
        'room_has_password': "🔒 Password:", 'wrong_password': "❌ Wrong",
        'already_in_room': "Already in!", 'joined_room': "✅ Joined `{}`!",
        'only_creator_start': "Only creator!", 'not_enough_ruzcoin': "No money",
        'nothing_to_buy': "Nothing", 'language_selected': "English 🇬🇧",
        'player_eliminated': "💀 {} out!", 'player_won': "🏆 {} WON!",
        'game_over': "🎮 Game Over!", 'debt_warning': "⚠️ {} debt! Sell.",
        'property_sold': "💰 {} sold {} ${}",
        'all_stations_owned': "🚉 {} all RR!", 'three_streets_owned': "🏘️ {} 3 groups!",
        'moving_countdown': "⏱️ Moving {}...", 'turn_end_countdown': "⏱️ Ends {}...",
        'decision_time': "⏱️ {} deciding {}s", 'waiting': "⏳ Wait...",
        'doubles_turn': "🎲 {} extra turn!",
        'house_built': "🏠 {} built on {} ({}→{})", 'hotel_built': "🏨 {} hotel on {}!",
        'max_houses': "Max built!", 'trade': "🔄 Trade",
        'trade_select_player': "🔄 Trade with whom?", 'trade_select_want': "What do you want?",
        'trade_select_give': "What do you give?", 'trade_enter_money': "💰 Enter amount:",
        'trade_money': "💰 Money", 'trade_cancel': "❌ Cancel",
        'trade_confirm': "✅ Accept", 'trade_reject': "❌ Decline",
        'trade_proposal': "🔄 **Trade from {}:**\nWants: {}\nGives: {}\nAccept?",
        'trade_accepted': "🔄 Trade done! {} ↔ {}", 'trade_rejected': "🔄 {} declined trade",
        'trade_sent': "🔄 Trade sent to {}", 'auto_roll': "🎲 Auto-roll for {}!",
        'auto_skip': "⏰ Auto-skip for {}",
    },
    'ru': {
        'welcome': "🎩 **RUZOPOLY**!\n\nМонополия с **Ruzcoin** 💰\n\nЯзык:",
        'create_room': "🏠 Создать", 'join_by_code': "🚪 По коду",
        'browse_rooms': "📋 Список", 'choose_max_players': "👥 Макс:",
        'players': "игр.", 'password_question': "Макс: {}. Пароль?",
        'with_password': "🔒 Да", 'no_password': "🔓 Нет",
        'enter_password': "🔐 Пароль:", 'allow_buyout_question': "Выкуп?",
        'allow_buyout': "✅ Да", 'no_buyout': "❌ Нет",
        'choose_turn_time': "⏰ Время:", 'seconds_15': "15с", 'seconds_30': "30с", 'seconds_60': "60с",
        'room_info': "🏠 **Ruzopoly**\n🔑 `{}`\n🔒 `{}`\n👥 {}/{}\n💼 {}\n⏰ {}с\n\n{}\n\nЖдём...",
        'enabled': 'Вкл', 'disabled': 'Выкл', 'none': 'нет',
        'add_bot': "🤖 Бот", 'start_game': "🚀 Старт", 'refresh': "🔄",
        'room_not_found': "Не найдена", 'room_full': "Полна",
        'bot_added': "Бот {} добавлен!", 'need_min_players': "Мин 2",
        'game_starting': "🎲 Старт!", 'game_started': "🎲 **Началась!**",
        'player_turn': "🎮 **ХОД: {}**", 'roll_dice': "🎲 Бросить",
        'buy_property': "💵 Купить {} (${})", 'buyout_property': "💎 Выкупить {} (${})",
        'sell_property': "💰 Продать {} (${})", 'build_house': "🏠 Строить {} (${})",
        'skip': "❌ Пропуск", 'pay_jail': "💰 $150 выйти",
        'not_your_turn': "Не ваш ход",
        'rolled': "🎲 {} бросил: {}+{}={}", 'doubles': "🎲 {} ДУБЛЬ!",
        'third_double': "🎲 {} 3й ДУБЛЬ! ТЮРЬМА!",
        'passed_start': "💰 {} СТАРТ +$200", 'at_start': "🏁 {} СТАРТ +$200",
        'chest_reward': "💎 {} +${} Казна!", 'tax_paid': "💸 {} -${}",
        'visiting_jail': "👀 {} тюрьма", 'at_parking': "🅿️ {} парковка",
        'go_to_jail': "🚔 {} ТЮРЬМА!", 'rent_paid': "💰 {} -${} → {} ({})",
        'own_property': "🏠 {} своя: {}", 'free_property': "🏡 Свободно: **{}** ${} (рента ${})",
        'not_enough_money': "💸 {} мало", 'property_bought': "✅ {} купил {} ${}!",
        'property_buyout': "💎 {} выкупил {} у {} ${}!",
        'purchase_declined': "❌ {} пропустил", 'timeout': "⏰ {} время",
        'jail_doubles': "🎲 {} {}+{} свободен!", 'jail_no_doubles': "🎲 {} тюрьма {}+{} ост:{}",
        'jail_pay_forced': "🎲 {} $150 выход", 'jail_paid_out': "💰 {} $150 свободен!",
        'available_rooms': "📋 **Комнаты:**\n\n", 'no_rooms': "📋 Нет",
        'join': "Войти {}", 'back': "« Назад", 'enter_room_code': "🔑 Код:",
        'room_has_password': "🔒 Пароль:", 'wrong_password': "❌ Неверно",
        'already_in_room': "Уже здесь!", 'joined_room': "✅ Вошли `{}`!",
        'only_creator_start': "Только создатель!", 'not_enough_ruzcoin': "Мало денег",
        'nothing_to_buy': "Нечего", 'language_selected': "Русский 🇷🇺",
        'player_eliminated': "💀 {} выбыл!", 'player_won': "🏆 {} ПОБЕДИЛ!",
        'game_over': "🎮 Конец!", 'debt_warning': "⚠️ {} долг! Продавай.",
        'property_sold': "💰 {} продал {} ${}",
        'all_stations_owned': "🚉 {} все вокзалы!", 'three_streets_owned': "🏘️ {} 3 группы!",
        'moving_countdown': "⏱️ Ход {}...", 'turn_end_countdown': "⏱️ Конец {}...",
        'decision_time': "⏱️ {} решает {}с", 'waiting': "⏳ Ждите...",
        'doubles_turn': "🎲 {} ещё ход!",
        'house_built': "🏠 {} строит на {} ({}→{})", 'hotel_built': "🏨 {} отель {}!",
        'max_houses': "Максимум!", 'trade': "🔄 Обмен",
        'trade_select_player': "🔄 С кем обмен?", 'trade_select_want': "Что хотите получить?",
        'trade_select_give': "Что отдаёте?", 'trade_enter_money': "💰 Введите сумму:",
        'trade_money': "💰 Деньги", 'trade_cancel': "❌ Отмена",
        'trade_confirm': "✅ Принять", 'trade_reject': "❌ Отклонить",
        'trade_proposal': "🔄 **Обмен от {}:**\nХочет: {}\nОтдаёт: {}\nПринять?",
        'trade_accepted': "🔄 Обмен! {} ↔ {}", 'trade_rejected': "🔄 {} отклонил обмен",
        'trade_sent': "🔄 Обмен отправлен {}", 'auto_roll': "🎲 Авто-бросок {}!",
        'auto_skip': "⏰ Авто-пропуск {}",
    }
}


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if c.fetchone():
        c.execute("PRAGMA table_info(users)")
        cols = [x[1] for x in c.fetchall()]
        if 'language' not in cols: c.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en'")
    else:
        c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,language TEXT DEFAULT 'en',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
    if c.fetchone():
        c.execute("PRAGMA table_info(rooms)")
        cols = [x[1] for x in c.fetchall()]
        for col, td in [('language','TEXT DEFAULT "en"'),('player_ids','TEXT DEFAULT "[]"'),('allow_buyout','BOOLEAN DEFAULT 1'),('turn_time','INTEGER DEFAULT 30'),('awaiting_buyout','BOOLEAN DEFAULT 0')]:
            if col not in cols: c.execute(f"ALTER TABLE rooms ADD COLUMN {col} {td}")
    else:
        c.execute("CREATE TABLE rooms(code TEXT PRIMARY KEY,creator_id INTEGER,chat_id INTEGER,max_players INTEGER,password TEXT,current_turn INTEGER DEFAULT 0,is_started BOOLEAN DEFAULT 0,last_message_id INTEGER,chance_deck TEXT,risk_deck TEXT,awaiting_buy INTEGER,awaiting_buyout BOOLEAN DEFAULT 0,language TEXT DEFAULT 'en',player_ids TEXT DEFAULT '[]',allow_buyout BOOLEAN DEFAULT 1,turn_time INTEGER DEFAULT 30,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS players(room_code TEXT,user_id INTEGER,name TEXT,money INTEGER DEFAULT 1500,position INTEGER DEFAULT 0,color TEXT,is_bot BOOLEAN DEFAULT 0,in_jail BOOLEAN DEFAULT 0,jail_turns INTEGER DEFAULT 0,is_active BOOLEAN DEFAULT 1,doubles_count INTEGER DEFAULT 0,PRIMARY KEY(room_code,user_id))")
    c.execute("PRAGMA table_info(players)")
    if 'doubles_count' not in [x[1] for x in c.fetchall()]: c.execute("ALTER TABLE players ADD COLUMN doubles_count INTEGER DEFAULT 0")
    c.execute("CREATE TABLE IF NOT EXISTS ownership(room_code TEXT,cell_idx INTEGER,owner_id INTEGER,houses INTEGER DEFAULT 0,PRIMARY KEY(room_code,cell_idx))")
    c.execute("PRAGMA table_info(ownership)")
    if 'houses' not in [x[1] for x in c.fetchall()]: c.execute("ALTER TABLE ownership ADD COLUMN houses INTEGER DEFAULT 0")
    c.execute("CREATE TABLE IF NOT EXISTS user_room(user_id INTEGER PRIMARY KEY,room_code TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS player_messages(room_code TEXT,user_id INTEGER,message_id INTEGER,PRIMARY KEY(room_code,user_id))")
    conn.commit(); conn.close()

init_db()

ROOM_STATES: Dict[str, dict] = {}

def get_room_state(code):
    if code not in ROOM_STATES:
        ROOM_STATES[code] = {'event_log':[],'in_cooldown':False,'is_moving':False,'emojis':{},'trades':{},'turn_timer':None}
    return ROOM_STATES[code]

def clear_room_state(code):
    st = ROOM_STATES.pop(code, None)
    if st and st.get('turn_timer'):
        st['turn_timer'].cancel()

GROUP_COLORS_HEX = {"brown":"#8B4513","lightblue":"#87CEEB","pink":"#FF69B4","orange":"#FFA500","red":"#FF3030","yellow":"#FFD700","green":"#2E8B57","darkblue":"#1E3A8A"}

BOARD = [
    {"name":"START","type":"go"},
    {"name":"Mediterranean","type":"property","group":"brown","price":60,"rent":[2,10,30,90,160,250],"house":50},
    {"name":"Chest","type":"chest"},
    {"name":"Baltic Ave","type":"property","group":"brown","price":60,"rent":[4,20,60,180,320,450],"house":50},
    {"name":"Income Tax","type":"tax","amount":200},
    {"name":"Reading RR","type":"property","group":"station","price":200,"rent":[25,50,100,200]},
    {"name":"Oriental Ave","type":"property","group":"lightblue","price":100,"rent":[6,30,90,270,400,550],"house":50},
    {"name":"Chance","type":"chance"},
    {"name":"Vermont Ave","type":"property","group":"lightblue","price":100,"rent":[6,30,90,270,400,550],"house":50},
    {"name":"Connecticut","type":"property","group":"lightblue","price":120,"rent":[8,40,100,300,450,600],"house":50},
    {"name":"JAIL","type":"jail"},
    {"name":"St.Charles","type":"property","group":"pink","price":140,"rent":[10,50,150,450,625,750],"house":100},
    {"name":"Electric Co","type":"property","group":"utility","price":150,"rent":[4,10]},
    {"name":"States Ave","type":"property","group":"pink","price":140,"rent":[10,50,150,450,625,750],"house":100},
    {"name":"Virginia Ave","type":"property","group":"pink","price":160,"rent":[12,60,180,500,700,900],"house":100},
    {"name":"Pennsylvania RR","type":"property","group":"station","price":200,"rent":[25,50,100,200]},
    {"name":"St.James","type":"property","group":"orange","price":180,"rent":[14,70,200,550,750,950],"house":100},
    {"name":"Chest","type":"chest"},
    {"name":"Tennessee","type":"property","group":"orange","price":180,"rent":[14,70,200,550,750,950],"house":100},
    {"name":"New York Ave","type":"property","group":"orange","price":200,"rent":[16,80,220,600,800,1000],"house":100},
    {"name":"PARKING","type":"free_parking"},
    {"name":"Kentucky Ave","type":"property","group":"red","price":220,"rent":[18,90,250,700,875,1050],"house":150},
    {"name":"Chance","type":"chance"},
    {"name":"Indiana Ave","type":"property","group":"red","price":220,"rent":[18,90,250,700,875,1050],"house":150},
    {"name":"Illinois Ave","type":"property","group":"red","price":240,"rent":[20,100,300,750,925,1100],"house":150},
    {"name":"B&O RR","type":"property","group":"station","price":200,"rent":[25,50,100,200]},
    {"name":"Atlantic Ave","type":"property","group":"yellow","price":260,"rent":[22,110,330,800,975,1150],"house":150},
    {"name":"Ventnor Ave","type":"property","group":"yellow","price":260,"rent":[22,110,330,800,975,1150],"house":150},
    {"name":"Water Works","type":"property","group":"utility","price":150,"rent":[4,10]},
    {"name":"Marvin Gdns","type":"property","group":"yellow","price":280,"rent":[24,120,360,850,1025,1200],"house":150},
    {"name":"GO TO JAIL","type":"go_to_jail"},
    {"name":"Pacific Ave","type":"property","group":"green","price":300,"rent":[26,130,390,900,1100,1275],"house":200},
    {"name":"N.Carolina","type":"property","group":"green","price":300,"rent":[26,130,390,900,1100,1275],"house":200},
    {"name":"Chest","type":"chest"},
    {"name":"Pennsylvania","type":"property","group":"green","price":320,"rent":[28,150,450,1000,1200,1400],"house":200},
    {"name":"Short Line RR","type":"property","group":"station","price":200,"rent":[25,50,100,200]},
    {"name":"Chance","type":"chance"},
    {"name":"Park Place","type":"property","group":"darkblue","price":350,"rent":[35,175,500,1100,1300,1500],"house":200},
    {"name":"Luxury Tax","type":"tax","amount":75},
    {"name":"Boardwalk","type":"property","group":"darkblue","price":400,"rent":[50,200,600,1400,1700,2000],"house":200},
]

CHANCE_CARDS = [
    {"text":"🎉 Lottery +$200","text_ru":"🎉 Лотерея +$200","effect":200},
    {"text":"🚗 Fine -$50","text_ru":"🚗 Штраф -$50","effect":-50},
    {"text":"🏦 Dividends +$100","text_ru":"🏦 Дивиденды +$100","effect":100},
    {"text":"🚓 Fine -$100","text_ru":"🚓 Штраф -$100","effect":-100},
    {"text":"🎂 Birthday +$50/p","text_ru":"🎂 ДР +$50/игрок","effect":"birthday"},
    {"text":"📈 Stocks +$150","text_ru":"📈 Акции +$150","effect":150},
    {"text":"🔧 Repairs -$100","text_ru":"🔧 Ремонт -$100","effect":-100},
    {"text":"🎁 Gift +$100","text_ru":"🎁 Подарок +$100","effect":100},
]
RISK_CARDS = [
    {"text":"💸 Tax -$150","text_ru":"💸 Налог -$150","effect":-150},
    {"text":"🎁 Gift +$100","text_ru":"🎁 Подарок +$100","effect":100},
    {"text":"🏥 Hospital -$100","text_ru":"🏥 Больница -$100","effect":-100},
    {"text":"💼 Bonus +$200","text_ru":"💼 Премия +$200","effect":200},
    {"text":"📚 School -$50","text_ru":"📚 Учёба -$50","effect":-50},
    {"text":"🎰 Casino +$250","text_ru":"🎰 Казино +$250","effect":250},
]
PLAYER_COLORS = ["#E74C3C","#3498DB","#2ECC71","#F1C40F","#9B59B6","#E67E22","#1ABC9C","#FF69B4"]

EMOJI_RE = re.compile("["
    "\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
    "\U0001f900-\U0001f9FF\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff"
    "\U00002600-\U000026FF\U0000200D\U00002640-\U00002642]+")


@dataclass
class Player:
    user_id:int; name:str; money:int=1500; position:int=0; color:str="#FFF"
    is_bot:bool=False; in_jail:bool=False; jail_turns:int=0; is_active:bool=True; doubles_count:int=0
    def pay(self,a): self.money-=a
    def receive(self,a): self.money+=a

@dataclass
class Room:
    code:str; creator_id:int; chat_id:int; max_players:int; password:Optional[str]=None
    players:Dict[int,Player]=field(default_factory=dict); ownership:Dict[int,Tuple[int,int]]=field(default_factory=dict)
    current_turn:int=0; is_started:bool=False; last_message_id:Optional[int]=None
    chance_deck:list=field(default_factory=lambda:CHANCE_CARDS.copy()); risk_deck:list=field(default_factory=lambda:RISK_CARDS.copy())
    awaiting_buy:Optional[int]=None; awaiting_buyout:bool=False; turn_timer_task:Optional[asyncio.Task]=None
    language:str='en'; player_ids:Set[int]=field(default_factory=set); allow_buyout:bool=True
    turn_time:int=30; player_message_ids:Dict[int,int]=field(default_factory=dict); can_roll:bool=True

    def active_players(self): return [p for p in self.players.values() if p.is_active]
    def current_player(self):
        a=self.active_players()
        return a[self.current_turn%len(a)] if a else None
    def next_turn(self):
        a=self.active_players()
        if a: self.current_turn=(self.current_turn+1)%len(a)
    def add_event(self,e):
        s=get_room_state(self.code); s['event_log'].append(e)
        if len(s['event_log'])>8: s['event_log'].pop(0)


class Database:
    @staticmethod
    def save_user(uid,uname,lang='en'):
        conn=sqlite3.connect(str(DB_PATH))
        try:
            c=conn.cursor(); c.execute("SELECT id FROM users WHERE id=?",(uid,))
            if c.fetchone(): conn.execute("UPDATE users SET username=? WHERE id=?",(uname,uid))
            else: conn.execute("INSERT INTO users(id,username,language) VALUES(?,?,?)",(uid,uname,lang))
            conn.commit()
        finally: conn.close()
    @staticmethod
    def get_user_language(uid):
        conn=sqlite3.connect(str(DB_PATH))
        try:
            c=conn.cursor(); c.execute("SELECT language FROM users WHERE id=?",(uid,))
            r=c.fetchone(); return r[0] if r else 'en'
        except: return 'en'
        finally: conn.close()
    @staticmethod
    def set_user_language(uid,lang):
        conn=sqlite3.connect(str(DB_PATH))
        try: conn.execute("UPDATE users SET language=? WHERE id=?",(lang,uid)); conn.commit()
        finally: conn.close()
    @staticmethod
    def create_room(room):
        conn=sqlite3.connect(str(DB_PATH))
        try:
            conn.execute("INSERT INTO rooms(code,creator_id,chat_id,max_players,password,current_turn,is_started,last_message_id,chance_deck,risk_deck,awaiting_buy,awaiting_buyout,language,player_ids,allow_buyout,turn_time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (room.code,room.creator_id,room.chat_id,room.max_players,room.password,room.current_turn,room.is_started,room.last_message_id,json.dumps(room.chance_deck),json.dumps(room.risk_deck),room.awaiting_buy,room.awaiting_buyout,room.language,json.dumps(list(room.player_ids)),room.allow_buyout,room.turn_time))
            conn.commit(); return True
        except sqlite3.IntegrityError: return False
        finally: conn.close()
    @staticmethod
    def get_room(code):
        conn=sqlite3.connect(str(DB_PATH))
        try:
            c=conn.cursor(); c.execute("SELECT * FROM rooms WHERE code=?",(code,))
            row=c.fetchone()
            if not row: return None
            cn=[d[0] for d in c.description]; r=dict(zip(cn,row))
            room=Room(code=r['code'],creator_id=r['creator_id'],chat_id=r['chat_id'],max_players=r['max_players'],password=r['password'],current_turn=r['current_turn'],is_started=bool(r['is_started']),last_message_id=r['last_message_id'],
                chance_deck=json.loads(r['chance_deck']) if r['chance_deck'] else CHANCE_CARDS.copy(),
                risk_deck=json.loads(r['risk_deck']) if r['risk_deck'] else RISK_CARDS.copy(),
                awaiting_buy=r['awaiting_buy'],awaiting_buyout=bool(r.get('awaiting_buyout',0)),
                language=r.get('language','en'),player_ids=set(json.loads(r['player_ids'])) if r.get('player_ids') else set(),
                allow_buyout=bool(r.get('allow_buyout',1)),turn_time=r.get('turn_time',30))
            c.execute("SELECT * FROM players WHERE room_code=?",(code,))
            pcn=[d[0] for d in c.description]
            for pr in c.fetchall():
                p=dict(zip(pcn,pr))
                room.players[p['user_id']]=Player(user_id=p['user_id'],name=p['name'],money=p['money'],position=p['position'],color=p['color'],is_bot=bool(p['is_bot']),in_jail=bool(p['in_jail']),jail_turns=p['jail_turns'],is_active=bool(p['is_active']),doubles_count=p.get('doubles_count',0))
                room.player_ids.add(p['user_id'])
            c.execute("SELECT cell_idx,owner_id,houses FROM ownership WHERE room_code=?",(code,))
            for o in c.fetchall(): room.ownership[o[0]]=(o[1],o[2])
            c.execute("SELECT user_id,message_id FROM player_messages WHERE room_code=?",(code,))
            for m in c.fetchall(): room.player_message_ids[m[0]]=m[1]
            return room
        finally: conn.close()
    @staticmethod
    def update_room(room):
        conn=sqlite3.connect(str(DB_PATH))
        try:
            conn.execute("UPDATE rooms SET current_turn=?,is_started=?,last_message_id=?,chance_deck=?,risk_deck=?,awaiting_buy=?,awaiting_buyout=?,language=?,player_ids=?,allow_buyout=?,turn_time=? WHERE code=?",
                (room.current_turn,room.is_started,room.last_message_id,json.dumps(room.chance_deck),json.dumps(room.risk_deck),room.awaiting_buy,room.awaiting_buyout,room.language,json.dumps(list(room.player_ids)),room.allow_buyout,room.turn_time,room.code))
            conn.commit()
        except Exception as e: logging.error(f"update_room:{e}")
        finally: conn.close()
    @staticmethod
    def add_player(code,player):
        conn=sqlite3.connect(str(DB_PATH))
        try:
            conn.execute("INSERT INTO players(room_code,user_id,name,money,position,color,is_bot,in_jail,jail_turns,is_active,doubles_count) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (code,player.user_id,player.name,player.money,player.position,player.color,player.is_bot,player.in_jail,player.jail_turns,player.is_active,player.doubles_count))
            conn.commit(); return True
        except sqlite3.IntegrityError: return False
        finally: conn.close()
    @staticmethod
    def update_player(code,player):
        conn=sqlite3.connect(str(DB_PATH))
        try:
            conn.execute("UPDATE players SET money=?,position=?,in_jail=?,jail_turns=?,is_active=?,doubles_count=? WHERE room_code=? AND user_id=?",
                (player.money,player.position,player.in_jail,player.jail_turns,player.is_active,player.doubles_count,code,player.user_id))
            conn.commit()
        except Exception as e: logging.error(f"update_player:{e}")
        finally: conn.close()
    @staticmethod
    def set_ownership(code,idx,oid,houses=0):
        conn=sqlite3.connect(str(DB_PATH))
        try: conn.execute("INSERT OR REPLACE INTO ownership(room_code,cell_idx,owner_id,houses) VALUES(?,?,?,?)",(code,idx,oid,houses)); conn.commit()
        finally: conn.close()
    @staticmethod
    def remove_ownership(code,idx):
        conn=sqlite3.connect(str(DB_PATH))
        try: conn.execute("DELETE FROM ownership WHERE room_code=? AND cell_idx=?",(code,idx)); conn.commit()
        finally: conn.close()
    @staticmethod
    def set_user_room(uid,code):
        conn=sqlite3.connect(str(DB_PATH))
        try: conn.execute("INSERT OR REPLACE INTO user_room(user_id,room_code) VALUES(?,?)",(uid,code)); conn.commit()
        finally: conn.close()
    @staticmethod
    def get_all_rooms():
        conn=sqlite3.connect(str(DB_PATH)); c=conn.cursor()
        try:
            c.execute("SELECT code,password,max_players FROM rooms WHERE is_started=0")
            rooms=[]
            for row in c.fetchall():
                c.execute("SELECT COUNT(*) FROM players WHERE room_code=?",(row[0],))
                rooms.append({'code':row[0],'has_password':bool(row[1]),'max_players':row[2],'current_players':c.fetchone()[0]})
            return rooms
        finally: conn.close()
    @staticmethod
    def set_player_message_id(code,uid,mid):
        conn=sqlite3.connect(str(DB_PATH))
        try: conn.execute("INSERT OR REPLACE INTO player_messages(room_code,user_id,message_id) VALUES(?,?,?)",(code,uid,mid)); conn.commit()
        finally: conn.close()

db=Database()

def generate_code(): return ''.join(random.choices(string.ascii_uppercase+string.digits,k=6))
def get_available_color(room):
    used={p.color for p in room.players.values()}
    a=[c for c in PLAYER_COLORS if c not in used]
    return random.choice(a) if a else "#FFF"
def t(key,lang='en',*args):
    text=TRANSLATIONS.get(lang,TRANSLATIONS['en']).get(key,key)
    if args:
        try: return text.format(*args)
        except: return text
    return text
def owns_full_group(room,pid,group):
    cells=[i for i,c in enumerate(BOARD) if c.get("group")==group]
    return all(i in room.ownership and room.ownership[i][0]==pid for i in cells)
def calc_rent(cell,houses,cnt=1,dice=0,full=False):
    g=cell.get("group")
    if g=="station": return cell["rent"][min(cnt-1,3)]
    elif g=="utility": return (cell["rent"][0] if cnt==1 else cell["rent"][1])*max(dice,7)
    else:
        r=cell["rent"][min(houses,5)]
        return r*2 if houses==0 and full else r
def buyout_price(cell,h): return int(cell.get("price",0)*1.5+h*cell.get("house",50))
def sell_price(cell,h): return int(cell.get("price",0)*0.5+h*cell.get("house",50)*0.5)
def get_props(room,pid):
    return [(i,BOARD[i],h) for i,(oid,h) in room.ownership.items() if oid==pid and BOARD[i]["type"]=="property"]
def count_stations(room,pid): return sum(1 for i,c in enumerate(BOARD) if c.get("group")=="station" and i in room.ownership and room.ownership[i][0]==pid)
def count_utils(room,pid): return sum(1 for i,c in enumerate(BOARD) if c.get("group")=="utility" and i in room.ownership and room.ownership[i][0]==pid)
def all_stations(room,pid): return count_stations(room,pid)==4
def three_streets(room,pid):
    return sum(1 for g in ["brown","lightblue","pink","orange","red","yellow","green","darkblue"] if owns_full_group(room,pid,g))>=3
def can_build(room,pid,idx):
    cell=BOARD[idx]
    if cell["type"]!="property" or cell.get("group") in ["station","utility"]: return False,0
    if idx not in room.ownership: return False,0
    oid,h=room.ownership[idx]
    if oid!=pid or h>=5: return False,0
    if not owns_full_group(room,pid,cell["group"]): return False,0
    cost=cell.get("house",50)
    p=room.players.get(pid)
    if not p or p.money<cost: return False,0
    return True,cost

def render_board(room):
    size=900; img=Image.new('RGB',(size,size),"#F5E9D3"); draw=ImageDraw.Draw(img)
    try:
        fb=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",10)
        fs=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",8)
        ft=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",20)
    except: fb=fs=ft=ImageFont.load_default()
    cs=size/11
    for idx in range(40):
        c=BOARD[idx]; x1,y1,x2,y2=_cr(idx,cs)
        bg="#FFF8DC"
        tp=c["type"]
        if tp=="go": bg="#FFE4B5"
        elif tp=="jail": bg="#FFDAB9"
        elif tp=="free_parking": bg="#D3D3D3"
        elif tp=="go_to_jail": bg="#FFB6C1"
        elif tp=="chance": bg="#FFFACD"
        elif tp=="chest": bg="#E0FFFF"
        elif tp=="tax": bg="#F0E68C"
        if idx in room.ownership:
            ow=room.players.get(room.ownership[idx][0])
            if ow: bg=ow.color
        draw.rectangle([x1,y1,x2,y2],fill=bg,outline="#333",width=2)
        if tp=="property" and c.get("group") in GROUP_COLORS_HEX:
            gc=GROUP_COLORS_HEX[c["group"]]
            if idx<=10: draw.rectangle([x1+2,y2-12,x2-2,y2-2],fill=gc)
            elif idx<=20: draw.rectangle([x2-12,y1+2,x2-2,y2-2],fill=gc)
            elif idx<=30: draw.rectangle([x1+2,y1+2,x2-2,y1+12],fill=gc)
            else: draw.rectangle([x1+2,y1+2,x1+12,y2-2],fill=gc)
        if idx in room.ownership:
            _,h=room.ownership[idx]
            if h>0: draw.text((x1+3,y1+28),("🏠"*min(h,4) if h<5 else "🏨"),fill="#000",font=fs)
        draw.text((x1+3,y1+3),c["name"][:12],fill="#000",font=fb)
        if tp=="property": draw.text((x1+3,y1+16),f"${c['price']}",fill="#555",font=fs)
    for i,p in enumerate(room.active_players()):
        x1,y1,x2,y2=_cr(p.position,cs)
        cx=x1+10+(i%3)*14; cy=y1+40+(i//3)*14
        draw.ellipse([cx-7,cy-7,cx+7,cy+7],fill=p.color,outline="#000",width=2)
        draw.text((cx-3,cy-5),str(i+1),fill="#FFF",font=fs)
    cx,cy=size//2,size//2
    draw.rectangle([cx-150,cy-80,cx+150,cy+80],fill="#FFF8DC",outline="#333",width=2)
    draw.text((cx-55,cy-70),"RUZOPOLY",fill="#2C3E50",font=ft)
    cur=room.current_player()
    if cur and room.is_started:
        draw.text((cx-140,cy-35),f"{cur.name}",fill="#000",font=fb)
        draw.text((cx-140,cy-15),f"${cur.money}",fill="#DAA520",font=fb)
        draw.text((cx-140,cy+5),BOARD[cur.position]['name'],fill="#555",font=fs)
    buf=io.BytesIO(); img.save(buf,format="PNG"); buf.seek(0); return buf.getvalue()

def _cr(idx,cs):
    if idx<=10: col,row=10-idx,10
    elif idx<=20: col,row=0,10-(idx-10)
    elif idx<=30: col,row=idx-20,0
    else: col,row=10,idx-30
    return col*cs,row*cs,(col+1)*cs,(row+1)*cs

class CreateRoom(StatesGroup):
    wait_max=State(); wait_password=State(); wait_buyout=State(); wait_turn_time=State()
class JoinRoom(StatesGroup):
    wait_code=State(); wait_password=State()
class TradeMoneyInput(StatesGroup):
    waiting=State()

bot=Bot(token=API_TOKEN)
storage=MemoryStorage()
dp=Dispatcher(storage=storage)
router=Router()
dp.include_router(router)

# ─── TURN TIMER (auto-roll after turn_time) ───
async def start_turn_timer(room_code):
    """Start timer for current player's turn. Auto-rolls if time runs out."""
    st=get_room_state(room_code)
    if st.get('turn_timer') and not st['turn_timer'].done():
        st['turn_timer'].cancel()
    st['turn_timer']=asyncio.create_task(_turn_timer_task(room_code))

async def _turn_timer_task(room_code):
    room=db.get_room(room_code)
    if not room or not room.is_started: return
    cur=room.current_player()
    if not cur or cur.is_bot: return
    try:
        await asyncio.sleep(room.turn_time)
    except asyncio.CancelledError:
        return
    room=db.get_room(room_code)
    if not room or not room.is_started: return
    cur=room.current_player()
    if not cur: return
    if room.can_roll and room.awaiting_buy is None:
        room.add_event(t('auto_roll',room.language,cur.name))
        await do_roll(room)
    elif room.awaiting_buy is not None:
        room.add_event(t('auto_skip',room.language,cur.name))
        room.awaiting_buy=None; room.awaiting_buyout=False; db.update_room(room)
        if cur.doubles_count>0:
            room.can_roll=True; db.update_room(room)
            await send_board(room); await maybe_bot(room)
        else:
            await delay(room.code,3,'turn_end_countdown')
            await end_turn(room)

async def buy_timeout(room_code):
    """15 sec timeout for buy decision"""
    await asyncio.sleep(15)
    room=db.get_room(room_code)
    if not room or not room.is_started or room.awaiting_buy is None: return
    cur=room.current_player()
    if not cur: return
    room.add_event(t('auto_skip',room.language,cur.name))
    room.awaiting_buy=None; room.awaiting_buyout=False; db.update_room(room)
    if cur.doubles_count>0:
        room.can_roll=True; db.update_room(room)
        await send_board(room); await maybe_bot(room)
    else:
        await delay(room.code,3,'turn_end_countdown')
        await end_turn(room)

async def delay(code,secs,key):
    room=db.get_room(code)
    if not room: return
    st=get_room_state(code); st['in_cooldown']=True
    if key=='moving_countdown': st['is_moving']=True
    last=0
    for r in range(secs,0,-1):
        await asyncio.sleep(1)
        now=time.time()
        if now-last>=3 or r==secs or r==1:
            last=now; room=db.get_room(code)
            if not room: break
            await send_board(room,timer_text=t(key,room.language,r))
    st['in_cooldown']=False
    if key=='moving_countdown': st['is_moving']=False

async def send_board(room,force=False,timer_text=None):
    img=render_board(room); cur=room.current_player(); st=get_room_state(room.code); now=time.time()
    text=""
    if timer_text: text+=f"{timer_text}\n"
    if st['event_log']: text+="\n".join(st['event_log'][-4:])+"\n"
    text+=f"\n🎲 **RUZOPOLY** `{room.code}`\n"
    if cur:
        text+=f"👑 {cur.name} ${cur.money}\n📍 {BOARD[cur.position]['name']}\n"
        if cur.doubles_count>0: text+=f"🎯 x{cur.doubles_count}\n"
    text+="\n💰 **Players:**\n"
    for p in room.players.values():
        mk="▶️" if cur and p.user_id==cur.user_id else "  "
        bm="🤖" if p.is_bot else "👤"
        stat="" if p.is_active else " ❌"
        jl=" 🔒" if p.in_jail else ""
        em=""
        emojis=st.get('emojis',{})
        if p.user_id in emojis:
            et,etx=emojis[p.user_id]
            if now-et<3: em=f" {etx}"
            else: del emojis[p.user_id]
        text+=f"{mk}{bm} {p.name}: ${p.money}{jl}{stat}{em}\n"

    for uid in room.player_ids:
        if uid<0: continue
        last=LAST_EDIT.get(uid,0)
        if now-last<MIN_EDIT_INTERVAL and not force: continue
        kb_buttons=[]
        if cur and room.is_started and uid==cur.user_id and not st['is_moving'] and not st['in_cooldown']:
            if room.can_roll and room.awaiting_buy is None:
                kb_buttons.append([InlineKeyboardButton(text=t('roll_dice',room.language),callback_data=f"roll_{room.code}")])
                # Build button
                idx=cur.position
                cb,cost=can_build(room,cur.user_id,idx)
                if cb:
                    cell=BOARD[idx]; _,h=room.ownership[idx]
                    lb=t('build_house',room.language,cell['name'],cost) if h<4 else f"🏨 Hotel {cell['name']} (${cost})"
                    kb_buttons.append([InlineKeyboardButton(text=lb,callback_data=f"build_{room.code}_{idx}")])
                # Trade button (only for humans)
                if not cur.is_bot:
                    kb_buttons.append([InlineKeyboardButton(text=t('trade',room.language),callback_data=f"trade_{room.code}")])
            if room.awaiting_buy is not None:
                cell=BOARD[room.awaiting_buy]
                if room.awaiting_buyout:
                    oid,h=room.ownership[room.awaiting_buy]
                    kb_buttons.append([InlineKeyboardButton(text=t('buyout_property',room.language,cell['name'],buyout_price(cell,h)),callback_data=f"buyout_{room.code}")])
                else:
                    kb_buttons.append([InlineKeyboardButton(text=t('buy_property',room.language,cell['name'],cell['price']),callback_data=f"buy_{room.code}")])
                kb_buttons.append([InlineKeyboardButton(text=t('skip',room.language),callback_data=f"skipbuy_{room.code}")])
            if cur.in_jail and room.awaiting_buy is None:
                kb_buttons.append([InlineKeyboardButton(text=t('pay_jail',room.language),callback_data=f"payjail_{room.code}")])
            if cur.money<0 and room.awaiting_buy is None:
                for pi,pc,ph in get_props(room,cur.user_id):
                    sp=sell_price(pc,ph)
                    kb_buttons.append([InlineKeyboardButton(text=t('sell_property',room.language,pc['name'],sp),callback_data=f"sell_{room.code}_{pi}")])
        # Trade response buttons for target player
        trades=st.get('trades',{})
        if uid in trades:
            tr=trades[uid]
            kb_buttons.append([
                InlineKeyboardButton(text=t('trade_confirm',room.language),callback_data=f"tradeaccept_{room.code}_{uid}"),
                InlineKeyboardButton(text=t('trade_reject',room.language),callback_data=f"tradereject_{room.code}_{uid}")
            ])

        kb=InlineKeyboardMarkup(inline_keyboard=kb_buttons) if kb_buttons else None
        photo=BufferedInputFile(img,filename="board.png")
        try:
            if uid in room.player_message_ids:
                try:
                    await bot.edit_message_media(chat_id=uid,message_id=room.player_message_ids[uid],
                        media=types.InputMediaPhoto(media=photo,caption=text,parse_mode="Markdown"),reply_markup=kb)
                    LAST_EDIT[uid]=time.time()
                except Exception as e:
                    es=str(e).lower()
                    if "not modified" in es: pass
                    elif "flood" in es:
                        m=re.search(r'retry after (\d+)',str(e))
                        LAST_EDIT[uid]=time.time()+(int(m.group(1)) if m else 30)
                    else:
                        try:
                            msg=await bot.send_photo(chat_id=uid,photo=BufferedInputFile(img,filename="b.png"),caption=text,parse_mode="Markdown",reply_markup=kb)
                            room.player_message_ids[uid]=msg.message_id; db.set_player_message_id(room.code,uid,msg.message_id); LAST_EDIT[uid]=time.time()
                        except: pass
            else:
                msg=await bot.send_photo(chat_id=uid,photo=BufferedInputFile(img,filename="b.png"),caption=text,parse_mode="Markdown",reply_markup=kb)
                room.player_message_ids[uid]=msg.message_id; db.set_player_message_id(room.code,uid,msg.message_id); LAST_EDIT[uid]=time.time()
        except Exception as e: logging.error(f"send:{uid}:{e}")

# ─── EMOJI ───
@router.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    text=message.text.strip() if message.text else ""
    uid=message.from_user.id
    # Check if in trade money input state
    cs=await state.get_state()
    if cs==TradeMoneyInput.waiting.state:
        await handle_trade_money_input(message, state)
        return
    # Check emoji
    if text and EMOJI_RE.fullmatch(text):
        try: await message.delete()
        except: pass
        conn=sqlite3.connect(str(DB_PATH)); c=conn.cursor()
        c.execute("SELECT room_code FROM user_room WHERE user_id=?",(uid,))
        row=c.fetchone(); conn.close()
        if not row: return
        room=db.get_room(row[0])
        if not room or not room.is_started or uid not in room.players: return
        st=get_room_state(room.code); st['emojis'][uid]=(time.time(),text)
        await send_board(room,force=True)
        await asyncio.sleep(3.5)
        room=db.get_room(room.code)
        if room and room.is_started: await send_board(room)

@router.message(CommandStart())
async def cmd_start(message: Message):
    lang=db.get_user_language(message.from_user.id)
    db.save_user(message.from_user.id,message.from_user.username or message.from_user.full_name,lang)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇬🇧 English",callback_data="lang_en"),InlineKeyboardButton(text="🇷🇺 Русский",callback_data="lang_ru")]])
    await message.answer(t('welcome',lang),reply_markup=kb,parse_mode="Markdown")

@router.callback_query(F.data.startswith("lang_"))
async def cb_lang(cb: CallbackQuery):
    lang=cb.data.split("_")[1]; db.set_user_language(cb.from_user.id,lang)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t('create_room',lang),callback_data="create_room")],[InlineKeyboardButton(text=t('join_by_code',lang),callback_data="join_room")],[InlineKeyboardButton(text=t('browse_rooms',lang),callback_data="browse_rooms")]])
    await cb.message.edit_text(t('language_selected',lang),reply_markup=kb,parse_mode="Markdown")

@router.callback_query(F.data=="browse_rooms")
async def cb_browse(cb: CallbackQuery):
    lang=db.get_user_language(cb.from_user.id); rooms=db.get_all_rooms()
    if not rooms:
        await cb.message.edit_text(t('no_rooms',lang),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t('create_room',lang),callback_data="create_room")],[InlineKeyboardButton(text=t('back',lang),callback_data="back_to_menu")]])); return
    text=t('available_rooms',lang); kbb=[]
    for r in rooms:
        text+=f"{'🔒' if r['has_password'] else '🔓'} `{r['code']}` {r['current_players']}/{r['max_players']}\n"
        if not r['has_password']: kbb.append([InlineKeyboardButton(text=t('join',lang,r['code']),callback_data=f"quickjoin_{r['code']}")])
    kbb.append([InlineKeyboardButton(text=t('refresh',lang),callback_data="browse_rooms")])
    kbb.append([InlineKeyboardButton(text=t('back',lang),callback_data="back_to_menu")])
    await cb.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=kbb),parse_mode="Markdown")

@router.callback_query(F.data.startswith("quickjoin_"))
async def cb_qjoin(cb: CallbackQuery):
    lang=db.get_user_language(cb.from_user.id); code=cb.data.split("_")[1]; room=db.get_room(code)
    if not room: await cb.answer(t('room_not_found',lang),show_alert=True); return
    if room.password: await cb.answer(t('room_has_password',lang),show_alert=True); return
    if len(room.players)>=room.max_players: await cb.answer(t('room_full',lang),show_alert=True); return
    if cb.from_user.id in room.players: await cb.answer(t('already_in_room',lang),show_alert=True); return
    p=Player(user_id=cb.from_user.id,name=cb.from_user.full_name,color=get_available_color(room))
    if not db.add_player(room.code,p): await cb.answer(t('room_full',lang),show_alert=True); return
    room.players[p.user_id]=p; room.player_ids.add(p.user_id); db.set_user_room(cb.from_user.id,room.code); db.update_room(room)
    await cb.answer(t('joined_room',lang,room.code)); await show_lobby(cb.message,room)

@router.callback_query(F.data=="back_to_menu")
async def cb_back(cb: CallbackQuery):
    lang=db.get_user_language(cb.from_user.id)
    await cb.message.edit_text(t('welcome',lang),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t('create_room',lang),callback_data="create_room")],[InlineKeyboardButton(text=t('join_by_code',lang),callback_data="join_room")],[InlineKeyboardButton(text=t('browse_rooms',lang),callback_data="browse_rooms")]]),parse_mode="Markdown")

@router.callback_query(F.data=="create_room")
async def cb_create(cb: CallbackQuery,state: FSMContext):
    lang=db.get_user_language(cb.from_user.id)
    await cb.message.edit_text(t('choose_max_players',lang),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="2",callback_data="max_2"),InlineKeyboardButton(text="3",callback_data="max_3")],[InlineKeyboardButton(text="4",callback_data="max_4"),InlineKeyboardButton(text="6",callback_data="max_6")],[InlineKeyboardButton(text="8",callback_data="max_8")]]))
    await state.set_state(CreateRoom.wait_max)

@router.callback_query(F.data.startswith("max_"),StateFilter(CreateRoom.wait_max))
async def cb_max(cb: CallbackQuery,state: FSMContext):
    lang=db.get_user_language(cb.from_user.id); mp=int(cb.data.split("_")[1]); await state.update_data(max_players=mp)
    await cb.message.edit_text(t('password_question',lang,mp),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t('with_password',lang),callback_data="pass_yes")],[InlineKeyboardButton(text=t('no_password',lang),callback_data="pass_no")]]))
    await state.set_state(CreateRoom.wait_password)

@router.callback_query(F.data=="pass_no",StateFilter(CreateRoom.wait_password))
async def cb_nopass(cb: CallbackQuery,state: FSMContext):
    lang=db.get_user_language(cb.from_user.id); await state.update_data(password=None)
    await cb.message.edit_text(t('allow_buyout_question',lang),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t('allow_buyout',lang),callback_data="buyout_yes")],[InlineKeyboardButton(text=t('no_buyout',lang),callback_data="buyout_no")]]))
    await state.set_state(CreateRoom.wait_buyout)

@router.callback_query(F.data=="pass_yes",StateFilter(CreateRoom.wait_password))
async def cb_askpass(cb: CallbackQuery,state: FSMContext):
    await cb.message.edit_text(t('enter_password',db.get_user_language(cb.from_user.id)))

@router.message(StateFilter(CreateRoom.wait_password))
async def msg_pass(msg: Message,state: FSMContext):
    lang=db.get_user_language(msg.from_user.id); await state.update_data(password=msg.text.strip())
    await msg.answer(t('allow_buyout_question',lang),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t('allow_buyout',lang),callback_data="buyout_yes")],[InlineKeyboardButton(text=t('no_buyout',lang),callback_data="buyout_no")]]))
    await state.set_state(CreateRoom.wait_buyout)

@router.callback_query(F.data.startswith("buyout_"),StateFilter(CreateRoom.wait_buyout))
async def cb_buyout_ch(cb: CallbackQuery,state: FSMContext):
    lang=db.get_user_language(cb.from_user.id); await state.update_data(allow_buyout=(cb.data=="buyout_yes"))
    await cb.message.edit_text(t('choose_turn_time',lang),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t('seconds_15',lang),callback_data="time_15")],[InlineKeyboardButton(text=t('seconds_30',lang),callback_data="time_30")],[InlineKeyboardButton(text=t('seconds_60',lang),callback_data="time_60")]]))
    await state.set_state(CreateRoom.wait_turn_time)

@router.callback_query(F.data.startswith("time_"),StateFilter(CreateRoom.wait_turn_time))
async def cb_time(cb: CallbackQuery,state: FSMContext):
    tt=int(cb.data.split("_")[1]); data=await state.get_data()
    lang=db.get_user_language(cb.from_user.id); code=generate_code()
    room=Room(code=code,creator_id=cb.from_user.id,chat_id=cb.from_user.id,max_players=data['max_players'],password=data.get('password'),language=lang,allow_buyout=data['allow_buyout'],turn_time=tt)
    p=Player(user_id=cb.from_user.id,name=cb.from_user.full_name,color=get_available_color(room))
    room.players[p.user_id]=p; room.player_ids.add(p.user_id)
    if not db.create_room(room): await cb.answer("Error",show_alert=True); return
    db.add_player(code,p); db.set_user_room(cb.from_user.id,code); await state.clear(); await show_lobby(cb.message,room)

async def show_lobby(m,room):
    pt="\n".join([f"{'🤖' if p.is_bot else '👤'} {p.name}" for p in room.players.values()])
    bs=t('enabled',room.language) if room.allow_buyout else t('disabled',room.language)
    text=t('room_info',room.language,room.code,room.password or t('none',room.language),len(room.players),room.max_players,bs,room.turn_time,pt)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t('add_bot',room.language),callback_data=f"addbot_{room.code}")],[InlineKeyboardButton(text=t('start_game',room.language),callback_data=f"start_{room.code}")],[InlineKeyboardButton(text=t('refresh',room.language),callback_data=f"lobby_{room.code}")]])
    if isinstance(m,CallbackQuery):
        try: await m.message.edit_text(text,reply_markup=kb,parse_mode="Markdown")
        except: await m.answer()
    else: await m.answer(text,reply_markup=kb,parse_mode="Markdown")

@router.callback_query(F.data.startswith("lobby_"))
async def cb_lobby(cb: CallbackQuery):
    room=db.get_room(cb.data.split("_")[1])
    if not room: await cb.answer("Not found",show_alert=True); return
    await show_lobby(cb,room)

@router.callback_query(F.data.startswith("addbot_"))
async def cb_addbot(cb: CallbackQuery):
    lang=db.get_user_language(cb.from_user.id); code=cb.data.split("_")[1]; room=db.get_room(code)
    if not room: await cb.answer("Not found",show_alert=True); return
    if len(room.players)>=room.max_players: await cb.answer(t('room_full',lang),show_alert=True); return
    bn=["Alpha","Beta","Gamma","Delta","Epsilon","Zeta","Eta","Theta"]
    used={p.name.replace("🤖 ","") for p in room.players.values() if p.is_bot}
    name=random.choice([n for n in bn if n not in used] or [f"Bot{random.randint(1,99)}"])
    bid=-random.randint(10000,99999)
    p=Player(user_id=bid,name=f"🤖 {name}",color=get_available_color(room),is_bot=True)
    if not db.add_player(code,p): await cb.answer("Full",show_alert=True); return
    room.players[bid]=p; room.player_ids.add(bid); db.update_room(room)
    await cb.answer(t('bot_added',lang,name)); await show_lobby(cb,room)

@router.callback_query(F.data.startswith("start_"))
async def cb_start(cb: CallbackQuery):
    lang=db.get_user_language(cb.from_user.id); code=cb.data.split("_")[1]; room=db.get_room(code)
    if not room: await cb.answer("Not found",show_alert=True); return
    if cb.from_user.id!=room.creator_id: await cb.answer(t('only_creator_start',lang),show_alert=True); return
    if len(room.players)<2: await cb.answer(t('need_min_players',lang),show_alert=True); return
    room.is_started=True; room.can_roll=True; db.update_room(room)
    try: await cb.message.edit_text(t('game_starting',room.language))
    except: pass
    room.add_event(t('game_started',room.language))
    cur=room.current_player()
    if cur: room.add_event(t('player_turn',room.language,cur.name))
    await send_board(room,force=True)
    await start_turn_timer(room.code)
    await maybe_bot(room)

@router.callback_query(F.data=="join_room")
async def cb_join_menu(cb: CallbackQuery,state: FSMContext):
    await cb.message.edit_text(t('enter_room_code',db.get_user_language(cb.from_user.id))); await state.set_state(JoinRoom.wait_code)

@router.message(StateFilter(JoinRoom.wait_code))
async def msg_jcode(msg: Message,state: FSMContext):
    lang=db.get_user_language(msg.from_user.id); code=msg.text.strip().upper(); room=db.get_room(code)
    if not room: await msg.answer(t('room_not_found',lang)); await state.clear(); return
    if room.password: await state.update_data(join_code=code); await msg.answer(t('room_has_password',lang)); await state.set_state(JoinRoom.wait_password); return
    await do_join(msg,room,state)

@router.message(StateFilter(JoinRoom.wait_password))
async def msg_jpass(msg: Message,state: FSMContext):
    lang=db.get_user_language(msg.from_user.id); data=await state.get_data(); code=data.get("join_code")
    if not code: await state.clear(); return
    room=db.get_room(code)
    if not room: await msg.answer(t('room_not_found',lang)); await state.clear(); return
    if msg.text.strip()!=room.password: await msg.answer(t('wrong_password',lang)); return
    await do_join(msg,room,state)

async def do_join(msg,room,state):
    lang=db.get_user_language(msg.from_user.id)
    if msg.from_user.id in room.players: await msg.answer(t('already_in_room',lang)); await state.clear(); return
    if len(room.players)>=room.max_players: await msg.answer(t('room_full',lang)); await state.clear(); return
    p=Player(user_id=msg.from_user.id,name=msg.from_user.full_name,color=get_available_color(room))
    if not db.add_player(room.code,p): await msg.answer("Full"); await state.clear(); return
    room.players[p.user_id]=p; room.player_ids.add(p.user_id); db.set_user_room(msg.from_user.id,room.code); db.update_room(room)
    await state.clear(); await msg.answer(t('joined_room',lang,room.code),parse_mode="Markdown"); await show_lobby(msg,room)

# ─── GAME ───
@router.callback_query(F.data.startswith("roll_"))
async def cb_roll(cb: CallbackQuery):
    lang=db.get_user_language(cb.from_user.id); code=cb.data.split("_")[1]; room=db.get_room(code)
    if not room or not room.is_started: await cb.answer("No",show_alert=True); return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer(t('not_your_turn',lang),show_alert=True); return
    st=get_room_state(room.code)
    if not room.can_roll or st['in_cooldown']: await cb.answer(t('waiting',lang),show_alert=True); return
    await cb.answer(); await do_roll(room)

async def do_roll(room):
    room=db.get_room(room.code)
    if not room or not room.is_started: return
    cur=room.current_player()
    if not cur: return
    # Cancel turn timer
    st=get_room_state(room.code)
    if st.get('turn_timer') and not st['turn_timer'].done(): st['turn_timer'].cancel()
    room.can_roll=False; db.update_room(room); await send_board(room)

    if cur.in_jail:
        d1,d2=random.randint(1,6),random.randint(1,6)
        if d1==d2:
            cur.in_jail=False; cur.jail_turns=0; cur.doubles_count=0; db.update_player(room.code,cur)
            room.add_event(t('jail_doubles',room.language,cur.name,d1,d2)); await send_board(room)
            await delay(room.code,3,'moving_countdown')
            room=db.get_room(room.code)
            if not room: return
            cur=room.players.get(cur.user_id)
            if not cur: return
            await move(room,cur,d1+d2,d1+d2,False)
        else:
            cur.jail_turns+=1
            if cur.jail_turns>=3:
                cur.pay(150); cur.in_jail=False; cur.jail_turns=0; cur.doubles_count=0; db.update_player(room.code,cur)
                room.add_event(t('jail_pay_forced',room.language,cur.name)); await send_board(room)
                await delay(room.code,3,'moving_countdown')
                room=db.get_room(room.code)
                if not room: return
                cur=room.players.get(cur.user_id)
                if not cur: return
                await move(room,cur,d1+d2,d1+d2,False)
            else:
                db.update_player(room.code,cur)
                room.add_event(t('jail_no_doubles',room.language,cur.name,d1,d2,3-cur.jail_turns))
                await delay(room.code,3,'turn_end_countdown'); await end_turn(room)
        return

    d1,d2=random.randint(1,6),random.randint(1,6); total=d1+d2; dbl=(d1==d2)
    room.add_event(t('rolled',room.language,cur.name,d1,d2,total))
    if dbl:
        cur.doubles_count+=1; db.update_player(room.code,cur)
        if cur.doubles_count>=3:
            room.add_event(t('third_double',room.language,cur.name))
            cur.position=10; cur.in_jail=True; cur.jail_turns=0; cur.doubles_count=0
            db.update_player(room.code,cur); db.update_room(room); await send_board(room)
            await delay(room.code,3,'turn_end_countdown'); await end_turn(room); return
        room.add_event(t('doubles',room.language,cur.name))
    await send_board(room)
    await delay(room.code,3,'moving_countdown')
    room=db.get_room(room.code)
    if not room: return
    cur=room.players.get(cur.user_id)
    if not cur: return
    await move(room,cur,total,total,dbl)

async def move(room,player,steps,dice,dbl=False):
    old=player.position; new=(old+steps)%40
    if new<old and new!=0:
        player.receive(200); db.update_player(room.code,player)
        room.add_event(t('passed_start',room.language,player.name))
    player.position=new; db.update_player(room.code,player)
    await process(room,player,dice,dbl)

async def process(room,player,dice,dbl=False):
    cell=BOARD[player.position]; ct=cell["type"]
    async def finish():
        nonlocal room
        if dbl:
            room=db.get_room(room.code)
            if not room: return
            room.can_roll=True; db.update_room(room)
            room.add_event(t('doubles_turn',room.language,player.name))
            await send_board(room)
            await start_turn_timer(room.code)
            cur=room.current_player()
            if cur and cur.is_bot: await maybe_bot(room)
        else:
            await delay(room.code,3,'turn_end_countdown'); await end_turn(room)

    if ct=="go":
        player.receive(200); db.update_player(room.code,player)
        room.add_event(t('at_start',room.language,player.name)); await send_board(room); await finish()
    elif ct=="property": await handle_prop(room,player,cell,dice,dbl)
    elif ct=="chance":
        card=random.choice(room.chance_deck); await apply_card(room,player,card,"🎲",dbl)
    elif ct=="chest":
        amt=random.choice([50,100,150,200]); player.receive(amt); db.update_player(room.code,player)
        room.add_event(t('chest_reward',room.language,player.name,amt)); await send_board(room); await finish()
    elif ct=="risk":
        card=random.choice(room.risk_deck); await apply_card(room,player,card,"⚠️",dbl)
    elif ct=="tax":
        player.pay(cell["amount"]); db.update_player(room.code,player)
        room.add_event(t('tax_paid',room.language,player.name,cell["amount"]))
        await check_debt(room,player); await send_board(room); await finish()
    elif ct=="jail":
        room.add_event(t('visiting_jail',room.language,player.name)); await send_board(room); await finish()
    elif ct=="free_parking":
        room.add_event(t('at_parking',room.language,player.name)); await send_board(room); await finish()
    elif ct=="go_to_jail":
        player.position=10; player.in_jail=True; player.jail_turns=0; player.doubles_count=0
        db.update_player(room.code,player); room.add_event(t('go_to_jail',room.language,player.name))
        await send_board(room); await delay(room.code,3,'turn_end_countdown'); await end_turn(room)

async def handle_prop(room,player,cell,dice,dbl=False):
    idx=player.position
    async def finish():
        nonlocal room
        if dbl:
            room=db.get_room(room.code)
            if not room: return
            room.can_roll=True; db.update_room(room)
            room.add_event(t('doubles_turn',room.language,player.name))
            await send_board(room)
            await start_turn_timer(room.code)
            cur=room.current_player()
            if cur and cur.is_bot: await maybe_bot(room)
        else:
            await delay(room.code,3,'turn_end_countdown'); await end_turn(room)

    if idx in room.ownership:
        oid,h=room.ownership[idx]
        if oid==player.user_id:
            # Own property — show build button, allow roll/build
            room.add_event(t('own_property',room.language,player.name,cell['name']))
            if dbl:
                room=db.get_room(room.code)
                if not room: return
                room.can_roll=True; db.update_room(room)
                room.add_event(t('doubles_turn',room.language,player.name))
                await send_board(room)
                await start_turn_timer(room.code)
                if player.is_bot:
                    # Bot builds if can
                    cb2,cost2=can_build(room,player.user_id,idx)
                    if cb2:
                        await asyncio.sleep(1); room=db.get_room(room.code)
                        if room:
                            p=room.players.get(player.user_id)
                            if p:
                                c2,co2=can_build(room,p.user_id,idx)
                                if c2:
                                    p.pay(co2); _,hh=room.ownership[idx]; room.ownership[idx]=(p.user_id,hh+1)
                                    db.set_ownership(room.code,idx,p.user_id,hh+1); db.update_player(room.code,p)
                                    room.add_event(t('hotel_built' if hh+1>=5 else 'house_built',room.language,p.name,cell['name'],hh,hh+1))
                                    await send_board(room)
                    await maybe_bot(room)
            else:
                # Not double — end turn, but show build button briefly
                room.can_roll=False; db.update_room(room)
                # Check if can build — give 15s
                cb2,_=can_build(room,player.user_id,idx)
                if cb2 and not player.is_bot:
                    room.awaiting_buy=idx; room.awaiting_buyout=False; db.update_room(room)
                    await send_board(room)
                    # Set build/skip timeout
                    room.turn_timer_task=asyncio.create_task(buy_timeout(room.code))
                elif cb2 and player.is_bot:
                    await asyncio.sleep(1); room=db.get_room(room.code)
                    if room:
                        p=room.players.get(player.user_id)
                        if p:
                            c3,co3=can_build(room,p.user_id,idx)
                            if c3:
                                p.pay(co3); _,hh=room.ownership[idx]; room.ownership[idx]=(p.user_id,hh+1)
                                db.set_ownership(room.code,idx,p.user_id,hh+1); db.update_player(room.code,p)
                                room.add_event(t('hotel_built' if hh+1>=5 else 'house_built',room.language,p.name,cell['name'],hh,hh+1))
                    await delay(room.code,3,'turn_end_countdown'); await end_turn(room)
                else:
                    await send_board(room)
                    await delay(room.code,3,'turn_end_countdown'); await end_turn(room)
        else:
            # Other's property — pay rent
            owner=room.players.get(oid)
            if not owner or not owner.is_active: await send_board(room); await finish(); return
            g=cell.get("group")
            if g=="station": rent=calc_rent(cell,h,count_stations(room,oid),dice)
            elif g=="utility": rent=calc_rent(cell,h,count_utils(room,oid),dice)
            else: rent=calc_rent(cell,h,1,dice,owns_full_group(room,oid,g))
            player.pay(rent); owner.receive(rent)
            db.update_player(room.code,player); db.update_player(room.code,owner)
            room.add_event(t('rent_paid',room.language,player.name,rent,owner.name,cell['name']))
            await check_debt(room,player)
            if room.allow_buyout and g not in ["station","utility"] and player.is_active:
                bp=buyout_price(cell,h)
                if player.money>=bp:
                    room.awaiting_buy=idx; room.awaiting_buyout=True; db.update_room(room)
                    await send_board(room)
                    if not player.is_bot:
                        room.turn_timer_task=asyncio.create_task(buy_timeout(room.code))
                    else:
                        await asyncio.sleep(1.5); room=db.get_room(room.code)
                        if room and room.awaiting_buy==idx:
                            room.awaiting_buy=None; room.awaiting_buyout=False; db.update_room(room)
                            room.add_event(t('purchase_declined',room.language,player.name))
                        await finish()
                else: await send_board(room); await finish()
            else: await send_board(room); await finish()
    else:
        if player.money>=cell["price"]:
            room.awaiting_buy=idx; room.awaiting_buyout=False; db.update_room(room)
            br=cell['rent'][0] if cell.get('rent') else 0
            room.add_event(t('free_property',room.language,cell['name'],cell['price'],br))
            await send_board(room)
            if not player.is_bot:
                room.turn_timer_task=asyncio.create_task(buy_timeout(room.code))
            else:
                await asyncio.sleep(1.5); room=db.get_room(room.code)
                if room and room.awaiting_buy==idx:
                    p=room.players.get(player.user_id)
                    if p:
                        p.pay(cell["price"]); room.ownership[idx]=(p.user_id,0)
                        db.set_ownership(room.code,idx,p.user_id,0)
                        room.awaiting_buy=None; room.awaiting_buyout=False
                        db.update_room(room); db.update_player(room.code,p)
                        room.add_event(t('property_bought',room.language,p.name,cell['name'],cell['price']))
                        if all_stations(room,p.user_id): await end_game(room,p,'stations'); return
                        if three_streets(room,p.user_id): await end_game(room,p,'streets'); return
                await finish()
        else:
            room.add_event(t('not_enough_money',room.language,player.name)); await send_board(room); await finish()

async def apply_card(room,player,card,title,dbl=False):
    ct=card.get('text_ru' if room.language=='ru' else 'text',card['text'])
    room.add_event(f"{title}: {ct}")
    eff=card["effect"]
    if isinstance(eff,int):
        if eff>0: player.receive(eff)
        else: player.pay(abs(eff))
        db.update_player(room.code,player)
    elif eff=="birthday":
        for p in room.active_players():
            if p.user_id!=player.user_id: p.pay(50); player.receive(50); db.update_player(room.code,p)
        db.update_player(room.code,player)
    await check_debt(room,player); await send_board(room)
    if dbl:
        room=db.get_room(room.code)
        if not room: return
        room.can_roll=True; db.update_room(room)
        room.add_event(t('doubles_turn',room.language,player.name)); await send_board(room)
        await start_turn_timer(room.code)
        cur=room.current_player()
        if cur and cur.is_bot: await maybe_bot(room)
    else:
        await delay(room.code,3,'turn_end_countdown'); await end_turn(room)

async def check_debt(room,player):
    if player.money<0:
        props=get_props(room,player.user_id)
        total=sum(sell_price(c,h) for _,c,h in props)
        if total+player.money<0:
            player.is_active=False; db.update_player(room.code,player)
            room.add_event(t('player_eliminated',room.language,player.name))
            for pi,_,_ in props:
                if pi in room.ownership: del room.ownership[pi]
                db.remove_ownership(room.code,pi)
            a=room.active_players()
            if len(a)<=1 and a: await end_game(room,a[0],'last_standing')
        else:
            room.add_event(t('debt_warning',room.language,player.name))

async def end_game(room,winner,reason):
    if reason=='stations': room.add_event(t('all_stations_owned',room.language,winner.name))
    elif reason=='streets': room.add_event(t('three_streets_owned',room.language,winner.name))
    room.add_event(t('player_won',room.language,winner.name))
    room.add_event(t('game_over',room.language))
    room.is_started=False; db.update_room(room); clear_room_state(room.code); await send_board(room)

async def end_turn(room):
    st=get_room_state(room.code)
    if st.get('turn_timer') and not st['turn_timer'].done(): st['turn_timer'].cancel()
    room=db.get_room(room.code)
    if not room or not room.is_started: return
    cur=room.current_player()
    if cur: cur.doubles_count=0; db.update_player(room.code,cur)
    room.awaiting_buy=None; room.awaiting_buyout=False; room.next_turn(); room.can_roll=True; db.update_room(room)
    cur=room.current_player()
    if cur: room.add_event(t('player_turn',room.language,cur.name))
    await send_board(room)
    await start_turn_timer(room.code)
    asyncio.create_task(maybe_bot(room))

async def maybe_bot(room):
    room=db.get_room(room.code)
    if not room or not room.is_started: return
    for _ in range(len(room.players)+1):
        cur=room.current_player()
        if not cur: return
        if cur.is_active: break
        room.next_turn(); db.update_room(room)
    cur=room.current_player()
    if not cur or not cur.is_bot or not room.can_roll: return
    st=get_room_state(room.code)
    if st['in_cooldown']: return
    await asyncio.sleep(2)
    room=db.get_room(room.code)
    if not room or not room.is_started or not room.can_roll: return
    if get_room_state(room.code)['in_cooldown']: return
    cur=room.current_player()
    if cur and cur.is_bot and cur.is_active: await do_roll(room)

# ─── BUILD ───
@router.callback_query(F.data.startswith("build_"))
async def cb_build(cb: CallbackQuery):
    parts=cb.data.split("_"); code=parts[1]; idx=int(parts[2])
    room=db.get_room(code)
    if not room: await cb.answer("No",show_alert=True); return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer(t('not_your_turn',room.language),show_alert=True); return
    ok,cost=can_build(room,cur.user_id,idx)
    if not ok: await cb.answer(t('max_houses',room.language),show_alert=True); return
    cell=BOARD[idx]; _,h=room.ownership[idx]
    cur.pay(cost); room.ownership[idx]=(cur.user_id,h+1)
    db.set_ownership(room.code,idx,cur.user_id,h+1); db.update_player(room.code,cur); db.update_room(room)
    await cb.answer()
    room.add_event(t('hotel_built' if h+1>=5 else 'house_built',room.language,cur.name,cell['name'],h,h+1))
    if three_streets(room,cur.user_id): await end_game(room,cur,'streets'); return
    await send_board(room)

# ─── BUY/BUYOUT/SELL/SKIP/JAIL ───
@router.callback_query(F.data.startswith("buy_"))
async def cb_buy(cb: CallbackQuery):
    code=cb.data.split("_")[1]; room=db.get_room(code)
    if not room: await cb.answer("No",show_alert=True); return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer(t('not_your_turn',room.language),show_alert=True); return
    if room.awaiting_buy is None or room.awaiting_buyout: await cb.answer("No",show_alert=True); return
    idx=room.awaiting_buy; cell=BOARD[idx]
    if cur.money<cell["price"]: await cb.answer(t('not_enough_ruzcoin',room.language),show_alert=True); return
    cur.pay(cell["price"]); room.ownership[idx]=(cur.user_id,0)
    db.set_ownership(room.code,idx,cur.user_id,0); room.awaiting_buy=None; room.awaiting_buyout=False
    if room.turn_timer_task and not room.turn_timer_task.done(): room.turn_timer_task.cancel()
    db.update_room(room); db.update_player(room.code,cur); await cb.answer()
    room.add_event(t('property_bought',room.language,cur.name,cell['name'],cell['price']))
    if all_stations(room,cur.user_id): await end_game(room,cur,'stations'); return
    if three_streets(room,cur.user_id): await end_game(room,cur,'streets'); return
    await send_board(room)
    if cur.doubles_count>0:
        room.can_roll=True; db.update_room(room); room.add_event(t('doubles_turn',room.language,cur.name))
        await send_board(room); await start_turn_timer(room.code); await maybe_bot(room)
    else: await delay(room.code,3,'turn_end_countdown'); await end_turn(room)

@router.callback_query(F.data.startswith("buyout_"))
async def cb_buyout(cb: CallbackQuery):
    code=cb.data.split("_")[1]; room=db.get_room(code)
    if not room: await cb.answer("No",show_alert=True); return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer("No",show_alert=True); return
    if room.awaiting_buy is None or not room.awaiting_buyout: await cb.answer("No",show_alert=True); return
    idx=room.awaiting_buy
    if idx not in room.ownership: await cb.answer("No",show_alert=True); return
    cell=BOARD[idx]; oid,h=room.ownership[idx]; bp=buyout_price(cell,h)
    if cur.money<bp: await cb.answer(t('not_enough_ruzcoin',room.language),show_alert=True); return
    owner=room.players.get(oid)
    if not owner: await cb.answer("No",show_alert=True); return
    cur.pay(bp); owner.receive(bp); room.ownership[idx]=(cur.user_id,h)
    db.set_ownership(room.code,idx,cur.user_id,h); room.awaiting_buy=None; room.awaiting_buyout=False
    if room.turn_timer_task and not room.turn_timer_task.done(): room.turn_timer_task.cancel()
    db.update_room(room); db.update_player(room.code,cur); db.update_player(room.code,owner); await cb.answer()
    room.add_event(t('property_buyout',room.language,cur.name,cell['name'],owner.name,bp))
    if three_streets(room,cur.user_id): await end_game(room,cur,'streets'); return
    await send_board(room)
    if cur.doubles_count>0:
        room.can_roll=True; db.update_room(room); room.add_event(t('doubles_turn',room.language,cur.name))
        await send_board(room); await start_turn_timer(room.code); await maybe_bot(room)
    else: await delay(room.code,3,'turn_end_countdown'); await end_turn(room)

@router.callback_query(F.data.startswith("sell_"))
async def cb_sell(cb: CallbackQuery):
    parts=cb.data.split("_"); code=parts[1]; pi=int(parts[2]); room=db.get_room(code)
    if not room: await cb.answer("No",show_alert=True); return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer("No",show_alert=True); return
    if pi not in room.ownership: await cb.answer("No",show_alert=True); return
    oid,h=room.ownership[pi]
    if oid!=cur.user_id: await cb.answer("No",show_alert=True); return
    cell=BOARD[pi]; sp=sell_price(cell,h); cur.receive(sp); del room.ownership[pi]
    db.remove_ownership(room.code,pi); db.update_player(room.code,cur); await cb.answer()
    room.add_event(t('property_sold',room.language,cur.name,cell['name'],sp))
    if cur.money>=0:
        await send_board(room)
        if cur.doubles_count>0:
            room.can_roll=True; db.update_room(room); await send_board(room); await maybe_bot(room)
        else: await delay(room.code,3,'turn_end_countdown'); await end_turn(room)
    else: await check_debt(room,cur); await send_board(room)

@router.callback_query(F.data.startswith("skipbuy_"))
async def cb_skip(cb: CallbackQuery):
    code=cb.data.split("_")[1]; room=db.get_room(code)
    if not room: return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer("No",show_alert=True); return
    room.awaiting_buy=None; room.awaiting_buyout=False
    if room.turn_timer_task and not room.turn_timer_task.done(): room.turn_timer_task.cancel()
    db.update_room(room); await cb.answer()
    room.add_event(t('purchase_declined',room.language,cb.from_user.full_name))
    if cur.doubles_count>0:
        room.can_roll=True; db.update_room(room); room.add_event(t('doubles_turn',room.language,cur.name))
        await send_board(room); await start_turn_timer(room.code); await maybe_bot(room)
    else: await delay(room.code,3,'turn_end_countdown'); await end_turn(room)

@router.callback_query(F.data.startswith("payjail_"))
async def cb_jail(cb: CallbackQuery):
    code=cb.data.split("_")[1]; room=db.get_room(code)
    if not room: return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer("No",show_alert=True); return
    if cur.money<150: await cb.answer(t('not_enough_ruzcoin',room.language),show_alert=True); return
    cur.pay(150); cur.in_jail=False; cur.jail_turns=0; cur.doubles_count=0
    db.update_player(room.code,cur); await cb.answer()
    room.add_event(t('jail_paid_out',room.language,cur.name))
    room.can_roll=True; db.update_room(room); await send_board(room)
    await start_turn_timer(room.code); await maybe_bot(room)

# ─── TRADE SYSTEM ───
@router.callback_query(F.data.startswith("trade_"))
async def cb_trade_start(cb: CallbackQuery):
    """Start trade — select player"""
    parts=cb.data.split("_")
    if len(parts)!=2: return  # trade_{code}
    code=parts[1]; room=db.get_room(code)
    if not room or not room.is_started: await cb.answer("No",show_alert=True); return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer(t('not_your_turn',room.language),show_alert=True); return
    # Show player selection
    btns=[]
    for p in room.active_players():
        if p.user_id!=cur.user_id and not p.is_bot:
            btns.append([InlineKeyboardButton(text=f"{'👤'} {p.name} (${p.money})",callback_data=f"tplayer_{code}_{p.user_id}")])
    btns.append([InlineKeyboardButton(text=t('trade_cancel',room.language),callback_data=f"tcancel_{code}")])
    await cb.answer()
    try: await cb.message.answer(t('trade_select_player',room.language),reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    except: pass

@router.callback_query(F.data.startswith("tplayer_"))
async def cb_trade_player(cb: CallbackQuery):
    """Selected target player — now select what you want"""
    parts=cb.data.split("_"); code=parts[1]; target_id=int(parts[2])
    room=db.get_room(code)
    if not room: await cb.answer("No",show_alert=True); return
    cur=room.current_player()
    if not cur or cur.user_id!=cb.from_user.id: await cb.answer("No",show_alert=True); return
    target=room.players.get(target_id)
    if not target: await cb.answer("No",show_alert=True); return
    # Store trade state
    st=get_room_state(code)
    st.setdefault('trade_building',{})
    st['trade_building'][cb.from_user.id]={'target':target_id,'want':None,'give':None,'step':'want'}
    # Show target's properties + money option
    btns=[]
    for pi,pc,ph in get_props(room,target_id):
        btns.append([InlineKeyboardButton(text=f"🏠 {pc['name']} ({ph}🏠)",callback_data=f"twant_{code}_prop_{pi}")])
    btns.append([InlineKeyboardButton(text=t('trade_money',room.language),callback_data=f"twant_{code}_money")])
    btns.append([InlineKeyboardButton(text=t('trade_cancel',room.language),callback_data=f"tcancel_{code}")])
    try: await cb.message.edit_text(t('trade_select_want',room.language),reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    except: pass

@router.callback_query(F.data.startswith("twant_"))
async def cb_trade_want(cb: CallbackQuery, state: FSMContext):
    """Selected what you want — property or money"""
    parts=cb.data.split("_"); code=parts[1]; wtype=parts[2]
    room=db.get_room(code)
    if not room: return
    st=get_room_state(code)
    tb=st.get('trade_building',{}).get(cb.from_user.id)
    if not tb: await cb.answer("No trade",show_alert=True); return

    if wtype=="money":
        target=room.players.get(tb['target'])
        max_money=target.money if target else 0
        tb['step']='want_money'
        await cb.message.edit_text(f"{t('trade_enter_money',room.language)}\n(max: ${max_money})")
        await state.set_state(TradeMoneyInput.waiting)
        await state.update_data(trade_code=code,trade_phase='want')
        return
    elif wtype=="prop":
        prop_idx=int(parts[3])
        tb['want']=('prop',prop_idx)
    tb['step']='give'
    # Now select what to give
    cur=room.current_player()
    btns=[]
    if cur:
        for pi,pc,ph in get_props(room,cur.user_id):
            btns.append([InlineKeyboardButton(text=f"🏠 {pc['name']} ({ph}🏠)",callback_data=f"tgive_{code}_prop_{pi}")])
    btns.append([InlineKeyboardButton(text=t('trade_money',room.language),callback_data=f"tgive_{code}_money")])
    btns.append([InlineKeyboardButton(text=t('trade_cancel',room.language),callback_data=f"tcancel_{code}")])
    try: await cb.message.edit_text(t('trade_select_give',room.language),reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    except: pass

@router.callback_query(F.data.startswith("tgive_"))
async def cb_trade_give(cb: CallbackQuery, state: FSMContext):
    """Selected what to give"""
    parts=cb.data.split("_"); code=parts[1]; gtype=parts[2]
    room=db.get_room(code)
    if not room: return
    st=get_room_state(code)
    tb=st.get('trade_building',{}).get(cb.from_user.id)
    if not tb: await cb.answer("No trade",show_alert=True); return

    if gtype=="money":
        cur=room.current_player()
        max_money=cur.money if cur else 0
        tb['step']='give_money'
        await cb.message.edit_text(f"{t('trade_enter_money',room.language)}\n(max: ${max_money})")
        await state.set_state(TradeMoneyInput.waiting)
        await state.update_data(trade_code=code,trade_phase='give')
        return
    elif gtype=="prop":
        prop_idx=int(parts[3])
        tb['give']=('prop',prop_idx)

    # Send trade proposal
    await send_trade_proposal(room,cb.from_user.id,tb,cb.message)

async def handle_trade_money_input(message: Message, state: FSMContext):
    """Handle money amount input for trade"""
    data=await state.get_data()
    code=data.get('trade_code'); phase=data.get('trade_phase')
    if not code: await state.clear(); return
    await state.clear()

    try: amount=int(message.text.strip().replace('$',''))
    except:
        try: await message.delete()
        except: pass
        return

    try: await message.delete()
    except: pass

    room=db.get_room(code)
    if not room: return
    st=get_room_state(code)
    tb=st.get('trade_building',{}).get(message.from_user.id)
    if not tb: return

    if phase=='want':
        target=room.players.get(tb['target'])
        if target and amount>target.money: amount=target.money
        if amount<=0: return
        tb['want']=('money',amount)
        tb['step']='give'
        # Show give options
        cur=room.current_player()
        btns=[]
        if cur:
            for pi,pc,ph in get_props(room,cur.user_id):
                btns.append([InlineKeyboardButton(text=f"🏠 {pc['name']}",callback_data=f"tgive_{code}_prop_{pi}")])
        btns.append([InlineKeyboardButton(text=t('trade_money',room.language),callback_data=f"tgive_{code}_money")])
        btns.append([InlineKeyboardButton(text=t('trade_cancel',room.language),callback_data=f"tcancel_{code}")])
        await message.answer(t('trade_select_give',room.language),reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    elif phase=='give':
        cur=room.current_player()
        if cur and amount>cur.money: amount=cur.money
        if amount<=0: return
        tb['give']=('money',amount)
        await send_trade_proposal(room,message.from_user.id,tb)

async def send_trade_proposal(room,from_uid,tb,msg=None):
    """Send trade proposal to target player"""
    target_id=tb['target']
    want=tb['want']; give=tb['give']
    if not want or not give: return

    # Format description
    def fmt(item):
        if item[0]=='money': return f"${item[1]}"
        else:
            cell=BOARD[item[1]]
            return cell['name']

    want_str=fmt(want); give_str=fmt(give)
    from_player=room.players.get(from_uid)
    from_name=from_player.name if from_player else "?"

    # Store pending trade
    st=get_room_state(room.code)
    st['trades'][target_id]={'from':from_uid,'want':want,'give':give,'from_name':from_name}

    room.add_event(t('trade_sent',room.language,room.players.get(target_id,Player(0,"?")).name))

    # Clean up building state
    if from_uid in st.get('trade_building',{}): del st['trade_building'][from_uid]

    # Update board to show accept/reject buttons to target
    await send_board(room,force=True)
    if msg:
        try: await msg.delete()
        except: pass

@router.callback_query(F.data.startswith("tcancel_"))
async def cb_trade_cancel(cb: CallbackQuery, state: FSMContext):
    code=cb.data.split("_")[1]
    st=get_room_state(code)
    if cb.from_user.id in st.get('trade_building',{}): del st['trade_building'][cb.from_user.id]
    await state.clear()
    try: await cb.message.delete()
    except: pass
    await cb.answer()

@router.callback_query(F.data.startswith("tradeaccept_"))
async def cb_trade_accept(cb: CallbackQuery):
    parts=cb.data.split("_"); code=parts[1]; target_uid=int(parts[2])
    if cb.from_user.id!=target_uid: await cb.answer("Not for you",show_alert=True); return
    room=db.get_room(code)
    if not room: await cb.answer("No",show_alert=True); return
    st=get_room_state(code)
    trade=st.get('trades',{}).get(target_uid)
    if not trade: await cb.answer("No trade",show_alert=True); return

    from_uid=trade['from']; want=trade['want']; give=trade['give']
    from_p=room.players.get(from_uid); to_p=room.players.get(target_uid)
    if not from_p or not to_p: await cb.answer("Error"); del st['trades'][target_uid]; return

    # Execute trade
    if want[0]=='money':
        amt=min(want[1],to_p.money)
        to_p.pay(amt); from_p.receive(amt)
    else:
        idx=want[1]
        if idx in room.ownership and room.ownership[idx][0]==target_uid:
            _,h=room.ownership[idx]; room.ownership[idx]=(from_uid,h)
            db.set_ownership(room.code,idx,from_uid,h)

    if give[0]=='money':
        amt=min(give[1],from_p.money)
        from_p.pay(amt); to_p.receive(amt)
    else:
        idx=give[1]
        if idx in room.ownership and room.ownership[idx][0]==from_uid:
            _,h=room.ownership[idx]; room.ownership[idx]=(target_uid,h)
            db.set_ownership(room.code,idx,target_uid,h)

    db.update_player(room.code,from_p); db.update_player(room.code,to_p)
    del st['trades'][target_uid]
    room.add_event(t('trade_accepted',room.language,from_p.name,to_p.name))
    await cb.answer()
    if three_streets(room,from_uid): await end_game(room,from_p,'streets'); return
    if three_streets(room,target_uid): await end_game(room,to_p,'streets'); return
    await send_board(room,force=True)

@router.callback_query(F.data.startswith("tradereject_"))
async def cb_trade_reject(cb: CallbackQuery):
    parts=cb.data.split("_"); code=parts[1]; target_uid=int(parts[2])
    if cb.from_user.id!=target_uid: await cb.answer("Not for you",show_alert=True); return
    st=get_room_state(code)
    trade=st.get('trades',{}).get(target_uid)
    if trade:
        room=db.get_room(code)
        if room:
            room.add_event(t('trade_rejected',room.language,cb.from_user.full_name))
        del st['trades'][target_uid]
    await cb.answer()
    room=db.get_room(code)
    if room: await send_board(room,force=True)


async def main():
    print("🚀 Ruzopoly started!")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
