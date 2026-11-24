import asyncio
import logging
import time
import os
from random import randint
from typing import Optional, List, Dict, Any

import aiosqlite
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================== НАСТРОЙКИ ====================
# Вставь токен сюда ИЛИ создай файл .env с BOT_TOKEN=...
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА")

CURRENCY = "Ваймики"
CURRENCY_EMOJI = "💎"
MAX_PLOTS = 5
START_VAIMIKI = 20

# key: (название, эмодзи, цена за 1 шт, время роста сек, мин урожай, макс урожай)
CROPS = {
    "carrot":  ("Морковь",  "🥕", 1, 30 * 60,  8, 12),
    "beet":    ("Свёкла",   "🟣", 2, 45 * 60,  6, 10),
    "potato":  ("Картошка", "🥔", 3, 60 * 60,  5,  9),
    "tomato":  ("Помидор",  "🍅", 4, 40 * 60,  7, 11),
    "cabbage": ("Капуста",  "🥬", 2, 50 * 60,  6, 10),
    "corn":    ("Кукуруза", "🌽", 5, 90 * 60,  4,  8),
}

START_SEEDS = {"carrot": 3, "beet": 1}
DB_PATH = "farm.db"

# ==================== БАЗА ДАННЫХ ====================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                vaimiki INTEGER DEFAULT 0,
                created_at REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER,
                crop_key TEXT,
                seeds INTEGER DEFAULT 0,
                harvested INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, crop_key)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS plots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                crop_key TEXT,
                amount INTEGER,
                planted_at REAL,
                ready_at REAL
            )
        """)
        await db.commit()


async def ensure_user(user_id: int, username: str = None, full_name: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO users (user_id, username, full_name, vaimiki, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, username or "", full_name or "", START_VAIMIKI, time.time())
            )
            for crop, amount in START_SEEDS.items():
                await db.execute(
                    "INSERT INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, ?, 0)",
                    (user_id, crop, amount)
                )
            for crop in CROPS:
                if crop not in START_SEEDS:
                    await db.execute(
                        "INSERT INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, 0, 0)",
                        (user_id, crop)
                    )
            await db.commit()
        else:
            await db.execute(
                "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                (username or "", full_name or "", user_id)
            )
            await db.commit()


async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_inventory(user_id: int) -> Dict[str, Dict[str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT crop_key, seeds, harvested FROM inventory WHERE user_id = ?", (user_id,)
        )
        rows = await cursor.fetchall()
        result = {crop: {"seeds": 0, "harvested": 0} for crop in CROPS}
        for row in rows:
            result[row["crop_key"]] = {"seeds": row["seeds"], "harvested": row["harvested"]}
        return result


async def get_plots(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM plots WHERE user_id = ? ORDER BY planted_at", (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def count_active_plots(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM plots WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def plant(user_id: int, crop_key: str, amount: int) -> bool:
    if crop_key not in CROPS:
        return False
    inv = await get_inventory(user_id)
    if inv[crop_key]["seeds"] < amount:
        return False
    if await count_active_plots(user_id) + amount > MAX_PLOTS:
        return False

    _, _, _, grow_time, _, _ = CROPS[crop_key]
    now = time.time()
    ready = now + grow_time

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE inventory SET seeds = seeds - ? WHERE user_id = ? AND crop_key = ?",
            (amount, user_id, crop_key)
        )
        for _ in range(amount):
            await db.execute(
                "INSERT INTO plots (user_id, crop_key, amount, planted_at, ready_at) VALUES (?, ?, 1, ?, ?)",
                (user_id, crop_key, now, ready)
            )
        await db.commit()
    return True


async def harvest_all(user_id: int) -> Dict[str, Any]:
    now = time.time()
    plots = await get_plots(user_id)
    ready_plots = [p for p in plots if p["ready_at"] <= now]

    if not ready_plots:
        return {"harvested": {}, "vaimiki_gained": 0, "total_crops": 0}

    harvested = {}
    total_vaimiki = 0
    total_crops = 0
    ids_to_delete = []

    for p in ready_plots:
        crop = p["crop_key"]
        _, _, value, _, ymin, ymax = CROPS[crop]
        amount = randint(ymin, ymax)
        harvested[crop] = harvested.get(crop, 0) + amount
        total_vaimiki += amount * value
        total_crops += amount
        ids_to_delete.append(p["id"])

    async with aiosqlite.connect(DB_PATH) as db:
        for pid in ids_to_delete:
            await db.execute("DELETE FROM plots WHERE id = ?", (pid,))
        for crop, amount in harvested.items():
            await db.execute(
                "UPDATE inventory SET harvested = harvested + ? WHERE user_id = ? AND crop_key = ?",
                (amount, user_id, crop)
            )
        await db.execute(
            "UPDATE users SET vaimiki = vaimiki + ? WHERE user_id = ?",
            (total_vaimiki, user_id)
        )
        await db.commit()

    return {"harvested": harvested, "vaimiki_gained": total_vaimiki, "total_crops": total_crops}


async def buy_seeds(user_id: int, crop_key: str, amount: int) -> bool:
    if crop_key not in CROPS:
        return False
    _, _, value, *_ = CROPS[crop_key]
    cost = value * 2 * amount
    user = await get_user(user_id)
    if not user or user["vaimiki"] < cost:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET vaimiki = vaimiki - ? WHERE user_id = ?",
            (cost, user_id)
        )
        await db.execute(
            "INSERT OR IGNORE INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, 0, 0)",
            (user_id, crop_key)
        )
        await db.execute(
            "UPDATE inventory SET seeds = seeds + ? WHERE user_id = ? AND crop_key = ?",
            (amount, user_id, crop_key)
        )
        await db.commit()
    return True


async def get_top_vaimiki(limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, username, full_name, vaimiki FROM users ORDER BY vaimiki DESC LIMIT ?",
            (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_top_crop(crop_key: str, limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT u.user_id, u.username, u.full_name, i.harvested
            FROM inventory i
            JOIN users u ON u.user_id = i.user_id
            WHERE i.crop_key = ?
            ORDER BY i.harvested DESC
            LIMIT ?
        """, (crop_key, limit))
        return [dict(r) for r in await cursor.fetchall()]


