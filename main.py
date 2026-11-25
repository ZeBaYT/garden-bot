"""
Огородник 2.0 — Ферма Ваймиков
200+ культур, грядки 5–100, топы.

Запуск: pip install aiogram && python main.py
"""

import asyncio
import logging
import os
import random
import sqlite3
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, BotCommand,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TOKEN = os.getenv("BOT_TOKEN", "9194809506:AAFmvmDPdS0Yn-gvE64bq7C5BUOeUsWRs8g")

CURRENCY = "Ваймики"
CURRENCY_EMOJI = "💎"
START_PLOTS = 5
MAX_PLOTS_LIMIT = 100
START_VAIMIKI = 30

def plot_price(current_plots: int) -> int:
    return 12 * current_plots

CROPS = {
    "carrot": ("Морковь", "🥕", 1, 1500, 8, 13),
    "beet": ("Свёкла", "🟣", 2, 2400, 6, 11),
    "potato": ("Картошка", "🥔", 2, 3000, 7, 12),
    "tomato": ("Помидор", "🍅", 3, 2100, 6, 11),
    "cabbage": ("Капуста", "🥬", 2, 2700, 6, 10),
    "corn": ("Кукуруза", "🌽", 4, 4200, 5, 9),
    "cucumber": ("Огурец", "🥒", 2, 1800, 7, 12),
    "pepper": ("Перец", "🫑", 3, 2400, 5, 10),
    "onion": ("Лук", "🧅", 1, 2100, 8, 14),
    "garlic": ("Чеснок", "🧄", 2, 3300, 5, 9),
    "radish": ("Редис", "🔴", 1, 1200, 9, 15),
    "eggplant": ("Баклажан", "🍆", 4, 3600, 4, 8),
    "pumpkin": ("Тыква", "🎃", 6, 5400, 3, 6),
    "broccoli": ("Брокколи", "🥦", 3, 3000, 5, 9),
    "cauliflower": ("Цветная капуста", "⚪", 3, 3300, 5, 9),
    "spinach": ("Шпинат", "🍃", 1, 1500, 8, 14),
    "lettuce": ("Салат", "🥗", 1, 1320, 9, 15),
    "zucchini": ("Кабачок", "🟢", 2, 2400, 6, 11),
    "peas": ("Горох", "🟢", 2, 2100, 7, 12),
    "beans": ("Фасоль", "🫘", 2, 2700, 6, 11),
    "asparagus": ("Спаржа", "🟢", 5, 4800, 3, 7),
    "celery": ("Сельдерей", "🌿", 2, 3000, 5, 10),
    "parsley": ("Петрушка", "🌿", 1, 1800, 8, 13),
    "dill": ("Укроп", "🌿", 1, 1680, 9, 14),
    "basil": ("Базилик", "🌿", 2, 1920, 7, 12),
    "chili": ("Чили", "🌶️", 3, 2700, 5, 10),
    "sweet_potato": ("Батат", "🍠", 3, 3900, 5, 9),
    "turnip": ("Репа", "🟣", 1, 2100, 7, 12),
    "parsnip": ("Пастернак", "🤍", 2, 3300, 5, 9),
    "leek": ("Лук-порей", "🧅", 2, 3000, 6, 10),
    "apple": ("Яблоко", "🍎", 3, 3300, 5, 10),
    "pear": ("Груша", "🍐", 3, 3600, 5, 9),
    "strawberry": ("Клубника", "🍓", 4, 2100, 6, 12),
    "grape": ("Виноград", "🍇", 5, 4200, 4, 9),
    "watermelon": ("Арбуз", "🍉", 7, 6000, 2, 5),
    "melon": ("Дыня", "🍈", 6, 5100, 3, 6),
    "cherry": ("Вишня", "🍒", 4, 2700, 5, 11),
    "peach": ("Персик", "🍑", 5, 3900, 4, 8),
    "banana": ("Банан", "🍌", 4, 3000, 5, 10),
    "lemon": ("Лимон", "🍋", 3, 3300, 5, 9),
    "orange": ("Апельсин", "🍊", 4, 3600, 4, 9),
    "kiwi": ("Киви", "🥝", 5, 4200, 4, 8),
    "pineapple": ("Ананас", "🍍", 7, 6600, 2, 5),
    "mango": ("Манго", "🥭", 6, 5400, 3, 7),
    "avocado": ("Авокадо", "🥑", 6, 5700, 2, 5),
    "blueberry": ("Черника", "🫐", 4, 2400, 6, 11),
    "raspberry": ("Малина", "🔴", 4, 2280, 6, 12),
    "blackberry": ("Ежевика", "⚫", 4, 2520, 5, 11),
    "plum": ("Слива", "🟣", 3, 3000, 5, 10),
    "apricot": ("Абрикос", "🟠", 4, 3300, 4, 9),
    "fig": ("Инжир", "🟤", 5, 4500, 3, 7),
    "pomegranate": ("Гранат", "🔴", 5, 4800, 3, 7),
    "coconut": ("Кокос", "🥥", 6, 6000, 2, 4),
    "papaya": ("Папайя", "🧡", 5, 5100, 3, 6),
    "guava": ("Гуава", "🟢", 5, 4200, 4, 8),
    "dragonfruit": ("Питахайя", "🐉", 8, 6000, 2, 5),
    "lychee": ("Личи", "🔴", 7, 5400, 3, 6),
    "rambutan": ("Рамбутан", "🔴", 7, 5700, 2, 5),
    "durian": ("Дуриан", "🟢", 10, 7200, 1, 3),
    "jackfruit": ("Джекфрут", "🟡", 8, 6600, 2, 4),
    "starfruit": ("Карамбола", "⭐", 6, 4800, 3, 7),
    "passionfruit": ("Маракуйя", "🟣", 6, 4500, 3, 7),
    "persimmon": ("Хурма", "🟠", 4, 3900, 4, 8),
    "quince": ("Айва", "🟡", 3, 4200, 4, 8),
    "mulberry": ("Шелковица", "🟣", 3, 3000, 5, 10),
    "gooseberry": ("Крыжовник", "🟢", 3, 2700, 6, 11),
    "currant": ("Смородина", "🔴", 3, 2400, 6, 12),
    "cranberry": ("Клюква", "🔴", 4, 3300, 5, 10),
    "lingonberry": ("Брусника", "🔴", 4, 3000, 5, 10),
    "cloudberry": ("Морошка", "🟠", 6, 4200, 3, 7),
    "feijoa": ("Фейхоа", "🟢", 5, 4800, 3, 7),
    "longan": ("Лонган", "🟤", 6, 5100, 3, 6),
    "mangosteen": ("Мангостан", "🟣", 9, 6600, 1, 4),
    "salak": ("Салак", "🟤", 7, 5700, 2, 5),
    "tamarind": ("Тамаринд", "🟤", 5, 5100, 3, 7),
    "breadfruit": ("Хлебное дерево", "🟢", 7, 6300, 2, 4),
    "soursop": ("Сметанное яблоко", "🟢", 7, 6000, 2, 5),
    "cherimoya": ("Черимойя", "🟢", 7, 5700, 2, 5),
    "jabuticaba": ("Жабутикаба", "🟣", 8, 6000, 2, 4),
    "miracle_fruit": ("Чудо-ягода", "🔴", 9, 4800, 2, 5),
    "noni": ("Нони", "⚪", 5, 5400, 3, 6),
    "horn_melon": ("Кивано", "🟢", 6, 4500, 3, 7),
    "cactus_fruit": ("Кактусовый плод", "🌵", 4, 3600, 4, 9),
    "yuzu": ("Юдзу", "🟡", 5, 4200, 3, 7),
    "pomelo": ("Помело", "🟡", 5, 4800, 3, 6),
    "clementine": ("Клементин", "🟠", 3, 3000, 5, 10),
    "tangerine": ("Мандарин", "🍊", 3, 2880, 5, 10),
    "grapefruit": ("Грейпфрут", "🔴", 4, 4200, 4, 8),
    "lime": ("Лайм", "🟢", 3, 3000, 5, 9),
    "kumquat": ("Кумкват", "🟠", 4, 3300, 4, 9),
    "blood_orange": ("Кровавый апельсин", "🔴", 4, 3600, 4, 8),
    "loquat": ("Мушмула", "🟠", 4, 3300, 4, 9),
    "rowan": ("Рябина", "🟠", 2, 3000, 6, 11),
    "hawthorn": ("Боярышник", "🔴", 2, 3300, 5, 10),
    "elderberry": ("Бузина", "🟣", 3, 2700, 5, 11),
    "sea_buckthorn": ("Облепиха", "🟠", 4, 3000, 5, 10),
    "barberry": ("Барбарис", "🔴", 3, 2700, 5, 10),
    "dogwood": ("Кизил", "🔴", 3, 3300, 5, 9),
    "chokeberry": ("Арония", "⚫", 3, 2880, 5, 11),
    "honeyberry": ("Жимолость", "🔵", 4, 2400, 6, 11),
    "goji": ("Годжи", "🔴", 5, 3600, 4, 9),
    "acai": ("Асаи", "🟣", 7, 5400, 2, 5),
    "lucuma": ("Лукума", "🟡", 6, 5700, 2, 5),
    "olive": ("Олива", "🫒", 4, 6000, 3, 7),
    "date": ("Финик", "🟤", 4, 5400, 3, 7),
    "jujube": ("Зизифус", "🔴", 4, 4200, 4, 8),
    "tamarillo": ("Тамарилло", "🔴", 5, 3900, 3, 7),
    "cape_gooseberry": ("Физалис", "🟡", 4, 3000, 5, 10),
    "tomatillo": ("Томатильо", "🟢", 3, 2700, 5, 10),
    "okra": ("Бамия", "🟢", 3, 3000, 5, 9),
    "artichoke": ("Артишок", "🟢", 5, 5100, 2, 5),
    "fennel": ("Фенхель", "🌿", 3, 3300, 4, 9),
    "kohlrabi": ("Кольраби", "🟢", 2, 2700, 6, 10),
    "rutabaga": ("Брюква", "🟣", 2, 3300, 5, 9),
    "horseradish": ("Хрен", "🤍", 3, 4200, 3, 7),
    "wasabi": ("Васаби", "🟢", 8, 6000, 1, 3),
    "ginger": ("Имбирь", "🟤", 4, 4800, 3, 7),
    "turmeric": ("Куркума", "🟡", 4, 4500, 3, 7),
    "vanilla": ("Ваниль", "🟤", 9, 7200, 1, 2),
    "saffron": ("Шафран", "🟣", 12, 8400, 1, 2),
    "truffle": ("Трюфель", "⚫", 15, 9000, 1, 2),
    "morel": ("Сморчок", "🟤", 8, 4200, 2, 4),
    "chanterelle": ("Лисичка", "🟠", 6, 3600, 3, 6),
    "porcini": ("Белый гриб", "🟤", 7, 4500, 2, 5),
    "shiitake": ("Шиитаке", "🟤", 5, 3300, 3, 7),
    "oyster_mushroom": ("Вёшенка", "⚪", 3, 2400, 5, 10),
    "bamboo_shoot": ("Бамбуковый побег", "🎋", 4, 3000, 4, 8),
    "lotus_root": ("Корень лотоса", "🌸", 5, 4200, 3, 6),
    "taro": ("Таро", "🟣", 4, 4500, 3, 7),
    "yuca": ("Маниока", "🟤", 3, 4800, 4, 8),
    "plantain": ("Плантан", "🍌", 3, 3600, 4, 9),
    "wax_apple": ("Восковое яблоко", "🔴", 4, 3300, 4, 9),
    "rose_apple": ("Розовое яблоко", "🩷", 4, 3000, 4, 9),
    "ambarella": ("Амбарелла", "🟡", 4, 4200, 3, 7),
    "quinoa": ("Киноа", "⚪", 3, 3300, 5, 9),
    "amaranth": ("Амарант", "🔴", 3, 3000, 5, 10),
    "buckwheat": ("Гречка", "🟤", 2, 2400, 6, 11),
    "rice": ("Рис", "🍚", 3, 4200, 4, 8),
    "wheat": ("Пшеница", "🟡", 2, 3000, 6, 10),
    "oats": ("Овёс", "⚪", 2, 2700, 6, 11),
    "barley": ("Ячмень", "🟡", 2, 3000, 6, 10),
    "rye": ("Рожь", "🟤", 2, 3300, 5, 10),
    "millet": ("Пшено", "🟡", 2, 2700, 6, 11),
    "cashew_fruit": ("Кешью", "🟡", 5, 4500, 3, 7),
    "macadamia": ("Макадамия", "🟤", 8, 6600, 1, 3),
    "brazil_nut": ("Бразильский орех", "🟤", 8, 7200, 1, 3),
    "pepino": ("Пепино", "🟡", 4, 3300, 4, 9),
    "naranjilla": ("Наранхилья", "🟠", 5, 4200, 3, 7),
    "pitanga": ("Питанга", "🔴", 4, 3300, 4, 9),
    "surinam_cherry": ("Суринамская вишня", "🔴", 4, 3000, 5, 9),
    "grumichama": ("Грумичама", "🔴", 5, 4200, 3, 7),
    "cambuci": ("Камбучи", "🟢", 6, 5100, 2, 5),
    "bacuri": ("Бакури", "🟡", 7, 6000, 1, 4),
    "pequi": ("Пеки", "🟡", 6, 5700, 2, 4),
    "umbu": ("Умбу", "🟢", 4, 4500, 3, 6),
    "caja": ("Кажа", "🟡", 5, 4800, 2, 5),
    "bacaba": ("Бакаба", "🟣", 6, 5400, 2, 4),
    "buriti": ("Бурити", "🟠", 5, 5100, 2, 5),
    "tucuma": ("Тукума", "🟠", 5, 4800, 3, 6),
    "aguaje": ("Агуахе", "🔴", 5, 5400, 2, 5),
    "pupunha": ("Пупунья", "🟠", 4, 4500, 3, 7),
    "canistel": ("Канистел", "🟡", 5, 5100, 3, 6),
    "mamey": ("Мамей", "🟤", 6, 6000, 2, 4),
    "black_sapote": ("Чёрная сапота", "⚫", 6, 5400, 2, 5),
    "white_sapote": ("Белая сапота", "🟢", 5, 5100, 3, 6),
    "star_apple": ("Звёздное яблоко", "🟣", 6, 5400, 2, 5),
    "santol": ("Сантол", "🟡", 5, 4800, 3, 6),
    "langsat": ("Лангсат", "🟡", 6, 5100, 2, 5),
    "pulasan": ("Пуласан", "🔴", 7, 5400, 2, 5),
    "nam_nam": ("Нам-нам", "🟡", 6, 5100, 2, 5),
    "jambu": ("Джамбу", "🔴", 3, 2700, 5, 10),
    "water_apple": ("Водяное яблоко", "🔴", 3, 2700, 5, 10),
    "malay_apple": ("Малайское яблоко", "🔴", 4, 3300, 4, 8),
    "june_plum": ("Июньская слива", "🟡", 4, 3900, 4, 8),
    "hog_plum": ("Свиная слива", "🟡", 3, 3300, 4, 9),
    "imbu": ("Имбу", "🟡", 4, 4200, 3, 7),
    "cupuacu": ("Купуасу", "🟤", 8, 6600, 1, 3),
    "camu_camu": ("Каму-каму", "🔴", 8, 5100, 2, 5),
    "maqui": ("Маки", "🟣", 7, 4800, 2, 5),
    "sapodilla": ("Саподилла", "🟤", 6, 5400, 2, 5),
    "ackee": ("Акки", "🟡", 8, 6000, 2, 4),
    "custard_apple": ("Кремовое яблоко", "🟢", 6, 5400, 3, 6),
    "rollinia": ("Роллиния", "🟡", 8, 6000, 1, 4),
    "biriba": ("Бириба", "🟡", 7, 5700, 2, 4),
    "abiu": ("Абиу", "🟡", 6, 5400, 2, 5),
    "kepel": ("Кепель", "🟤", 8, 6000, 1, 3),
    "baobab": ("Баобаб", "🌳", 9, 7800, 1, 3),
    "marula": ("Марула", "🟡", 6, 5100, 3, 6),
    "bergamot": ("Бергамот", "🟢", 5, 3900, 3, 7),
    "ugli": ("Угли-фрукт", "🟡", 5, 4500, 3, 7),
    "nashi": ("Наши", "🍐", 4, 3900, 4, 8),
    "medlar": ("Мушмула германская", "🟤", 3, 4200, 4, 8),
    "serviceberry": ("Ирга", "🟣", 3, 3000, 5, 10),
    "galangal": ("Галангал", "⚪", 5, 5100, 2, 5),
    "cardamom": ("Кардамон", "🟢", 6, 5700, 2, 4),
    "enoki": ("Эноки", "⚪", 4, 2700, 4, 8),
    "matsutake": ("Мацутаке", "🟤", 12, 6000, 1, 3),
    "water_chestnut": ("Водяной орех", "🟤", 3, 3300, 4, 9),
    "ice_cream_bean": ("Мороженое-боб", "⚪", 6, 5100, 2, 5),
    "pacay": ("Пакай", "🟢", 5, 4800, 3, 6),
    "golden_apple": ("Золотое яблоко", "🟡", 5, 4500, 3, 6),
    "yellow_mombin": ("Жёлтый момбин", "🟡", 3, 3000, 5, 9),
    "red_mombin": ("Красный момбин", "🔴", 3, 3000, 5, 9),
    "tapereba": ("Тапереба", "🟡", 4, 4200, 3, 7),
    "pataua": ("Патауа", "🟣", 6, 5700, 2, 4),
    "acai_premium": ("Асаи премиум", "🟣", 8, 6000, 1, 4),
    "pejibaye": ("Пежибайе", "🟠", 4, 4200, 3, 7),
    "moriche": ("Мориче", "🟠", 5, 5100, 2, 5),
    "canola": ("Канола", "🟡", 2, 1800, 7, 12),
    "sorghum": ("Сорго", "🔴", 2, 3600, 5, 9),
    "wild_rice": ("Дикий рис", "🟤", 4, 4800, 3, 7),
    "pistachio_fruit": ("Фисташка", "🟢", 6, 5400, 2, 5),
    "velvet_apple": ("Бархатное яблоко", "🟤", 5, 5100, 3, 6),
    "duku": ("Дуку", "🟡", 6, 5100, 2, 5),
    "sentul": ("Сентул", "🟡", 5, 4500, 3, 6),
    "kepayang": ("Кепайянг", "🟢", 4, 4200, 3, 7),
    "mountain_apple": ("Горное яблоко", "🔴", 4, 3600, 4, 8),
    "oteheite_apple": ("Отахитское яблоко", "🔴", 5, 3900, 3, 7),
    "mangaba": ("Мангаба", "🟡", 5, 4800, 3, 6),
    "breadnut": ("Хлебный орех", "🟢", 5, 5400, 2, 5),
    "inga": ("Инга", "🟢", 5, 4500, 3, 6),
    "jaboticaba_white": ("Белая жабутикаба", "⚪", 8, 6000, 1, 4),
    "bunga": ("Бунга", "🟣", 6, 4800, 2, 5),
    "cinnamon": ("Корица", "🟤", 5, 5400, 2, 5),
    "sapote": ("Сапота", "🟤", 6, 5700, 2, 5),
    "guanabana": ("Гуанабана", "🟢", 7, 6300, 2, 4),
    "annona": ("Аннона", "🟢", 7, 6000, 2, 4),
    "dragonfruit_yellow": ("Жёлтая питахайя", "🟡", 9, 6300, 1, 4),
    "dragonfruit_white": ("Белая питахайя", "⚪", 8, 6000, 2, 4),
    "lychee_premium": ("Личи премиум", "🔴", 8, 5700, 2, 4),
    "mangosteen_premium": ("Мангостан премиум", "🟣", 10, 6900, 1, 3),
    "durian_monthong": ("Дуриан Монтонг", "🟢", 12, 7800, 1, 2),
    "jackfruit_honey": ("Джекфрут медовый", "🟡", 9, 6900, 1, 3),
    "passionfruit_yellow": ("Жёлтая маракуйя", "🟡", 6, 4500, 3, 6),
    "passionfruit_purple": ("Фиолетовая маракуйя", "🟣", 6, 4500, 3, 6),
    "soursop_premium": ("Сметанное премиум", "🟢", 8, 6600, 1, 3),
    "cherimoya_premium": ("Черимойя премиум", "🟢", 8, 6000, 1, 3),
}

