"""
Огородник 3.1 — Ферма Ваймиков
100 культур: магазин идёт от дешёвого к дорогому — чем дальше, тем дороже семена и тем больше урожай.
У каждого плода свой вес и шанс мутации: чем тяжелее плод и реже мутация, тем больше Ваймиков.

Запуск: pip install -r requirements.txt && BOT_TOKEN=твой_токен python main.py
"""

import asyncio
import glob
import html
import logging
import os
import random
import shutil
import sqlite3
import time

from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


def _load_token() -> str:
    """Токен берём из переменной окружения BOT_TOKEN или из файла token.txt (в код его не пишем!)."""
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token and os.path.exists("token.txt"):
        with open("token.txt", encoding="utf-8") as f:
            token = f.read().strip()
    return token


TOKEN = _load_token()

# Твой Telegram user id (через @userinfobot). Можно несколько через запятую.
# На bothost: переменная окружения ADMIN_IDS=123456789
ADMIN_IDS = set()
for _part in os.getenv("ADMIN_IDS", "").replace(" ", "").split(","):
    if _part.isdigit():
        ADMIN_IDS.add(int(_part))

CURRENCY = "Ваймики"
CURRENCY_EMOJI = "💎"
START_PLOTS = 5
MAX_PLOTS_LIMIT = 1000
START_VAIMIKI = 30


def plot_price(current_plots: int) -> int:
    """Цена следующей грядки: растёт всё быстрее, чтобы не обесценивалась вместе с урожаем."""
    return round(12 * current_plots * 1.04 ** current_plots)


# ==================== КУЛЬТУРЫ ====================
# Список идёт ПО ПОРЯДКУ магазина: от дешёвого к дорогому. Хочешь добавить культуру —
# вставь строку туда, где она должна стоять, цены и рост посчитаются сами.
# формат: (ключ, название, эмодзи, средний вес плода в кг)
CROP_LIST = [
    ("radish", "Редис", "🔴", 0.05), ("lettuce", "Салат", "🥬", 0.25), ("carrot", "Морковь", "🥕", 0.15),
    ("spinach", "Шпинат", "🍃", 0.05), ("dill", "Укроп", "🌿", 0.03), ("parsley", "Петрушка", "🌿", 0.03),
    ("onion", "Лук", "🧅", 0.15), ("cucumber", "Огурец", "🥒", 0.2), ("peas", "Горох", "🟢", 0.02),
    ("beet", "Свёкла", "🟣", 0.3),
    ("potato", "Картошка", "🥔", 0.2), ("cabbage", "Капуста", "🥬", 1.5), ("zucchini", "Кабачок", "🟢", 0.5),
    ("tomato", "Помидор", "🍅", 0.2), ("garlic", "Чеснок", "🧄", 0.05), ("beans", "Фасоль", "🫘", 0.02),
    ("strawberry", "Клубника", "🍓", 0.02), ("apple", "Яблоко", "🍎", 0.2), ("pear", "Груша", "🍐", 0.2),
    ("peanut", "Арахис", "🥜", 0.03),
    ("corn", "Кукуруза", "🌽", 0.3), ("pepper", "Перец", "🫑", 0.2), ("cauliflower", "Цветная капуста", "⚪", 0.9),
    ("broccoli", "Брокколи", "🥦", 0.4), ("raspberry", "Малина", "🔴", 0.015), ("cherry", "Вишня", "🍒", 0.008),
    ("plum", "Слива", "🟣", 0.06), ("lemon", "Лимон", "🍋", 0.12), ("blueberry", "Черника", "🫐", 0.01),
    ("walnut", "Грецкий орех", "🌰", 0.03),
    ("eggplant", "Баклажан", "🍆", 0.3), ("pumpkin", "Тыква", "🎃", 8.0), ("grape", "Виноград", "🍇", 0.4),
    ("peach", "Персик", "🍑", 0.15), ("banana", "Банан", "🍌", 0.15), ("orange", "Апельсин", "🍊", 0.2),
    ("hazelnut", "Фундук", "🌰", 0.02), ("oyster_mushroom", "Вёшенка", "⚪", 0.05),
    ("asparagus", "Спаржа", "🟢", 0.03), ("watermelon", "Арбуз", "🍉", 6.0),
    ("melon", "Дыня", "🍈", 1.8), ("kiwi", "Киви", "🥝", 0.08), ("chestnut", "Каштан", "🌰", 0.02),
    ("sweet_potato", "Батат", "🍠", 0.3), ("ginger", "Имбирь", "🟤", 0.1), ("artichoke", "Артишок", "🟢", 0.3),
    ("almond", "Миндаль", "🌰", 0.02), ("shiitake", "Шиитаке", "🟤", 0.05), ("avocado", "Авокадо", "🥑", 0.2),
    ("mango", "Манго", "🥭", 0.35),
    ("pineapple", "Ананас", "🍍", 1.6), ("coconut", "Кокос", "🥥", 0.9), ("pomegranate", "Гранат", "🔴", 0.3),
    ("fig", "Инжир", "🟤", 0.06), ("chili", "Чили", "🌶️", 0.02), ("pecan", "Пекан", "🌰", 0.02),
    ("chanterelle", "Лисичка", "🟠", 0.04), ("cranberry", "Клюква", "🔴", 0.01), ("papaya", "Папайя", "🧡", 0.8),
    ("pomelo", "Помело", "🟡", 0.8),
    ("dragonfruit", "Питахайя", "🐉", 0.4), ("lychee", "Личи", "🔴", 0.02), ("passionfruit", "Маракуйя", "🟣", 0.05),
    ("persimmon", "Хурма", "🟠", 0.2), ("macadamia", "Макадамия", "🟤", 0.01), ("pine_nut", "Кедровый орех", "🌲", 0.01),
    ("porcini", "Белый гриб", "🟤", 0.2), ("cardamom", "Кардамон", "🟢", 0.01), ("cinnamon", "Корица", "🟤", 0.02),
    ("jackfruit", "Джекфрут", "🟡", 9.0),
    ("goji", "Годжи", "🔴", 0.01), ("acai", "Асаи", "🟣", 0.01), ("durian", "Дуриан", "🟢", 2.5),
    ("mangosteen", "Мангостан", "🟣", 0.1), ("rambutan", "Рамбутан", "🔴", 0.03),
    ("brazil_nut", "Бразильский орех", "🟤", 0.02), ("morel", "Сморчок", "🟤", 0.03), ("wasabi", "Васаби", "🟢", 0.1),
    ("pistachio_fruit", "Фисташка", "🟢", 0.01), ("cashew_fruit", "Кешью", "🟡", 0.01),
    ("starfruit", "Карамбола", "⭐", 0.1), ("soursop", "Сметанное яблоко", "🟢", 1.2), ("vanilla", "Ваниль", "🟤", 0.01),
    ("olive", "Олива", "🫒", 0.005), ("saffron", "Шафран", "🟣", 0.002), ("truffle", "Трюфель", "⚫", 0.1),
    ("matsutake", "Мацутаке", "🟤", 0.08), ("black_walnut", "Чёрный орех", "⚫", 0.04),
    ("pili_nut", "Пили", "🟤", 0.02), ("baobab", "Баобаб", "🌳", 1.0),
    ("miracle_fruit", "Чудо-ягода", "🔴", 0.01), ("jabuticaba", "Жабутикаба", "🟣", 0.03),
    ("cupuacu", "Купуасу", "🟤", 1.0), ("durian_monthong", "Дуриан Монтонг", "🟢", 3.0),
    ("dragonfruit_yellow", "Жёлтая питахайя", "🟡", 0.4), ("golden_apple", "Золотое яблоко", "🟡", 0.3),
    ("carolina_reaper", "Каролинский жнец", "🌶️", 0.01), ("jackfruit_honey", "Джекфрут медовый", "🟡", 9.0),
    ("mangosteen_premium", "Мангостан премиум", "🟣", 0.1), ("golden_walnut", "Золотой орех", "🟡", 0.05),
]