# ==================== КЛАВИАТУРЫ ====================
def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🌾 Моя ферма", callback_data="farm"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
    )
    b.row(
        InlineKeyboardButton(text="🛒 Магазин семян", callback_data="shop"),
        InlineKeyboardButton(text="🏆 Топы", callback_data="tops"),
    )
    b.row(InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"))
    return b.as_markup()


def farm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🌱 Посадить", callback_data="plant_menu"),
        InlineKeyboardButton(text="🧺 Собрать урожай", callback_data="harvest"),
    )
    b.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="farm"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
    )
    return b.as_markup()


def plant_menu_kb(inventory: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, (name, emoji, *_) in CROPS.items():
        seeds = inventory.get(key, {}).get("seeds", 0)
        b.row(InlineKeyboardButton(
            text=f"{emoji} {name} (семян: {seeds})",
            callback_data=f"plant_crop:{key}"
        ))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="farm"))
    return b.as_markup()


def plant_amount_kb(crop_key: str, max_amount: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    row = []
    for a in [1, 2, 3, 5]:
        if a <= max_amount:
            row.append(InlineKeyboardButton(text=str(a), callback_data=f"do_plant:{crop_key}:{a}"))
    if row:
        b.row(*row)
    if max_amount > 5:
        b.row(InlineKeyboardButton(text=f"Все ({max_amount})", callback_data=f"do_plant:{crop_key}:{max_amount}"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="plant_menu"))
    return b.as_markup()


def shop_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, (name, emoji, value, *_) in CROPS.items():
        price = value * 2
        b.row(InlineKeyboardButton(
            text=f"{emoji} {name} — {price} {CURRENCY_EMOJI} / шт",
            callback_data=f"buy_seed:{key}"
        ))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return b.as_markup()


def buy_amount_kb(crop_key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for a in [1, 3, 5, 10]:
        b.add(InlineKeyboardButton(text=str(a), callback_data=f"do_buy:{crop_key}:{a}"))
    b.adjust(4)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="shop"))
    return b.as_markup()