START_SEEDS = {"carrot": 5, "radish": 3, "lettuce": 2, "cucumber": 2}
# отдельная база на каждый токен бота — данные не смешиваются
import hashlib
_DB_HASH = hashlib.md5(TOKEN.encode()).hexdigest()[:10]
DB_PATH = f"game_{_DB_HASH}.db"

dp = Dispatcher()

def uid_of(event) -> int:
    return event.from_user.id


def own_cb(data: str, user_id: int) -> str:
    """callback_data с привязкой к игроку — чужие нажатия не сработают."""
    return f"{data}|{user_id}"


def parse_own(c) -> tuple:
    """Вернёт (payload, ok). ok=False если кнопку нажал не тот игрок."""
    raw = c.data or ""
    if "|" not in raw:
        return raw, True  # старые кнопки без uid — разрешаем только себе через from_user
    payload, sid = raw.rsplit("|", 1)
    try:
        owner = int(sid)
    except ValueError:
        return payload, False
    if owner != c.from_user.id:
        return payload, False
    return payload, True


# --- защита: только личные чаты и только свой аккаунт ---
def is_private(event) -> bool:
    chat = getattr(event, "chat", None) or getattr(getattr(event, "message", None), "chat", None)
    return bool(chat and chat.type == "private")


async def guard(c: CallbackQuery) -> bool:
    """Чужие кнопки / группы — игнор."""
    if not is_private(c):
        await c.answer("Бот работает только в личных сообщениях", show_alert=True)
        return False
    return True