# --- как считается прогрессия (крути под себя) ---
PRICE_GROWTH = 0.05      # цена плода каждый раз растёт минимум на 1 и на ~5%
SEED_PRICE_MULT = 2      # семя стоит в 2 раза дороже среднего плода
GROW_MIN_FIRST = 15      # рост первой культуры, минут
GROW_MIN_LAST = 180      # рост последней культуры, минут
YIELD_AVG_FIRST = 8      # плодов с грядки в среднем у первой культуры
YIELD_AVG_LAST = 14      # ...и у последней: чем дальше, тем больше


def _build_crops() -> dict:
    """ключ -> (название, эмодзи, цена плода, рост в секундах, урожай от, урожай до)"""
    n = len(CROP_LIST)
    crops = {}
    value = 0
    for i, (key, name, emoji, _kg) in enumerate(CROP_LIST):
        value = 1 if i == 0 else value + max(1, round(value * PRICE_GROWTH))  # строго растёт
        t = i / (n - 1)
        grow_min = 5 * round((GROW_MIN_FIRST + (GROW_MIN_LAST - GROW_MIN_FIRST) * t) / 5)
        avg_yield = YIELD_AVG_FIRST + (YIELD_AVG_LAST - YIELD_AVG_FIRST) * t
        crops[key] = (name, emoji, value, grow_min * 60, round(avg_yield * 0.7), round(avg_yield * 1.3))
    return crops


CROPS = _build_crops()
CROP_ORDER = [row[0] for row in CROP_LIST]
BASE_WEIGHT = {row[0]: row[3] for row in CROP_LIST}

START_SEEDS = {"radish": 3, "lettuce": 2}

# ==================== ВЕС ====================
WEIGHT_POWER = 1.5      # цена растёт как (вес / средний вес) ** WEIGHT_POWER
GIANT_CHANCE = 0.03     # шанс гиганта (вес в 1.8–3 раза больше среднего)


def seed_price(key: str) -> int:
    return CROPS[key][2] * SEED_PRICE_MULT


def fmt_num(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def money(n) -> str:
    return f"{fmt_num(n)} {CURRENCY_EMOJI}"


def fmt_weight(kg: float) -> str:
    if kg < 1:
        return f"{kg * 1000:.0f} г"
    return f"{kg:.2f} кг"


def fmt_minutes(seconds: int) -> str:
    m = int(seconds // 60)
    if m >= 60:
        return f"{m // 60}ч {m % 60}м" if m % 60 else f"{m // 60}ч"
    return f"{m} мин"


# ==================== МУТАЦИИ ====================
# ключ: (название, эмодзи, множитель цены, шанс в % на каждый плод)
# чем реже мутация — тем больше множитель
MUTATIONS = {
    "wet":     ("Мокрый",      "💧", 2,   12.0),
    "chilled": ("Холодный",    "❄️", 3,   6.0),
    "moonlit": ("Лунный",      "🌙", 5,   3.0),
    "golden":  ("Золотой",     "✨", 10,  1.2),
    "frozen":  ("Ледяной",     "🧊", 20,  0.5),
    "rainbow": ("Радужный",    "🌈", 50,  0.15),
    "thunder": ("Громовой",    "⚡", 100, 0.04),
}


def roll_mutation():
    """Вернёт ключ мутации или None. У плода максимум одна мутация."""
    r = random.random() * 100
    acc = 0.0
    for key, (_, _, _, chance) in MUTATIONS.items():
        acc += chance
        if r < acc:
            return key
    return None


def roll_fruit(crop_key: str):
    """Один плод: (вес в кг, мутация или None, цена в Ваймиках — дробная)."""
    if random.random() < GIANT_CHANCE:
        ratio = random.uniform(1.8, 3.0)
    else:
        ratio = random.uniform(0.6, 1.4)
    mut = roll_mutation()
    mult = MUTATIONS[mut][2] if mut else 1
    value = CROPS[crop_key][2] * (ratio ** WEIGHT_POWER) * mult
    return BASE_WEIGHT[crop_key] * ratio, mut, value


def roll_harvest(crop_keys):
    """Собирает урожай со списка грядок (по одному ключу культуры на грядку)."""
    per_crop = {}   # культура -> {"amt", "value" (дробная), "best_w"}
    muts = {}       # мутация -> сколько штук
    best = []       # топ-3 самых дорогих плода: (цена, культура, вес, мутация)
    for crop in crop_keys:
        ymin, ymax = CROPS[crop][4], CROPS[crop][5]
        d = per_crop.setdefault(crop, {"amt": 0, "value": 0.0, "best_w": 0.0})
        for _ in range(random.randint(ymin, ymax)):
            w, mut, val = roll_fruit(crop)
            d["amt"] += 1
            d["value"] += val
            if w > d["best_w"]:
                d["best_w"] = w
            if mut:
                muts[mut] = muts.get(mut, 0) + 1
            if len(best) < 3 or val > best[-1][0]:
                best.append((val, crop, w, mut))
                best.sort(key=lambda t: -t[0])
                del best[3:]
    total = 0
    for d in per_crop.values():
        d["coins"] = max(1, round(d["value"]))
        total += d["coins"]
    return {"crops": per_crop, "muts": muts, "best": best, "total": total}


# ==================== БАЗА ДАННЫХ ====================
dp = Dispatcher(storage=MemoryStorage())

# База лежит в DATA_DIR: на Bothost папка /app/data не стирается при «Обновить из Git».
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except OSError:          # например, локально нет прав на /app — кладём рядом с main.py
    DATA_DIR = "."
DB_PATH = os.path.join(DATA_DIR, "game.db")

# Старые версии называли файл game_<хэш токена>.db. Если ты загрузил такой файл в DATA_DIR
# (или он лежит рядом с main.py) — подхватываем и переименовываем, чтобы игроки не потерялись.
if not os.path.exists(DB_PATH):
    _old_dbs = sorted(
        glob.glob(os.path.join(DATA_DIR, "game_*.db")) + glob.glob("game_*.db"),
        key=os.path.getmtime,
    )
    if _old_dbs:
        shutil.copy2(_old_dbs[-1], DB_PATH)

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
        user_id     INTEGER,
        crop_key    TEXT,
        seeds       INTEGER NOT NULL DEFAULT 0,
        harvested   INTEGER NOT NULL DEFAULT 0,
        best_weight REAL NOT NULL DEFAULT 0,
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
# сколько мутаций каждого вида нашёл игрок
db.execute("""
    CREATE TABLE IF NOT EXISTS mutation_log (
        user_id      INTEGER,
        mutation_key TEXT,
        count        INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, mutation_key)
    )
""")
db.execute("CREATE INDEX IF NOT EXISTS idx_plots_user ON plots (user_id)")
db.execute("""
    CREATE TABLE IF NOT EXISTS user_chats (
        user_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        PRIMARY KEY (user_id, chat_id)
    )
""")
db.execute("""
    CREATE TABLE IF NOT EXISTS ready_notified (
        plot_id INTEGER PRIMARY KEY
    )
""")
db.commit()


def _add_column_if_missing(table: str, column: str, ddl: str):
    cols = [r["name"] for r in db.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        db.commit()


# миграции для баз, созданных старыми версиями бота
_add_column_if_missing("players", "plots_limit", "INTEGER NOT NULL DEFAULT 3")
_add_column_if_missing("inventory", "best_weight", "REAL NOT NULL DEFAULT 0")

REFUND_PLANT = 20   # Ваймиков за посаженную грядку убранной культуры
REFUND_SEED = 5     # Ваймиков за семя убранной культуры


def migrate_removed_crops():
    """Культур стало меньше: убираем старые из базы, а игрокам возвращаем Ваймики."""
    marks = ",".join("?" * len(CROPS))
    keys = tuple(CROPS)
    refunds = {}
    for r in db.execute(
        f"SELECT user_id, COUNT(*) AS n FROM plots WHERE crop_key NOT IN ({marks}) GROUP BY user_id", keys
    ):
        refunds[r["user_id"]] = refunds.get(r["user_id"], 0) + r["n"] * REFUND_PLANT
    for r in db.execute(
        f"SELECT user_id, SUM(seeds) AS n FROM inventory WHERE crop_key NOT IN ({marks}) GROUP BY user_id", keys
    ):
        refunds[r["user_id"]] = refunds.get(r["user_id"], 0) + (r["n"] or 0) * REFUND_SEED
    for user_id, coins in refunds.items():
        db.execute("UPDATE players SET vaimiki = vaimiki + ? WHERE user_id = ?", (coins, user_id))
    db.execute(f"DELETE FROM plots WHERE crop_key NOT IN ({marks})", keys)
    db.execute(f"DELETE FROM inventory WHERE crop_key NOT IN ({marks})", keys)
    db.commit()


migrate_removed_crops()

def ensure_player(user) -> bool:
    """Заносит игрока в базу, если его там ещё нет. True — если игрок новый."""
    row = db.execute("SELECT name FROM players WHERE user_id = ?", (user.id,)).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO players (user_id, name, vaimiki, plots_limit) VALUES (?, ?, ?, ?)",
            (user.id, user.full_name, START_VAIMIKI, START_PLOTS)
        )
        for crop in CROPS:
            db.execute(
                "INSERT OR IGNORE INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, ?, 0)",
                (user.id, crop, START_SEEDS.get(crop, 0))
            )
        db.commit()
        logging.info("Новый игрок в базе: %s (id %s)", user.full_name, user.id)
        return True
    if row["name"] != user.full_name:
        db.execute("UPDATE players SET name = ? WHERE user_id = ?", (user.full_name, user.id))
        db.commit()
    return False


def track_chat(user_id: int, chat_id: int):
    """Запоминаем чат, где писал игрок — туда уйдут уведомления о созревании."""
    if chat_id is None:
        return
    db.execute(
        "INSERT OR IGNORE INTO user_chats (user_id, chat_id) VALUES (?, ?)",
        (user_id, chat_id)
    )
    db.commit()


class RegisterMiddleware(BaseMiddleware):
    """Любое сообщение или нажатие кнопки сначала записывает игрока в базу, потом идёт к обработчику."""

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is not None and not user.is_bot:
            ensure_player(user)
            chat = getattr(event, "chat", None)
            if chat is None and getattr(event, "message", None) is not None:
                chat = event.message.chat
            if chat is not None:
                track_chat(user.id, chat.id)
        return await handler(event, data)


dp.message.outer_middleware(RegisterMiddleware())
dp.callback_query.outer_middleware(RegisterMiddleware())


def get_player(user_id: int):
    return db.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)).fetchone()