def tops_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💎 Топ по Ваймикам", callback_data="top:vaimiki"))
    b.row(
        InlineKeyboardButton(text="🥕 Морковь", callback_data="top:carrot"),
        InlineKeyboardButton(text="🟣 Свёкла", callback_data="top:beet"),
    )
    b.row(
        InlineKeyboardButton(text="🥔 Картошка", callback_data="top:potato"),
        InlineKeyboardButton(text="🍅 Помидор", callback_data="top:tomato"),
    )
    b.row(
        InlineKeyboardButton(text="🥬 Капуста", callback_data="top:cabbage"),
        InlineKeyboardButton(text="🌽 Кукуруза", callback_data="top:corn"),
    )
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return b.as_markup()


def back_to_tops_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ К топам", callback_data="tops"))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return b.as_markup()


def back_main_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return b.as_markup()


def format_time_left(seconds: float) -> str:
    if seconds <= 0:
        return "✅ Готово!"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins >= 60:
        hours = mins // 60
        mins = mins % 60
        return f"{hours}ч {mins}м"
    return f"{mins}м {secs}с"


# ==================== ХЕНДЛЕРЫ ====================
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await ensure_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = (
        f"🌾 <b>Добро пожаловать на Ферму Ваймиков!</b>\n\n"
        f"Здесь ты выращиваешь овощи и зарабатываешь {CURRENCY_EMOJI} <b>{CURRENCY}</b>.\n\n"
        f"• Сажай семена\n"
        f"• Жди пока вырастут\n"
        f"• Собирай урожай и получай {CURRENCY}\n"
        f"• Соревнуйся в топах!\n\n"
        f"Нажми кнопку ниже 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыбери действие:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    inv = await get_inventory(callback.from_user.id)
    lines = [
        f"👤 <b>Профиль</b>",
        f"Имя: {callback.from_user.full_name}",
        f"{CURRENCY_EMOJI} {CURRENCY}: <b>{user['vaimiki']}</b>",
        "",
        "📦 <b>Инвентарь:</b>"
    ]
    for key, (name, emoji, *_) in CROPS.items():
        data = inv.get(key, {"seeds": 0, "harvested": 0})
        lines.append(f"{emoji} {name}: семян {data['seeds']} | собрано {data['harvested']}")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_main_kb())
    await callback.answer()


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    text = (
        f"ℹ️ <b>Как играть</b>\n\n"
        f"1. Зайди в <b>Магазин семян</b> и купи семена.\n"
        f"2. Перейди в <b>Моя ферма</b> → Посадить.\n"
        f"3. Выбери культуру и количество.\n"
        f"4. Жди (время роста у каждой культуры своё).\n"
        f"5. Нажми <b>Собрать урожай</b> — получишь овощи + {CURRENCY}!\n\n"
        f"<b>Цены за 1 единицу урожая:</b>\n"
    )
    for key, (name, emoji, value, grow_sec, ymin, ymax) in CROPS.items():
        mins = grow_sec // 60
        text += f"{emoji} {name}: {value} {CURRENCY_EMOJI} | рост {mins} мин | урожай {ymin}–{ymax}\n"
    text += f"\nМаксимум {MAX_PLOTS} активных грядок.\nСемена стоят в 2 раза дороже — выгода в количестве!"
    await callback.message.edit_text(text, reply_markup=back_main_kb())
    await callback.answer()