# ==================== БАЗА ДАННЫХ ====================
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row

db.execute("""
    CREATE TABLE IF NOT EXISTS players (
        user_id     INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        vaimiki     INTEGER NOT NULL DEFAULT 0,
        plots_limit INTEGER NOT NULL DEFAULT 3
    )
""")
db.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        user_id   INTEGER,
        crop_key  TEXT,
        seeds     INTEGER NOT NULL DEFAULT 0,
        harvested INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, crop_key)
    )
""")
db.execute("""
    CREATE TABLE IF NOT EXISTS plots (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        crop_key   TEXT,
        planted_at REAL,
        ready_at   REAL
    )
""")
db.commit()

# миграция: если старая таблица без plots_limit
try:
    db.execute("SELECT plots_limit FROM players LIMIT 1")
except sqlite3.OperationalError:
    db.execute("ALTER TABLE players ADD COLUMN plots_limit INTEGER NOT NULL DEFAULT 3")
    db.commit()


def ensure_player(user):
    db.execute(
        "INSERT OR IGNORE INTO players (user_id, name, vaimiki, plots_limit) VALUES (?, ?, ?, ?)",
        (user.id, user.full_name, START_VAIMIKI, START_PLOTS)
    )
    db.execute("UPDATE players SET name = ? WHERE user_id = ?", (user.full_name, user.id))
    for crop in CROPS:
        seeds = START_SEEDS.get(crop, 0)
        db.execute(
            "INSERT OR IGNORE INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, ?, 0)",
            (user.id, crop, seeds)
        )
    db.commit()


def get_player(user_id: int):
    return db.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)).fetchone()


def get_inventory(user_id: int) -> dict:
    rows = db.execute(
        "SELECT crop_key, seeds, harvested FROM inventory WHERE user_id = ?", (user_id,)
    ).fetchall()
    result = {c: {"seeds": 0, "harvested": 0} for c in CROPS}
    for r in rows:
        if r["crop_key"] in result:
            result[r["crop_key"]] = {"seeds": r["seeds"], "harvested": r["harvested"]}
    return result


def get_plots(user_id: int):
    return db.execute(
        "SELECT * FROM plots WHERE user_id = ? ORDER BY planted_at", (user_id,)
    ).fetchall()


def count_plots(user_id: int) -> int:
    return db.execute("SELECT COUNT(*) FROM plots WHERE user_id = ?", (user_id,)).fetchone()[0]


def format_time(seconds: float) -> str:
    if seconds <= 0:
        return "✅ Готово!"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins >= 60:
        return f"{mins // 60}ч {mins % 60}м"
    return f"{mins}м {secs}с"


# ==================== КЛАВИАТУРЫ ====================
def main_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🌾 Ферма", callback_data=own_cb("farm", uid)),
        InlineKeyboardButton(text="👤 Профиль", callback_data=own_cb("profile", uid)),
    )
    b.row(
        InlineKeyboardButton(text="🛒 Магазин", callback_data=own_cb("shop", uid)),
        InlineKeyboardButton(text="🏆 Топы", callback_data=own_cb("tops", uid)),
    )
    b.row(InlineKeyboardButton(text="ℹ️ Помощь", callback_data=own_cb("help", uid)))
    return b.as_markup()


def farm_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🌱 Посадить", callback_data=own_cb("plant_menu", uid)),
        InlineKeyboardButton(text="🧺 Собрать", callback_data=own_cb("harvest", uid)),
    )
    b.row(
        InlineKeyboardButton(text="📐 Купить грядку", callback_data=own_cb("buy_plot", uid)),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=own_cb("farm", uid)),
    )
    b.row(InlineKeyboardButton(text="◀️ Меню", callback_data=own_cb("menu", uid)))
    return b.as_markup()


def plant_menu_kb(uid: int, inv: dict, page: int = 0) -> InlineKeyboardMarkup:
    keys = list(CROPS.keys())
    per_page = 8
    start = page * per_page
    chunk = keys[start:start + per_page]
    b = InlineKeyboardBuilder()
    for key in chunk:
        name, emoji, *_ = CROPS[key]
        seeds = inv.get(key, {}).get("seeds", 0)
        b.row(InlineKeyboardButton(
            text=f"{emoji} {name} ({seeds})",
            callback_data=own_cb(f"pc:{key}", uid)
        ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=own_cb(f"plant_page:{page-1}", uid)))
    if start + per_page < len(keys):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=own_cb(f"plant_page:{page+1}", uid)))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=own_cb("farm", uid)))
    return b.as_markup()


def plant_amount_kb(uid: int, crop: str, max_a: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    row = []
    for a in [1, 2, 3, 5]:
        if a <= max_a:
            row.append(InlineKeyboardButton(text=str(a), callback_data=own_cb(f"dp:{crop}:{a}", uid)))
    if row:
        b.row(*row)
    if max_a > 5:
        b.row(InlineKeyboardButton(text=f"Все ({max_a})", callback_data=own_cb(f"dp:{crop}:{max_a}", uid)))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=own_cb("plant_menu", uid)))
    return b.as_markup()


def shop_kb(uid: int, page: int = 0) -> InlineKeyboardMarkup:
    keys = list(CROPS.keys())
    per_page = 8
    start = page * per_page
    chunk = keys[start:start + per_page]
    b = InlineKeyboardBuilder()
    for key in chunk:
        name, emoji, value, *_ = CROPS[key]
        price = value * 2
        b.row(InlineKeyboardButton(
            text=f"{emoji} {name} — {price} {CURRENCY_EMOJI}",
            callback_data=own_cb(f"bs:{key}", uid)
        ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=own_cb(f"shop_page:{page-1}", uid)))
    if start + per_page < len(keys):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=own_cb(f"shop_page:{page+1}", uid)))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="📐 Купить грядку", callback_data=own_cb("buy_plot", uid)))
    b.row(InlineKeyboardButton(text="◀️ Меню", callback_data=own_cb("menu", uid)))
    return b.as_markup()


def buy_amount_kb(uid: int, crop: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for a in [1, 3, 5, 10]:
        b.add(InlineKeyboardButton(text=str(a), callback_data=own_cb(f"db:{crop}:{a}", uid)))
    b.adjust(4)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=own_cb("shop", uid)))
    return b.as_markup()


def tops_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💎 Топ Ваймиков", callback_data=own_cb("top:vaimiki", uid)))
    b.row(
        InlineKeyboardButton(text="🥕 Морковь", callback_data=own_cb("top:carrot", uid)),
        InlineKeyboardButton(text="🍓 Клубника", callback_data=own_cb("top:strawberry", uid)),
    )
    b.row(
        InlineKeyboardButton(text="🍅 Помидор", callback_data=own_cb("top:tomato", uid)),
        InlineKeyboardButton(text="🍉 Арбуз", callback_data=own_cb("top:watermelon", uid)),
    )
    b.row(
        InlineKeyboardButton(text="🥔 Картошка", callback_data=own_cb("top:potato", uid)),
        InlineKeyboardButton(text="🍇 Виноград", callback_data=own_cb("top:grape", uid)),
    )
    b.row(InlineKeyboardButton(text="◀️ Меню", callback_data=own_cb("menu", uid)))
    return b.as_markup()


def back_tops_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ К топам", callback_data=own_cb("tops", uid)))
    b.row(InlineKeyboardButton(text="🏠 Меню", callback_data=own_cb("menu", uid)))
    return b.as_markup()


def back_menu_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Меню", callback_data=own_cb("menu", uid)))
    return b.as_markup()


# ==================== КОМАНДЫ ====================
@dp.message(CommandStart())
@dp.message(Command("help"))
async def cmd_start(message: Message):
    ensure_player(message.from_user)
    await message.answer(
        f"🌾 <b>Ферма Ваймиков</b>\n\n"
        f"Выращивай овощи и фрукты, зарабатывай {CURRENCY_EMOJI} <b>{CURRENCY}</b>!\n\n"
        f"• 25+ культур\n"
        f"• Покупай дополнительные грядки\n"
        f"• Соревнуйся в топах\n\n"
        f"Команды: /farm /shop /balance /top\n"
        f"Или кнопки 👇",
        reply_markup=main_kb(message.from_user.id),
        parse_mode="HTML"
    )


@dp.message(Command("farm"))
async def cmd_farm(message: Message):
    ensure_player(message.from_user)
    await show_farm(message, message.from_user.id)


@dp.message(Command("shop"))
async def cmd_shop(message: Message):
    ensure_player(message.from_user)
    p = get_player(message.from_user.id)
    await message.answer(
        f"🛒 <b>Магазин</b>\nУ тебя: {CURRENCY_EMOJI} <b>{p['vaimiki']}</b>",
        reply_markup=shop_kb(message.from_user.id),
        parse_mode="HTML"
    )


@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    ensure_player(message.from_user)
    await show_profile(message, message.from_user)


@dp.message(Command("top"))
async def cmd_top(message: Message):
    await message.answer("🏆 <b>Топы</b>", reply_markup=tops_kb(message.from_user.id), parse_mode="HTML")


# ==================== ПОКАЗ ====================
async def show_farm(target, user_id: int, edit: bool = False):
    p = get_player(user_id)
    plots = get_plots(user_id)
    limit = p["plots_limit"]
    now = time.time()
    lines = [f"🌾 <b>Твоя ферма</b>  ({count_plots(user_id)}/{limit} грядок)\n"]
    if not plots:
        lines.append("Грядки пустые. Нажми «Посадить».")
    else:
        ready = 0
        for i, pl in enumerate(plots, 1):
            name, emoji, *_ = CROPS[pl["crop_key"]]
            left = pl["ready_at"] - now
            if left <= 0:
                ready += 1
            lines.append(f"{i}. {emoji} {name} — {format_time(left)}")
        if ready:
            lines.append(f"\n🎉 Готово к сбору: <b>{ready}</b>")
    if limit < MAX_PLOTS_LIMIT:
        lines.append(f"\nСлед. грядка: {plot_price(limit)} {CURRENCY_EMOJI}")
    text = "\n".join(lines)
    if edit and hasattr(target, "message"):
        await target.message.edit_text(text, reply_markup=farm_kb(user_id), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=farm_kb(user_id), parse_mode="HTML")


async def show_profile(target, user, edit: bool = False):
    p = get_player(user.id)
    inv = get_inventory(user.id)
    lines = [
        f"👤 <b>{user.full_name}</b>",
        f"{CURRENCY_EMOJI} {CURRENCY}: <b>{p['vaimiki']}</b>",
        f"Грядок: <b>{p['plots_limit']}</b>/{MAX_PLOTS_LIMIT}",
        "",
        "📦 Собрано (топ):"
    ]
    # показываем только то, что есть
    items = [(k, v) for k, v in inv.items() if v["harvested"] > 0 or v["seeds"] > 0]
    items.sort(key=lambda x: -x[1]["harvested"])
    for key, d in items[:12]:
        name, emoji, *_ = CROPS[key]
        lines.append(f"{emoji} {name}: семян {d['seeds']} | собрано {d['harvested']}")
    if not items:
        lines.append("Пока пусто")
    text = "\n".join(lines)
    uid = user.id
    if edit and hasattr(target, "message"):
        await target.message.edit_text(text, reply_markup=back_menu_kb(uid), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=back_menu_kb(uid), parse_mode="HTML")


# ==================== CALLBACKS ====================
@dp.callback_query(F.data.startswith("menu"))
async def cb_menu(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    await c.message.edit_text("🏠 <b>Главное меню</b>", reply_markup=main_kb(c.from_user.id), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data.startswith("farm"))
async def cb_farm(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    ensure_player(c.from_user)
    await show_farm(c, c.from_user.id, edit=True)
    await c.answer()


@dp.callback_query(F.data.startswith("profile"))
async def cb_profile(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    ensure_player(c.from_user)
    await show_profile(c, c.from_user, edit=True)
    await c.answer()


@dp.callback_query(F.data.startswith("help"))
async def cb_help(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    text = (
        f"ℹ️ <b>Как играть</b>\n\n"
        f"1. Купи семена в магазине\n"
        f"2. Посади на ферме\n"
        f"3. Жди роста\n"
        f"4. Собери урожай → {CURRENCY}\n"
        f"5. Покупай новые грядки, чтобы сажать больше\n\n"
        f"Стартовых грядок: {START_PLOTS}\n"
        f"Максимум грядок: {MAX_PLOTS_LIMIT}\n"
        f"Всего культур: {len(CROPS)}"
    )
    await c.message.edit_text(text, reply_markup=back_menu_kb(c.from_user.id), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data.startswith("buy_plot"))
async def cb_buy_plot(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    ensure_player(c.from_user)
    p = get_player(c.from_user.id)
    limit = p["plots_limit"]
    if limit >= MAX_PLOTS_LIMIT:
        await c.answer("Уже максимум грядок!", show_alert=True)
        return
    price = plot_price(limit)
    if p["vaimiki"] < price:
        await c.answer(f"Нужно {price} {CURRENCY_EMOJI}, у тебя {p['vaimiki']}", show_alert=True)
        return
    db.execute(
        "UPDATE players SET vaimiki = vaimiki - ?, plots_limit = plots_limit + 1 WHERE user_id = ?",
        (price, c.from_user.id)
    )
    db.commit()
    await c.answer(f"Грядка куплена! Теперь {limit + 1}", show_alert=True)
    await show_farm(c, c.from_user.id, edit=True)


@dp.callback_query(F.data.startswith("plant_menu"))
@dp.callback_query(F.data.startswith("plant_page:"))
async def cb_plant_menu(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    page = 0
    if payload.startswith("plant_page:"):
        page = int(payload.split(":")[1])
    inv = get_inventory(c.from_user.id)
    p = get_player(c.from_user.id)
    free = p["plots_limit"] - count_plots(c.from_user.id)
    await c.message.edit_text(
        f"🌱 <b>Посадка</b>\nСвободных грядок: <b>{free}</b>",
        reply_markup=plant_menu_kb(c.from_user.id, inv, page),
        parse_mode="HTML"
    )
    await c.answer()


@dp.callback_query(F.data.startswith("pc:"))
async def cb_plant_crop(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    crop = payload.split(":")[1]
    if crop not in CROPS:
        await c.answer("Нет такой культуры", show_alert=True)
        return
    inv = get_inventory(c.from_user.id)
    seeds = inv[crop]["seeds"]
    p = get_player(c.from_user.id)
    free = p["plots_limit"] - count_plots(c.from_user.id)
    max_can = min(seeds, free)
    name, emoji, value, grow, ymin, ymax = CROPS[crop]
    if max_can <= 0:
        await c.answer("Нет семян или свободных грядок!", show_alert=True)
        return
    text = (
        f"{emoji} <b>{name}</b>\n"
        f"Рост: {grow // 60} мин | Урожай: {ymin}–{ymax}\n"
        f"Цена 1 шт: {value} {CURRENCY_EMOJI}\n\n"
        f"Семян: {seeds} | Свободно: {free}\n"
        f"Сколько посадить?"
    )
    await c.message.edit_text(text, reply_markup=plant_amount_kb(c.from_user.id, crop, max_can), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data.startswith("dp:"))
async def cb_do_plant(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    _, crop, amount_s = payload.split(":")
    amount = int(amount_s)
    inv = get_inventory(c.from_user.id)
    p = get_player(c.from_user.id)
    free = p["plots_limit"] - count_plots(c.from_user.id)
    if inv[crop]["seeds"] < amount or amount > free:
        await c.answer("Нельзя посадить столько", show_alert=True)
        return
    _, _, _, grow, _, _ = CROPS[crop]
    now = time.time()
    db.execute(
        "UPDATE inventory SET seeds = seeds - ? WHERE user_id = ? AND crop_key = ?",
        (amount, c.from_user.id, crop)
    )
    for _ in range(amount):
        db.execute(
            "INSERT INTO plots (user_id, crop_key, planted_at, ready_at) VALUES (?, ?, ?, ?)",
            (c.from_user.id, crop, now, now + grow)
        )
    db.commit()
    name, emoji, *_ = CROPS[crop]
    await c.answer(f"Посажено {amount} × {emoji} {name}!", show_alert=True)
    await show_farm(c, c.from_user.id, edit=True)


@dp.callback_query(F.data.startswith("harvest"))
async def cb_harvest(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    now = time.time()
    plots = get_plots(c.from_user.id)
    ready = [p for p in plots if p["ready_at"] <= now]
    if not ready:
        await c.answer("Ещё нечего собирать 🌱", show_alert=True)
        return
    harvested = {}
    total_v = 0
    ids = []
    for pl in ready:
        crop = pl["crop_key"]
        _, _, value, _, ymin, ymax = CROPS[crop]
        amt = random.randint(ymin, ymax)
        harvested[crop] = harvested.get(crop, 0) + amt
        total_v += amt * value
        ids.append(pl["id"])
    for pid in ids:
        db.execute("DELETE FROM plots WHERE id = ?", (pid,))
    for crop, amt in harvested.items():
        db.execute(
            "UPDATE inventory SET harvested = harvested + ? WHERE user_id = ? AND crop_key = ?",
            (amt, c.from_user.id, crop)
        )
    db.execute(
        "UPDATE players SET vaimiki = vaimiki + ? WHERE user_id = ?",
        (total_v, c.from_user.id)
    )
    db.commit()
    lines = ["🧺 <b>Урожай собран!</b>\n"]
    for crop, amt in harvested.items():
        name, emoji, value, *_ = CROPS[crop]
        lines.append(f"{emoji} {name}: +{amt} (+{amt * value} {CURRENCY_EMOJI})")
    lines.append(f"\n💰 +{total_v} {CURRENCY}")
    await c.message.edit_text("\n".join(lines), reply_markup=farm_kb(c.from_user.id), parse_mode="HTML")
    await c.answer("Готово!")


@dp.callback_query(F.data.startswith("shop"))
@dp.callback_query(F.data.startswith("shop_page:"))
async def cb_shop(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    ensure_player(c.from_user)
    page = 0
    if payload.startswith("shop_page:"):
        page = int(payload.split(":")[1])
    p = get_player(c.from_user.id)
    await c.message.edit_text(
        f"🛒 <b>Магазин</b>\nУ тебя: {CURRENCY_EMOJI} <b>{p['vaimiki']}</b>",
        reply_markup=shop_kb(c.from_user.id, page),
        parse_mode="HTML"
    )
    await c.answer()


@dp.callback_query(F.data.startswith("bs:"))
async def cb_buy_seed(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    crop = payload.split(":")[1]
    name, emoji, value, *_ = CROPS[crop]
    price = value * 2
    await c.message.edit_text(
        f"{emoji} <b>{name}</b>\nЦена: {price} {CURRENCY_EMOJI} / семя\nСколько купить?",
        reply_markup=buy_amount_kb(c.from_user.id, crop),
        parse_mode="HTML"
    )
    await c.answer()


@dp.callback_query(F.data.startswith("db:"))
async def cb_do_buy(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    _, crop, amount_s = payload.split(":")
    amount = int(amount_s)
    _, _, value, *_ = CROPS[crop]
    cost = value * 2 * amount
    p = get_player(c.from_user.id)
    if p["vaimiki"] < cost:
        await c.answer("Недостаточно Ваймиков!", show_alert=True)
        return
    db.execute(
        "UPDATE players SET vaimiki = vaimiki - ? WHERE user_id = ?",
        (cost, c.from_user.id)
    )
    db.execute(
        "INSERT OR IGNORE INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, 0, 0)",
        (c.from_user.id, crop)
    )
    db.execute(
        "UPDATE inventory SET seeds = seeds + ? WHERE user_id = ? AND crop_key = ?",
        (amount, c.from_user.id, crop)
    )
    db.commit()
    name, emoji, *_ = CROPS[crop]
    p = get_player(c.from_user.id)
    await c.answer(f"+{amount} {emoji} {name} за {cost}!", show_alert=True)
    await c.message.edit_text(
        f"🛒 <b>Магазин</b>\nУ тебя: {CURRENCY_EMOJI} <b>{p['vaimiki']}</b>\n✅ Куплено!",
        reply_markup=shop_kb(message.from_user.id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("tops"))
async def cb_tops(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    await c.message.edit_text("🏆 <b>Топы</b>", reply_markup=tops_kb(message.from_user.id), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data.startswith("top:"))
async def cb_top(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer("⛔ Это кнопки другого игрока. Открой /start у себя.", show_alert=True)
        return
    key = payload.split(":")[1]
    if key == "vaimiki":
        rows = db.execute(
            "SELECT name, vaimiki FROM players ORDER BY vaimiki DESC LIMIT 10"
        ).fetchall()
        lines = [f"💎 <b>Топ по {CURRENCY}</b>\n"]
        if not rows:
            lines.append("Пока пусто")
        else:
            for i, r in enumerate(rows):
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
                lines.append(f"{medal} {r['name']}: <b>{r['vaimiki']}</b> {CURRENCY_EMOJI}")
    else:
        if key not in CROPS:
            await c.answer("Нет", show_alert=True)
            return
        name, emoji, *_ = CROPS[key]
        rows = db.execute("""
            SELECT p.name, i.harvested
            FROM inventory i JOIN players p ON p.user_id = i.user_id
            WHERE i.crop_key = ?
            ORDER BY i.harvested DESC LIMIT 10
        """, (key,)).fetchall()
        lines = [f"{emoji} <b>Топ по {name}</b>\n"]
        if not rows:
            lines.append("Пока пусто")
        else:
            for i, r in enumerate(rows):
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
                lines.append(f"{medal} {r['name']}: <b>{r['harvested']}</b> шт")
    await c.message.edit_text("\n".join(lines), reply_markup=back_tops_kb(c.from_user.id), parse_mode="HTML")
    await c.answer()


# ==================== ЗАПУСК ====================


async def main():
    if not TOKEN or "ВСТАВЬ" in str(TOKEN):
        raise SystemExit("Укажи токен")

    logging.basicConfig(level=logging.INFO)
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await bot.set_my_commands([
        BotCommand(command="start", description="🌱 Старт / меню"),
        BotCommand(command="farm", description="🌾 Ферма"),
        BotCommand(command="shop", description="🛒 Магазин"),
        BotCommand(command="balance", description="👤 Профиль"),
        BotCommand(command="top", description="🏆 Топы"),
        BotCommand(command="help", description="ℹ️ Помощь"),
    ])

    print("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