def get_inventory(user_id: int) -> dict:
    rows = db.execute(
        "SELECT crop_key, seeds, harvested, best_weight FROM inventory WHERE user_id = ?", (user_id,)
    ).fetchall()
    result = {k: {"seeds": 0, "harvested": 0, "best_weight": 0.0} for k in CROPS}
    for r in rows:
        if r["crop_key"] in result:
            result[r["crop_key"]] = {
                "seeds": r["seeds"], "harvested": r["harvested"], "best_weight": r["best_weight"],
            }
    return result


def get_plots(user_id: int):
    return db.execute(
        "SELECT * FROM plots WHERE user_id = ? ORDER BY planted_at", (user_id,)
    ).fetchall()


def count_plots(user_id: int) -> int:
    return db.execute("SELECT COUNT(*) FROM plots WHERE user_id = ?", (user_id,)).fetchone()[0]


def count_ready(user_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM plots WHERE user_id = ? AND ready_at <= ?", (user_id, time.time())
    ).fetchone()[0]


def save_harvest(user_id: int, plot_ids, res: dict):
    """Записывает результат сбора в базу. Без await внутри — сбор атомарный."""
    db.executemany("DELETE FROM plots WHERE id = ?", [(pid,) for pid in plot_ids])
    for crop, d in res["crops"].items():
        db.execute(
            "INSERT OR IGNORE INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, 0, 0)",
            (user_id, crop)
        )
        db.execute(
            "UPDATE inventory SET harvested = harvested + ?, best_weight = MAX(best_weight, ?) "
            "WHERE user_id = ? AND crop_key = ?",
            (d["amt"], d["best_w"], user_id, crop)
        )
    for mut, n in res["muts"].items():
        db.execute(
            "INSERT OR IGNORE INTO mutation_log (user_id, mutation_key, count) VALUES (?, ?, 0)",
            (user_id, mut)
        )
        db.execute(
            "UPDATE mutation_log SET count = count + ? WHERE user_id = ? AND mutation_key = ?",
            (n, user_id, mut)
        )
    db.execute("UPDATE players SET vaimiki = vaimiki + ? WHERE user_id = ?", (res["total"], user_id))
    db.commit()



def do_collect(user_id: int):
    """Собрать весь готовый урожай. Вернёт res или None если нечего."""
    now = time.time()
    ready = [p for p in get_plots(user_id) if p["ready_at"] <= now and p["crop_key"] in CROPS]
    if not ready:
        return None
    res = roll_harvest([p["crop_key"] for p in ready])
    save_harvest(user_id, [p["id"] for p in ready], res)
    # эти грядки уже собраны — уведомление больше не нужно
    db.executemany("DELETE FROM ready_notified WHERE plot_id = ?", [(p["id"],) for p in ready])
    db.commit()
    return res