@router.callback_query(F.data == "farm")
async def cb_farm(callback: CallbackQuery):
    await ensure_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    plots = await get_plots(callback.from_user.id)
    now = time.time()
    lines = [f"🌾 <b>Твоя ферма</b>\n"]
    if not plots:
        lines.append("Грядки пустые. Посади что-нибудь!")
    else:
        ready_count = 0
        for i, p in enumerate(plots, 1):
            name, emoji, *_ = CROPS[p["crop_key"]]
            left = p["ready_at"] - now
            status = format_time_left(left)
            if left <= 0:
                ready_count += 1
            lines.append(f"{i}. {emoji} {name} — {status}")
        lines.append(f"\nАктивных грядок: {len(plots)}/{MAX_PLOTS}")
        if ready_count:
            lines.append(f"🎉 Готово к сбору: <b>{ready_count}</b>")
    await callback.message.edit_text("\n".join(lines), reply_markup=farm_kb())
    await callback.answer()


@router.callback_query(F.data == "plant_menu")
async def cb_plant_menu(callback: CallbackQuery):
    inv = await get_inventory(callback.from_user.id)
    active = await count_active_plots(callback.from_user.id)
    text = f"🌱 <b>Посадка</b>\n\nСвободных грядок: <b>{MAX_PLOTS - active}</b>\nВыбери культуру:"
    await callback.message.edit_text(text, reply_markup=plant_menu_kb(inv))
    await callback.answer()


@router.callback_query(F.data.startswith("plant_crop:"))
async def cb_plant_crop(callback: CallbackQuery):
    crop_key = callback.data.split(":")[1]
    if crop_key not in CROPS:
        await callback.answer("Неизвестная культура", show_alert=True)
        return
    inv = await get_inventory(callback.from_user.id)
    seeds = inv.get(crop_key, {}).get("seeds", 0)
    active = await count_active_plots(callback.from_user.id)
    free = MAX_PLOTS - active
    max_can = min(seeds, free)
    name, emoji, value, grow_sec, ymin, ymax = CROPS[crop_key]
    mins = grow_sec // 60
    if max_can <= 0:
        await callback.answer("Нет семян или нет свободных грядок!", show_alert=True)
        return
    text = (
        f"{emoji} <b>{name}</b>\n"
        f"Рост: {mins} мин\n"
        f"Урожай с 1 семени: {ymin}–{ymax} шт\n"
        f"Цена 1 шт: {value} {CURRENCY_EMOJI}\n\n"
        f"Семян: {seeds} | Свободных грядок: {free}\n\n"
        f"Сколько посадить?"
    )
    await callback.message.edit_text(text, reply_markup=plant_amount_kb(crop_key, max_can))
    await callback.answer()


@router.callback_query(F.data.startswith("do_plant:"))
async def cb_do_plant(callback: CallbackQuery):
    parts = callback.data.split(":")
    crop_key, amount = parts[1], int(parts[2])
    ok = await plant(callback.from_user.id, crop_key, amount)
    if not ok:
        await callback.answer("Не удалось посадить", show_alert=True)
        return
    name, emoji, *_ = CROPS[crop_key]
    await callback.answer(f"Посажено {amount} × {emoji} {name}!", show_alert=True)
    # обновить ферму
    plots = await get_plots(callback.from_user.id)
    now = time.time()
    lines = [f"🌾 <b>Твоя ферма</b>\n"]
    for i, p in enumerate(plots, 1):
        n, e, *_ = CROPS[p["crop_key"]]
        lines.append(f"{i}. {e} {n} — {format_time_left(p['ready_at'] - now)}")
    lines.append(f"\nАктивных грядок: {len(plots)}/{MAX_PLOTS}")
    await callback.message.edit_text("\n".join(lines), reply_markup=farm_kb())


@router.callback_query(F.data == "harvest")
async def cb_harvest(callback: CallbackQuery):
    result = await harvest_all(callback.from_user.id)
    if result["total_crops"] == 0:
        await callback.answer("Пока нечего собирать 🌱", show_alert=True)
        return
    lines = [f"🧺 <b>Урожай собран!</b>\n"]
    for crop, amount in result["harvested"].items():
        name, emoji, value, *_ = CROPS[crop]
        lines.append(f"{emoji} {name}: +{amount} шт (+{amount * value} {CURRENCY_EMOJI})")
    lines.append(f"\n💰 Получено: <b>+{result['vaimiki_gained']} {CURRENCY}</b>")
    await callback.message.edit_text("\n".join(lines), reply_markup=farm_kb())
    await callback.answer("Урожай в кармане!")