def do_auto_plant(user_id: int):
    """Сажает имеющиеся семена на свободные грядки (от дешёвых к дорогим)."""
    p = get_player(user_id)
    free = p["plots_limit"] - count_plots(user_id)
    if free <= 0:
        return 0, []
    inv = get_inventory(user_id)
    planted_list = []
    total = 0
    now = time.time()
    for crop in CROP_ORDER:
        if free <= 0:
            break
        seeds = inv.get(crop, {}).get("seeds", 0)
        if seeds <= 0:
            continue
        n = min(seeds, free)
        grow = CROPS[crop][3]
        db.execute(
            "UPDATE inventory SET seeds = seeds - ? WHERE user_id = ? AND crop_key = ?",
            (n, user_id, crop)
        )
        db.executemany(
            "INSERT INTO plots (user_id, crop_key, planted_at, ready_at) VALUES (?, ?, ?, ?)",
            [(user_id, crop, now, now + grow)] * n
        )
        planted_list.append((crop, n))
        total += n
        free -= n
    if total:
        db.commit()
    return total, planted_list


def format_time(seconds: float) -> str:
    if seconds <= 0:
        return "✅ Готово!"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins >= 60:
        return f"{mins // 60}ч {mins % 60}м"
    return f"{mins}м {secs}с"


def esc(text) -> str:
    """Экранируем имена игроков, чтобы <b> в имени не ломал сообщение."""
    return html.escape(str(text))


# ==================== ЗАЩИТА КНОПОК ====================
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


NOT_YOURS = "⛔ Это кнопки другого игрока. Открой /start у себя."


async def safe_edit(c: CallbackQuery, text: str, kb: InlineKeyboardMarkup = None):
    """edit_text, который не падает, если текст не изменился (например, «Обновить»)."""
    try:
        await c.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ==================== ЭКРАНЫ (текст + кнопки) ====================
SHOP_PER_PAGE = 10
SHOP_PAGES = (len(CROP_ORDER) + SHOP_PER_PAGE - 1) // SHOP_PER_PAGE


def amount_options(max_a: int) -> list:
    """Какие количества предложить: 1, 5, 10, 25 (сколько влезает) и «всё»."""
    opts = [a for a in (1, 5, 10, 25) if a <= max_a]
    if max_a > 1 and max_a not in opts:
        opts.append(max_a)
    return opts


def menu_view(uid: int):
    p = get_player(uid)
    ready = count_ready(uid)
    line = f"🌾 Грядок: {count_plots(uid)}/{p['plots_limit']}"
    if ready:
        line += f"  ·  🧺 готово: <b>{ready}</b>"
    return f"🏠 <b>Главное меню</b>\n{money(p['vaimiki'])}  ·  {line}", main_kb(uid)


def main_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    ready = count_ready(uid)
    harvest = f"🧺 Собрать ({ready})" if ready else "🌾 Ферма"
    b.row(
        InlineKeyboardButton(text=harvest, callback_data=own_cb("harvest" if ready else "farm", uid)),
        InlineKeyboardButton(text="🛒 Магазин", callback_data=own_cb("shop", uid)),
    )
    b.row(
        InlineKeyboardButton(text="🌱 Посадить", callback_data=own_cb("plant_menu", uid)),
        InlineKeyboardButton(text="👤 Профиль", callback_data=own_cb("profile", uid)),
    )
    b.row(
        InlineKeyboardButton(text="🏆 Топы", callback_data=own_cb("tops", uid)),
        InlineKeyboardButton(text="ℹ️ Помощь", callback_data=own_cb("help", uid)),
    )
    return b.as_markup()


def farm_kb(uid: int, ready: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🌱 Посадить", callback_data=own_cb("plant_menu", uid)),
        InlineKeyboardButton(
            text=f"🧺 Собрать ({ready})" if ready else "🧺 Собрать",
            callback_data=own_cb("harvest", uid)
        ),
    )
    b.row(
        InlineKeyboardButton(text="📐 Купить грядку", callback_data=own_cb("buy_plot", uid)),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=own_cb("farm", uid)),
    )
    b.row(
        InlineKeyboardButton(text="🛒 Магазин", callback_data=own_cb("shop", uid)),
        InlineKeyboardButton(text="◀️ Меню", callback_data=own_cb("menu", uid)),
    )
    return b.as_markup()


def farm_view(uid: int):
    p = get_player(uid)
    plots = get_plots(uid)
    limit = p["plots_limit"]
    now = time.time()
    lines = [f"🌾 <b>Твоя ферма</b>  ({len(plots)}/{limit} грядок)\n"]
    ready = 0
    if not plots:
        lines.append("Грядки пустые. Нажми «Посадить».")
    else:
        groups = {}  # культура -> [сколько, готово, сколько до ближайшей]
        for pl in plots:
            if pl["crop_key"] not in CROPS:
                continue
            g = groups.setdefault(pl["crop_key"], [0, 0, None])
            g[0] += 1
            left = pl["ready_at"] - now
            if left <= 0:
                g[1] += 1
                ready += 1
            elif g[2] is None or left < g[2]:
                g[2] = left
        keys = sorted(groups, key=CROP_ORDER.index)
        for key in keys[:30]:
            name, emoji, *_ = CROPS[key]
            n, rd, nxt = groups[key]
            if rd == n:
                status = "✅ готово"
            elif rd:
                status = f"✅ {rd} · ⏳ {format_time(nxt)}"
            else:
                status = f"⏳ {format_time(nxt)}"
            lines.append(f"{emoji} {name} ×{n} — {status}")
        if len(keys) > 30:
            lines.append(f"…и ещё {len(keys) - 30} культур")
        if ready:
            lines.append(f"\n🎉 Готово к сбору: <b>{ready}</b>")
    free = limit - len(plots)
    if free:
        lines.append(f"\nСвободных грядок: <b>{free}</b>")
    if limit < MAX_PLOTS_LIMIT:
        lines.append(f"След. грядка: {money(plot_price(limit))}")
    return "\n".join(lines), farm_kb(uid, ready)


def plant_menu_view(uid: int, page: int = 0):
    inv = get_inventory(uid)
    p = get_player(uid)
    free = p["plots_limit"] - count_plots(uid)
    keys = [k for k in CROP_ORDER if inv[k]["seeds"] > 0]
    per_page = 8
    pages = max(1, (len(keys) + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    text = f"🌱 <b>Посадка</b>\nСвободных грядок: <b>{free}</b>"
    if not keys:
        text += "\n\nСемян нет — купи их в магазине."
    b = InlineKeyboardBuilder()
    for key in keys[page * per_page:(page + 1) * per_page]:
        name, emoji, *_ = CROPS[key]
        b.row(InlineKeyboardButton(
            text=f"{emoji} {name} ×{inv[key]['seeds']}",
            callback_data=own_cb(f"pc:{key}", uid)
        ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=own_cb(f"plant_page:{page - 1}", uid)))
    if pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=own_cb("noop", uid)))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=own_cb(f"plant_page:{page + 1}", uid)))
    if nav:
        b.row(*nav)
    if not keys:
        b.row(InlineKeyboardButton(text="🛒 В магазин", callback_data=own_cb("shop", uid)))
    b.row(
        InlineKeyboardButton(text="◀️ Ферма", callback_data=own_cb("farm", uid)),
        InlineKeyboardButton(text="🛒 Магазин", callback_data=own_cb("shop", uid)),
    )
    return text, b.as_markup()


def plant_crop_view(uid: int, crop: str):
    """Экран «сколько посадить». Вернёт None, если сажать нечего или некуда."""
    inv = get_inventory(uid)
    free = get_player(uid)["plots_limit"] - count_plots(uid)
    seeds = inv[crop]["seeds"]
    max_can = min(seeds, free)
    if max_can <= 0:
        return None
    name, emoji, value, grow, ymin, ymax = CROPS[crop]
    text = (
        f"{emoji} <b>{name}</b>\n"
        f"{fmt_minutes(grow)} · {ymin}–{ymax} шт · семян {seeds} · грядок {free}\n\n"
        f"Сколько посадить?"
    )
    b = InlineKeyboardBuilder()
    opts = amount_options(max_can)
    for a in opts:
        label = f"Все ({a})" if (a == max_can and max_can > 1) else str(a)
        b.add(InlineKeyboardButton(text=label, callback_data=own_cb(f"dp:{crop}:{a}", uid)))
    b.adjust(4)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=own_cb("plant_menu", uid)))
    return text, b.as_markup()


def shop_default_page(coins: int) -> int:
    """Открываем магазин на странице с самой дорогой культурой, которую игрок уже может купить."""
    idx = 0
    for i, key in enumerate(CROP_ORDER):
        if seed_price(key) <= coins:
            idx = i
        else:
            break
    return idx // SHOP_PER_PAGE


def shop_view(uid: int, page: int, note: str = ""):
    page = max(0, min(page, SHOP_PAGES - 1))
    p = get_player(uid)
    coins = p["vaimiki"]
    start = page * SHOP_PER_PAGE
    end = min(start + SHOP_PER_PAGE, len(CROP_ORDER))
    text = (
        f"🛒 <b>Магазин</b> · {money(coins)}\n"
        f"{start + 1}–{end} из {len(CROP_ORDER)} · чем дальше, тем выгоднее · 🔒 не хватает"
    )
    if note:
        text += f"\n{note}"
    b = InlineKeyboardBuilder()
    for key in CROP_ORDER[start:end]:
        name, emoji, *_ = CROPS[key]
        price = seed_price(key)
        lock = "" if coins >= price else " 🔒"
        b.row(InlineKeyboardButton(
            text=f"{emoji} {name} — {fmt_num(price)}{lock}",
            callback_data=own_cb(f"bs:{key}", uid)
        ))
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⏮", callback_data=own_cb("sp:0", uid)))
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=own_cb(f"sp:{page - 1}", uid)))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{SHOP_PAGES}", callback_data=own_cb("noop", uid)))
    if page < SHOP_PAGES - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=own_cb(f"sp:{page + 1}", uid)))
    if page < SHOP_PAGES - 2:
        nav.append(InlineKeyboardButton(text="⏭", callback_data=own_cb(f"sp:{SHOP_PAGES - 1}", uid)))
    b.row(*nav)
    b.row(
        InlineKeyboardButton(text="📐 Купить грядку", callback_data=own_cb("buy_plot", uid)),
        InlineKeyboardButton(text="◀️ Меню", callback_data=own_cb("menu", uid)),
    )
    return text, b.as_markup()