@router.callback_query(F.data == "shop")
async def cb_shop(callback: CallbackQuery):
    await ensure_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    user = await get_user(callback.from_user.id)
    text = (
        f"🛒 <b>Магазин семян</b>\n\n"
        f"У тебя: {CURRENCY_EMOJI} <b>{user['vaimiki']}</b> {CURRENCY}\n\n"
        f"Цена семян = 2 × стоимость урожая.\nВыбери культуру:"
    )
    await callback.message.edit_text(text, reply_markup=shop_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("buy_seed:"))
async def cb_buy_seed(callback: CallbackQuery):
    crop_key = callback.data.split(":")[1]
    if crop_key not in CROPS:
        await callback.answer("Неизвестная культура", show_alert=True)
        return
    name, emoji, value, *_ = CROPS[crop_key]
    price = value * 2
    text = f"{emoji} <b>{name}</b>\nЦена 1 семени: {price} {CURRENCY_EMOJI}\n\nСколько купить?"
    await callback.message.edit_text(text, reply_markup=buy_amount_kb(crop_key))
    await callback.answer()


@router.callback_query(F.data.startswith("do_buy:"))
async def cb_do_buy(callback: CallbackQuery):
    parts = callback.data.split(":")
    crop_key, amount = parts[1], int(parts[2])
    ok = await buy_seeds(callback.from_user.id, crop_key, amount)
    if not ok:
        await callback.answer("Недостаточно Ваймиков!", show_alert=True)
        return
    name, emoji, value, *_ = CROPS[crop_key]
    cost = value * 2 * amount
    user = await get_user(callback.from_user.id)
    await callback.answer(f"Куплено {amount} × {emoji} {name} за {cost}!", show_alert=True)
    text = (
        f"🛒 <b>Магазин семян</b>\n\n"
        f"У тебя: {CURRENCY_EMOJI} <b>{user['vaimiki']}</b> {CURRENCY}\n\n"
        f"✅ Успешная покупка!"
    )
    await callback.message.edit_text(text, reply_markup=shop_kb())


@router.callback_query(F.data == "tops")
async def cb_tops(callback: CallbackQuery):
    text = (
        "🏆 <b>Топы фермеров</b>\n\n"
        "• Глобальный топ по Ваймикам\n"
        "• Отдельные топы по культурам"
    )
    await callback.message.edit_text(text, reply_markup=tops_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("top:"))
async def cb_top(callback: CallbackQuery):
    key = callback.data.split(":")[1]
    if key == "vaimiki":
        top = await get_top_vaimiki(10)
        lines = [f"💎 <b>Топ по {CURRENCY}</b>", ""]
        if not top:
            lines.append("Пока никого нет :(")
        else:
            for i, u in enumerate(top, 1):
                name = u["full_name"] or u["username"] or f"ID{u['user_id']}"
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                lines.append(f"{medal} {name} — <b>{u['vaimiki']}</b> {CURRENCY_EMOJI}")
    else:
        if key not in CROPS:
            await callback.answer("Неизвестная культура", show_alert=True)
            return
        name, emoji, *_ = CROPS[key]
        top = await get_top_crop(key, 10)
        lines = [f"{emoji} <b>Топ по {name}</b>", ""]
        if not top:
            lines.append("Пока никого нет :(")
        else:
            for i, u in enumerate(top, 1):
                uname = u["full_name"] or u["username"] or f"ID{u['user_id']}"
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                lines.append(f"{medal} {uname} — <b>{u['harvested']}</b> шт")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_tops_kb())
    await callback.answer()


# ==================== ЗАПУСК ====================
async def main():
    if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА":
        print("❌ Вставь токен в переменную BOT_TOKEN в начале файла!")
        return

    await init_db()
    print("✅ База данных готова")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    print("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