def seed_view(uid: int, crop: str, note: str = ""):
    name, emoji, value, grow, ymin, ymax = CROPS[crop]
    idx = CROP_ORDER.index(crop)
    p = get_player(uid)
    seeds = get_inventory(uid)[crop]["seeds"]
    price = seed_price(crop)
    can = min(p["vaimiki"] // price, 1000)
    lines = [f"{emoji} <b>{name}</b> — №{idx + 1} из {len(CROP_ORDER)}"]
    if note:
        lines.append(note)
    lines += [
        f"Семя <b>{money(price)}</b> · у тебя {money(p['vaimiki'])}",
        f"{fmt_minutes(grow)} · {ymin}–{ymax} шт · плод ≈ {money(value)} · ~{fmt_weight(BASE_WEIGHT[crop])}",
        f"С грядки ≈ {money(round(value * (ymin + ymax) / 2))} + бонусы веса и мутаций",
    ]
    if can < 1:
        lines.append(f"\nНе хватает {money(price - p['vaimiki'])}")
    else:
        lines.append("\nСколько купить?")
    b = InlineKeyboardBuilder()
    for a in amount_options(can):
        label = f"Макс ({a})" if (a == can and can > 1) else str(a)
        b.add(InlineKeyboardButton(text=label, callback_data=own_cb(f"db:{crop}:{a}", uid)))
    b.adjust(4)
    if seeds > 0:
        b.row(InlineKeyboardButton(text=f"🌱 Посадить (семян: {seeds})", callback_data=own_cb(f"pc:{crop}", uid)))
    b.row(InlineKeyboardButton(text="◀️ К списку", callback_data=own_cb(f"sp:{idx // SHOP_PER_PAGE}", uid)))
    return "\n".join(lines), b.as_markup()


def tops_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="💎 Топ Ваймиков", callback_data=own_cb("top:vaimiki", uid)),
        InlineKeyboardButton(text="⚖️ Тяжелейшие", callback_data=own_cb("top:heavy", uid)),
    )
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
    b.row(
        InlineKeyboardButton(text="🥜 Арахис", callback_data=own_cb("top:peanut", uid)),
        InlineKeyboardButton(text="🌰 Миндаль", callback_data=own_cb("top:almond", uid)),
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


# ==================== ТЕКСТЫ ====================
def help_text() -> str:
    muts = "\n".join(
        f"{emoji} {name} ×{mult} — {chance:g}%"
        for name, emoji, mult, chance in sorted(MUTATIONS.values(), key=lambda m: -m[3])
    )
    return (
        f"ℹ️ <b>Как играть</b>\n\n"
        f"Купи семена 🛒 → посади 🌱 → собери 🧺 → получи {CURRENCY}.\nВ чате можно писать <b>Сбор</b> и <b>Посадить</b>.\n"
        f"Магазин идёт от дешёвого к дорогому: дальше — дороже семена и дольше рост, "
        f"зато урожай выгоднее.\n\n"
        f"⚖️ Чем тяжелее плод, тем он дороже (бывают гиганты до ×3).\n\n"
        f"🧬 <b>Мутации</b> (×к цене · шанс):\n{muts}\n\n"
        f"Грядок: {START_PLOTS} в начале, максимум {MAX_PLOTS_LIMIT} · культур: {len(CROPS)}"
    )


def harvest_report(res: dict) -> str:
    lines = ["🧺 <b>Урожай собран!</b>\n"]
    crops = sorted(res["crops"].items(), key=lambda kv: -kv[1]["coins"])
    for key, d in crops[:12]:
        name, emoji, *_ = CROPS[key]
        lines.append(f"{emoji} {name}: +{d['amt']} (+{money(d['coins'])})")
    if len(crops) > 12:
        lines.append(f"…и ещё {len(crops) - 12} культур")
    if res["muts"]:
        order = sorted(res["muts"].items(), key=lambda kv: -MUTATIONS[kv[0]][2])
        lines.append("\n🧬 Мутации: " + "  ".join(f"{MUTATIONS[m][1]}×{n}" for m, n in order))
    if res["best"]:
        lines.append("\n🏅 <b>Лучшие плоды:</b>")
        for val, key, weight, mut in res["best"]:
            name, emoji, *_ = CROPS[key]
            mtxt = ""
            if mut:
                m_name, m_emoji, m_mult, _chance = MUTATIONS[mut]
                mtxt = f" {m_emoji} {m_name} ×{m_mult}"
            lines.append(f"{emoji} {name}{mtxt} — {fmt_weight(weight)} → {money(max(1, round(val)))}")
    lines.append(f"\n💰 +{fmt_num(res['total'])} {CURRENCY}")
    return "\n".join(lines)


# ==================== КОМАНДЫ ====================


def all_broadcast_chats() -> list:
    chats = set()
    try:
        for (cid,) in db.execute("SELECT DISTINCT chat_id FROM user_chats"):
            chats.add(int(cid))
    except sqlite3.OperationalError:
        pass
    try:
        for (uid,) in db.execute("SELECT user_id FROM players"):
            chats.add(int(uid))
    except sqlite3.OperationalError:
        pass
    return sorted(chats)


async def send_broadcast(bot: Bot, text: str) -> tuple:
    """Шлёт text во все известные чаты. Возвращает (ok, fail)."""
    ok = fail = 0
    for chat_id in all_broadcast_chats():
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    return ok, fail


def top_vaimiki_text(limit: int = 10) -> str:
    """Текст топа по Ваймикам."""
    rows = db.execute(
        "SELECT name, vaimiki FROM players ORDER BY vaimiki DESC LIMIT ?", (limit,)
    ).fetchall()
    lines = [f"💎 <b>Топ по {CURRENCY}</b>"]
    if not rows:
        lines.append("Пока пусто")
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{medal} {esc(r['name'])}: <b>{fmt_num(r['vaimiki'])}</b> {CURRENCY_EMOJI}")
    return "\n".join(lines)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    text, kb = menu_view(message.from_user.id)
    await message.answer(
        f"🌾 <b>Ферма Ваймиков</b>\n"
        f"Сажай, собирай, зарабатывай {CURRENCY_EMOJI}. Плоды бывают тяжёлыми и мутировавшими ✨\n\n" + text,
        reply_markup=kb,
        parse_mode="HTML"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(help_text(), reply_markup=back_menu_kb(message.from_user.id), parse_mode="HTML")


@dp.message(Command("farm"))
async def cmd_farm(message: Message):
    text, kb = farm_view(message.from_user.id)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.message(Command("shop"))
async def cmd_shop(message: Message):
    uid = message.from_user.id
    text, kb = shop_view(uid, shop_default_page(get_player(uid)["vaimiki"]))
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    await show_profile(message, message.from_user)


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    players = db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    planted = db.execute("SELECT COUNT(*) FROM plots").fetchone()[0]
    size_kb = os.path.getsize(DB_PATH) / 1024
    await message.answer(
        f"📊 Игроков в базе: <b>{players}</b>\n🌱 Грядок посажено: {planted}\n💾 Файл базы: {size_kb:.0f} КБ",
        parse_mode="HTML"
    )



@dp.message(Command("broadcast", "say"))
async def cmd_broadcast(message: Message):
    await message.reply(
        "Используй админ-панель:\n<code>/stm пароль</code> → 📢 Рассылка",
        parse_mode="HTML",
    )


@dp.message(Command("top"))
async def cmd_top(message: Message):
    await message.answer(
        top_vaimiki_text(),
        reply_markup=tops_kb(message.from_user.id),
        parse_mode="HTML",
    )


@dp.message(Command("vaimiki"))
async def cmd_top_vaimiki(message: Message):
    await message.reply(top_vaimiki_text(), parse_mode="HTML")


@dp.message(lambda m: bool(m.text) and m.text.strip().casefold() in {
    "топ", "топ ваймики", "топ ваймиков", "ваймики топ", "top", "top vaimiki"
})
async def msg_top_vaimiki(message: Message):
    await message.reply(top_vaimiki_text(), parse_mode="HTML")


# ==================== ПРОФИЛЬ ====================
async def show_profile(target, user, edit: bool = False):
    p = get_player(user.id)
    inv = get_inventory(user.id)
    lines = [
        f"👤 <b>{esc(user.full_name)}</b>",
        f"{CURRENCY_EMOJI} {CURRENCY}: <b>{fmt_num(p['vaimiki'])}</b>",
        f"Грядок: <b>{p['plots_limit']}</b>/{MAX_PLOTS_LIMIT}",
    ]
    heavy = max(inv.items(), key=lambda kv: kv[1]["best_weight"])
    if heavy[1]["best_weight"] > 0:
        name, emoji, *_ = CROPS[heavy[0]]
        lines.append(f"⚖️ Рекорд веса: {emoji} {name} — {fmt_weight(heavy[1]['best_weight'])}")
    rows = db.execute(
        "SELECT mutation_key, count FROM mutation_log WHERE user_id = ? AND count > 0", (user.id,)
    ).fetchall()
    rows = [r for r in rows if r["mutation_key"] in MUTATIONS]
    if rows:
        rows.sort(key=lambda r: -MUTATIONS[r["mutation_key"]][2])
        lines.append("🧬 Мутации: " + "  ".join(f"{MUTATIONS[r['mutation_key']][1]} {r['count']}" for r in rows))
    lines += ["", "📦 Собрано (топ):"]
    # показываем только то, что есть
    items = [(k, v) for k, v in inv.items() if v["harvested"] > 0 or v["seeds"] > 0]
    items.sort(key=lambda x: -x[1]["harvested"])
    for key, d in items[:12]:
        name, emoji, *_ = CROPS[key]
        lines.append(f"{emoji} {name}: семян {d['seeds']} | собрано {d['harvested']}")
    if not items:
        lines.append("Пока пусто")
    text = "\n".join(lines)
    if edit and hasattr(target, "message"):
        await safe_edit(target, text, back_menu_kb(user.id))
    else:
        await target.answer(text, reply_markup=back_menu_kb(user.id), parse_mode="HTML")


# ==================== CALLBACKS ====================
@dp.callback_query(F.data.startswith("noop"))
async def cb_noop(c: CallbackQuery):
    await c.answer()


@dp.callback_query(F.data.startswith("menu"))
async def cb_menu(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    text, kb = menu_view(c.from_user.id)
    await safe_edit(c, text, kb)
    await c.answer()


@dp.callback_query(F.data.startswith("farm"))
async def cb_farm(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    text, kb = farm_view(c.from_user.id)
    await safe_edit(c, text, kb)
    await c.answer()


@dp.callback_query(F.data.startswith("profile"))
async def cb_profile(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    await show_profile(c, c.from_user, edit=True)
    await c.answer()


@dp.callback_query(F.data.startswith("help"))
async def cb_help(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    await safe_edit(c, help_text(), back_menu_kb(c.from_user.id))
    await c.answer()


@dp.callback_query(F.data.startswith("buy_plot"))
async def cb_buy_plot(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    p = get_player(c.from_user.id)
    limit = p["plots_limit"]
    if limit >= MAX_PLOTS_LIMIT:
        await c.answer("Уже максимум грядок!", show_alert=True)
        return
    price = plot_price(limit)
    if p["vaimiki"] < price:
        await c.answer(f"Нужно {fmt_num(price)} {CURRENCY_EMOJI}, у тебя {fmt_num(p['vaimiki'])}", show_alert=True)
        return
    db.execute(
        "UPDATE players SET vaimiki = vaimiki - ?, plots_limit = plots_limit + 1 WHERE user_id = ?",
        (price, c.from_user.id)
    )
    db.commit()
    await c.answer(f"Грядка куплена! Теперь {limit + 1}", show_alert=True)
    text, kb = farm_view(c.from_user.id)
    await safe_edit(c, text, kb)


@dp.callback_query(F.data.startswith("plant_menu"))
@dp.callback_query(F.data.startswith("plant_page:"))
async def cb_plant_menu(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    page = 0
    if payload.startswith("plant_page:"):
        page = int(payload.split(":")[1])
    text, kb = plant_menu_view(c.from_user.id, page)
    await safe_edit(c, text, kb)
    await c.answer()


@dp.callback_query(F.data.startswith("pc:"))
async def cb_plant_crop(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    crop = payload.split(":")[1]
    if crop not in CROPS:
        await c.answer("Нет такой культуры", show_alert=True)
        return
    view = plant_crop_view(c.from_user.id, crop)
    if view is None:
        await c.answer("Нет семян или свободных грядок!", show_alert=True)
        return
    await safe_edit(c, *view)
    await c.answer()


@dp.callback_query(F.data.startswith("dp:"))
async def cb_do_plant(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    _, crop, amount_s = payload.split(":")
    amount = int(amount_s)
    if crop not in CROPS or amount < 1:
        await c.answer("Нельзя посадить", show_alert=True)
        return
    uid = c.from_user.id
    inv = get_inventory(uid)
    free = get_player(uid)["plots_limit"] - count_plots(uid)
    if inv[crop]["seeds"] < amount or amount > free:
        await c.answer("Нельзя посадить столько", show_alert=True)
        return
    grow = CROPS[crop][3]
    now = time.time()
    db.execute(
        "UPDATE inventory SET seeds = seeds - ? WHERE user_id = ? AND crop_key = ?",
        (amount, uid, crop)
    )
    db.executemany(
        "INSERT INTO plots (user_id, crop_key, planted_at, ready_at) VALUES (?, ?, ?, ?)",
        [(uid, crop, now, now + grow)] * amount
    )
    db.commit()
    name, emoji, *_ = CROPS[crop]
    await c.answer(f"Посажено {amount} × {emoji} {name}!", show_alert=True)
    text, kb = farm_view(uid)
    await safe_edit(c, text, kb)


@dp.callback_query(F.data.startswith("harvest"))
async def cb_harvest(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    uid = c.from_user.id
    res = do_collect(uid)
    if res is None:
        await c.answer("Ещё нечего собирать 🌱", show_alert=True)
        return
    await safe_edit(c, harvest_report(res), farm_kb(uid, count_ready(uid)))
    await c.answer("Готово!")



@dp.message(Command("collect"))
async def cmd_collect(message: Message):
    uid = message.from_user.id
    res = do_collect(uid)
    if res is None:
        await message.reply("🌱 Пока нечего собирать — урожай ещё растёт.")
        return
    await message.reply(harvest_report(res), parse_mode="HTML")


@dp.message(Command("plant"))
async def cmd_plant(message: Message):
    uid = message.from_user.id
    total, planted = do_auto_plant(uid)
    if total == 0:
        free = get_player(uid)["plots_limit"] - count_plots(uid)
        if free <= 0:
            await message.reply("Нет свободных грядок. Купи ещё: /farm")
        else:
            await message.reply("Нет семян. Купи в магазине: /shop")
        return
    lines = [f"🌱 <b>Посажено: {total}</b>"]
    for crop, n in planted:
        name, emoji, *_ = CROPS[crop]
        lines.append(f"{emoji} {name}: ×{n}")
    free = get_player(uid)["plots_limit"] - count_plots(uid)
    lines.append("")
    lines.append(f"Свободно грядок: {free}")
    await message.reply("\n".join(lines), parse_mode="HTML")

# --- текстовые команды: «Сбор» / «Посадить» ---
@dp.message(lambda m: bool(m.text) and m.text.strip().casefold() in {
    "сбор", "собрать", "собрать урожай", "collect", "/collect"
})
async def msg_collect(message: Message):
    uid = message.from_user.id
    res = do_collect(uid)
    if res is None:
        await message.reply("🌱 Пока нечего собирать — урожай ещё растёт.")
        return
    await message.reply(harvest_report(res), parse_mode="HTML")


@dp.message(lambda m: bool(m.text) and m.text.strip().casefold() in {
    "посадить", "посади", "сажать", "plant", "/plant"
})
async def msg_plant(message: Message):
    uid = message.from_user.id
    total, planted = do_auto_plant(uid)
    if total == 0:
        free = get_player(uid)["plots_limit"] - count_plots(uid)
        if free <= 0:
            await message.reply("Нет свободных грядок. Купи ещё: /farm → 📐")
        else:
            await message.reply("Нет семян. Купи в магазине: /shop")
        return
    lines = [f"🌱 <b>Посажено: {total}</b>"]
    for crop, n in planted:
        name, emoji, *_ = CROPS[crop]
        lines.append(f"{emoji} {name}: ×{n}")
    free = get_player(uid)["plots_limit"] - count_plots(uid)
    lines.append("")
    lines.append(f"Свободно грядок: {free}")
    await message.reply("\n".join(lines), parse_mode="HTML")


@dp.callback_query(F.data.startswith("shop"))
async def cb_shop(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    uid = c.from_user.id
    text, kb = shop_view(uid, shop_default_page(get_player(uid)["vaimiki"]))
    await safe_edit(c, text, kb)
    await c.answer()


@dp.callback_query(F.data.startswith("sp:"))
async def cb_shop_page(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    text, kb = shop_view(c.from_user.id, int(payload.split(":")[1]))
    await safe_edit(c, text, kb)
    await c.answer()


@dp.callback_query(F.data.startswith("bs:"))
async def cb_buy_seed(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    crop = payload.split(":")[1]
    if crop not in CROPS:
        await c.answer("Нет такой культуры", show_alert=True)
        return
    await safe_edit(c, *seed_view(c.from_user.id, crop))
    await c.answer()


@dp.callback_query(F.data.startswith("db:"))
async def cb_do_buy(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    _, crop, amount_s = payload.split(":")
    amount = int(amount_s)
    if crop not in CROPS or amount < 1:
        await c.answer("Нельзя купить", show_alert=True)
        return
    uid = c.from_user.id
    cost = seed_price(crop) * amount
    p = get_player(uid)
    if p["vaimiki"] < cost:
        await c.answer("Недостаточно Ваймиков!", show_alert=True)
        return
    db.execute("UPDATE players SET vaimiki = vaimiki - ? WHERE user_id = ?", (cost, uid))
    db.execute(
        "INSERT OR IGNORE INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, 0, 0)",
        (uid, crop)
    )
    db.execute(
        "UPDATE inventory SET seeds = seeds + ? WHERE user_id = ? AND crop_key = ?",
        (amount, uid, crop)
    )
    db.commit()
    name, emoji, *_ = CROPS[crop]
    await c.answer(f"+{amount} {emoji} {name} за {fmt_num(cost)}!")
    # остаёмся на экране семени: можно докупить ещё или сразу посадить
    await safe_edit(c, *seed_view(uid, crop, note=f"✅ Куплено: {amount} шт за {money(cost)}"))


@dp.callback_query(F.data.startswith("tops"))
async def cb_tops(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    await safe_edit(c, "🏆 <b>Топы</b>", tops_kb(c.from_user.id))
    await c.answer()


@dp.callback_query(F.data.startswith("top:"))
async def cb_top(c: CallbackQuery):
    payload, ok = parse_own(c)
    if not ok:
        await c.answer(NOT_YOURS, show_alert=True)
        return
    key = payload.split(":")[1]
    medals = ["🥇", "🥈", "🥉"]
    if key == "vaimiki":
        lines = top_vaimiki_text().split("\n")
    elif key == "heavy":
        rows = db.execute("""
            SELECT p.name, i.crop_key, i.best_weight
            FROM inventory i JOIN players p ON p.user_id = i.user_id
            WHERE i.best_weight > 0
            ORDER BY i.best_weight DESC LIMIT 10
        """).fetchall()
        lines = ["⚖️ <b>Самые тяжёлые плоды</b>\n"]
        if not rows:
            lines.append("Пока пусто")
        for i, r in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i + 1}."
            if r["crop_key"] not in CROPS:
                continue
            name, emoji, *_ = CROPS[r["crop_key"]]
            lines.append(f"{medal} {esc(r['name'])}: {emoji} {name} — <b>{fmt_weight(r['best_weight'])}</b>")
    else:
        if key not in CROPS:
            await c.answer("Нет", show_alert=True)
            return
        name, emoji, *_ = CROPS[key]
        rows = db.execute("""
            SELECT p.name, i.harvested
            FROM inventory i JOIN players p ON p.user_id = i.user_id
            WHERE i.crop_key = ? AND i.harvested > 0
            ORDER BY i.harvested DESC LIMIT 10
        """, (key,)).fetchall()
        lines = [f"{emoji} <b>Топ по {name}</b>\n"]
        if not rows:
            lines.append("Пока пусто")
        for i, r in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{medal} {esc(r['name'])}: <b>{fmt_num(r['harvested'])}</b> шт")
    await safe_edit(c, "\n".join(lines), back_tops_kb(c.from_user.id))
    await c.answer()



# ==================== УВЕДОМЛЕНИЯ О СОЗРЕВАНИИ ====================
NOTIFY_INTERVAL = 45  # секунд между проверками


async def growth_notifier(bot: Bot):
    """Раз в NOTIFY_INTERVAL смотрит готовые грядки и пишет в чаты игрока."""
    while True:
        try:
            await asyncio.sleep(NOTIFY_INTERVAL)
            # Файл-рассылка: положи /app/data/broadcast.txt — бот разошлёт и переименует файл
            bcast = os.path.join(DATA_DIR, "broadcast.txt")
            if os.path.isfile(bcast):
                try:
                    with open(bcast, encoding="utf-8") as f:
                        body = f.read().strip()
                    if body:
                        ok, fail = await send_broadcast(bot, body)
                        logging.info("broadcast.txt: ok=%s fail=%s", ok, fail)
                    os.replace(bcast, bcast + ".done")
                except Exception:
                    logging.exception("broadcast.txt")
            now = time.time()
            crop_keys = list(CROPS.keys())
            placeholders = ",".join("?" * len(crop_keys))
            rows = db.execute(
                f"""
                SELECT p.id, p.user_id, p.crop_key
                FROM plots p
                LEFT JOIN ready_notified n ON n.plot_id = p.id
                WHERE p.ready_at <= ? AND n.plot_id IS NULL
                  AND p.crop_key IN ({placeholders})
                """,
                (now, *crop_keys),
            ).fetchall()
            if not rows:
                continue
            by_user = {}
            for r in rows:
                by_user.setdefault(r["user_id"], []).append(r)
            for user_id, plots in by_user.items():
                counts = {}
                for pl in plots:
                    counts[pl["crop_key"]] = counts.get(pl["crop_key"], 0) + 1
                parts = []
                for key, n in counts.items():
                    name, emoji, *_ = CROPS[key]
                    parts.append(f"{emoji} {name} ×{n}")
                text_msg = (
                    "🌾 <b>Урожай созрел!</b>\n"
                    + ", ".join(parts)
                    + "\n\nНапиши <b>Сбор</b> или нажми 🧺 на ферме."
                )
                chats = db.execute(
                    "SELECT chat_id FROM user_chats WHERE user_id = ?", (user_id,)
                ).fetchall()
                if not chats:
                    chats = [{"chat_id": user_id}]
                for ch in chats:
                    try:
                        await bot.send_message(ch["chat_id"], text_msg, parse_mode="HTML")
                    except Exception:
                        pass
                db.executemany(
                    "INSERT OR IGNORE INTO ready_notified (plot_id) VALUES (?)",
                    [(pl["id"],) for pl in plots],
                )
                db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("growth_notifier")


# ==================== АДМИН-ПАНЕЛЬ (отдельный файл) ====================
try:
    from admin_panel import router as admin_router, setup_admin
    setup_admin(
        db=db,
        crops=CROPS,
        crop_order=CROP_ORDER,
        currency=CURRENCY,
        currency_emoji=CURRENCY_EMOJI,
        fmt_num=fmt_num,
        seed_price=seed_price,
        send_broadcast=send_broadcast,
        all_chats=all_broadcast_chats,
    )
    dp.include_router(admin_router)
except Exception:
    logging.exception("Админ-панель не подключена")

# ==================== ОШИБКИ ====================
@dp.error()
async def on_error(event):
    """Любая ошибка в обработчике: пишем в лог и снимаем «часики» с кнопки, чтобы бот не казался зависшим."""
    logging.exception("Ошибка в обработчике: %s", event.exception)
    cq = event.update.callback_query
    if cq is not None:
        try:
            await cq.answer("⚠️ Что-то пошло не так, попробуй ещё раз")
        except Exception:
            pass
    return True


# ==================== ЗАПУСК ====================
async def main():
    if not TOKEN:
        raise SystemExit("Нет токена: задай переменную окружения BOT_TOKEN (или положи его в token.txt)")

    logging.basicConfig(level=logging.INFO)
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    cmds = [
        BotCommand(command="start", description="🌱 Старт / меню"),
        BotCommand(command="farm", description="🌾 Ферма"),
        BotCommand(command="shop", description="🛒 Магазин"),
        BotCommand(command="balance", description="👤 Профиль"),
        BotCommand(command="top", description="🏆 Топы"),
        BotCommand(command="help", description="ℹ️ Помощь"),
        BotCommand(command="collect", description="🧺 Сбор урожая"),
        BotCommand(command="plant", description="🌱 Посадить семена"),
        BotCommand(command="vaimiki", description="💎 Топ Ваймиков"),
    ]
    await bot.set_my_commands(cmds, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(cmds, scope=BotCommandScopeAllGroupChats())

    print(f"🚀 Бот запущен! База: {DB_PATH}")
    await bot.delete_webhook(drop_pending_updates=True)   # не разбирать нажатия, накопившиеся пока бот спал
    asyncio.create_task(growth_notifier(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
