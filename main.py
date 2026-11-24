"""
Огородник 2.0 — Ферма Ваймиков
Команды + кнопки. Несколько культур, валюта Ваймики, топы.

Запуск:
    pip install aiogram
    python bot.py
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

# ==================== НАСТРОЙКИ ====================
TOKEN = os.getenv("BOT_TOKEN", "9194809506:AAFmvmDPdS0Yn-gvE64bq7C5BUOeUsWRs8g")

CURRENCY = "Ваймики"
CURRENCY_EMOJI = "💎"
MAX_PLOTS = 5
START_VAIMIKI = 20

# культура: (название, эмодзи, цена за 1 шт, время роста сек, мин урожай, макс урожай)
CROPS = {
    "carrot":  ("Морковь",  "🥕", 1, 30 * 60,  8, 12),
    "beet":    ("Свёкла",   "🟣", 2, 45 * 60,  6, 10),
    "potato":  ("Картошка", "🥔", 3, 60 * 60,  5,  9),
    "tomato":  ("Помидор",  "🍅", 4, 40 * 60,  7, 11),
    "cabbage": ("Капуста",  "🥬", 2, 50 * 60,  6, 10),
    "corn":    ("Кукуруза", "🌽", 5, 90 * 60,  4,  8),
}

START_SEEDS = {"carrot": 3, "beet": 1}
DB_PATH = "game.db"

dp = Dispatcher()

# ==================== БАЗА ДАННЫХ ====================
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row

db.execute("""
    CREATE TABLE IF NOT EXISTS players (
        user_id   INTEGER PRIMARY KEY,
        name      TEXT NOT NULL,
        vaimiki   INTEGER NOT NULL DEFAULT 0,
        level     INTEGER NOT NULL DEFAULT 1
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


def ensure_player(user):
    db.execute(
        "INSERT OR IGNORE INTO players (user_id, name, vaimiki) VALUES (?, ?, ?)",
        (user.id, user.full_name, START_VAIMIKI)
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
def main_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🌾 Ферма", callback_data="farm"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
    )
    b.row(
        InlineKeyboardButton(text="🛒 Магазин", callback_data="shop"),
        InlineKeyboardButton(text="🏆 Топы", callback_data="tops"),
    )
    b.row(InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"))
    return b.as_markup()


def farm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🌱 Посадить", callback_data="plant_menu"),
        InlineKeyboardButton(text="🧺 Собрать", callback_data="harvest"),
    )
    b.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="farm"),
        InlineKeyboardButton(text="◀️ Меню", callback_data="menu"),
    )
    return b.as_markup()


def plant_menu_kb(inv: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, (name, emoji, *_) in CROPS.items():
        seeds = inv.get(key, {}).get("seeds", 0)
        b.row(InlineKeyboardButton(
            text=f"{emoji} {name} ({seeds} семян)",
            callback_data=f"pc:{key}"
        ))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="farm"))
    return b.as_markup()


def plant_amount_kb(crop: str, max_a: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    row = []
    for a in [1, 2, 3, 5]:
        if a <= max_a:
            row.append(InlineKeyboardButton(text=str(a), callback_data=f"dp:{crop}:{a}"))
    if row:
        b.row(*row)
    if max_a > 5:
        b.row(InlineKeyboardButton(text=f"Все ({max_a})", callback_data=f"dp:{crop}:{max_a}"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="plant_menu"))
    return b.as_markup()


def shop_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, (name, emoji, value, *_) in CROPS.items():
        price = value * 2
        b.row(InlineKeyboardButton(
            text=f"{emoji} {name} — {price} {CURRENCY_EMOJI}",
            callback_data=f"bs:{key}"
        ))
    b.row(InlineKeyboardButton(text="◀️ Меню", callback_data="menu"))
    return b.as_markup()


def buy_amount_kb(crop: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for a in [1, 3, 5, 10]:
        b.add(InlineKeyboardButton(text=str(a), callback_data=f"db:{crop}:{a}"))
    b.adjust(4)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="shop"))
    return b.as_markup()


def tops_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💎 Топ Ваймиков", callback_data="top:vaimiki"))
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
    b.row(InlineKeyboardButton(text="◀️ Меню", callback_data="menu"))
    return b.as_markup()


def back_tops_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ К топам", callback_data="tops"))
    b.row(InlineKeyboardButton(text="🏠 Меню", callback_data="menu"))
    return b.as_markup()


def back_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Меню", callback_data="menu"))
    return b.as_markup()


# ==================== КОМАНДЫ ====================
@dp.message(CommandStart())
@dp.message(Command("help"))
async def cmd_start(message: Message):
    ensure_player(message.from_user)
    await message.answer(
        f"🌾 <b>Ферма Ваймиков</b>\n\n"
        f"Выращивай овощи и зарабатывай {CURRENCY_EMOJI} <b>{CURRENCY}</b>!\n\n"
        f"Команды:\n"
        f"/farm — ферма\n"
        f"/shop — магазин семян\n"
        f"/balance — профиль\n"
        f"/top — топы\n"
        f"/help — помощь\n\n"
        f"Или пользуйся кнопками 👇",
        reply_markup=main_kb(),
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
        f"🛒 <b>Магазин семян</b>\n\n"
        f"У тебя: {CURRENCY_EMOJI} <b>{p['vaimiki']}</b>\n"
        f"Цена семян = 2 × стоимость урожая.",
        reply_markup=shop_kb(),
        parse_mode="HTML"
    )


@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    ensure_player(message.from_user)
    await show_profile(message, message.from_user)


@dp.message(Command("top"))
async def cmd_top(message: Message):
    await message.answer(
        "🏆 <b>Топы</b>\nВыбери категорию:",
        reply_markup=tops_kb(),
        parse_mode="HTML"
    )


# ==================== ПОКАЗ ФЕРМЫ / ПРОФИЛЯ ====================
async def show_farm(target, user_id: int, edit: bool = False):
    plots = get_plots(user_id)
    now = time.time()
    lines = ["🌾 <b>Твоя ферма</b>\n"]
    if not plots:
        lines.append("Грядки пустые. Нажми «Посадить».")
    else:
        ready = 0
        for i, p in enumerate(plots, 1):
            name, emoji, *_ = CROPS[p["crop_key"]]
            left = p["ready_at"] - now
            if left <= 0:
                ready += 1
            lines.append(f"{i}. {emoji} {name} — {format_time(left)}")
        lines.append(f"\nГрядок: {len(plots)}/{MAX_PLOTS}")
        if ready:
            lines.append(f"🎉 Готово: <b>{ready}</b>")
    text = "\n".join(lines)
    if edit and hasattr(target, "message"):
        await target.message.edit_text(text, reply_markup=farm_kb(), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=farm_kb(), parse_mode="HTML")


async def show_profile(target, user, edit: bool = False):
    p = get_player(user.id)
    inv = get_inventory(user.id)
    lines = [
        f"👤 <b>{user.full_name}</b>",
        f"{CURRENCY_EMOJI} {CURRENCY}: <b>{p['vaimiki']}</b>",
        "",
        "📦 Инвентарь:"
    ]
    for key, (name, emoji, *_) in CROPS.items():
        d = inv.get(key, {"seeds": 0, "harvested": 0})
        lines.append(f"{emoji} {name}: семян {d['seeds']} | собрано {d['harvested']}")
    text = "\n".join(lines)
    if edit and hasattr(target, "message"):
        await target.message.edit_text(text, reply_markup=back_menu_kb(), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=back_menu_kb(), parse_mode="HTML")


# ==================== CALLBACKS ====================
@dp.callback_query(F.data == "menu")
async def cb_menu(c: CallbackQuery):
    await c.message.edit_text(
        "🏠 <b>Главное меню</b>",
        reply_markup=main_kb(),
        parse_mode="HTML"
    )
    await c.answer()


@dp.callback_query(F.data == "farm")
async def cb_farm(c: CallbackQuery):
    ensure_player(c.from_user)
    await show_farm(c, c.from_user.id, edit=True)
    await c.answer()


@dp.callback_query(F.data == "profile")
async def cb_profile(c: CallbackQuery):
    ensure_player(c.from_user)
    await show_profile(c, c.from_user, edit=True)
    await c.answer()


@dp.callback_query(F.data == "help")
async def cb_help(c: CallbackQuery):
    text = (
        f"ℹ️ <b>Как играть</b>\n\n"
        f"1. Купи семена в магазине\n"
        f"2. Посади на ферме\n"
        f"3. Жди роста (30–90 мин)\n"
        f"4. Собери урожай → получи {CURRENCY}\n\n"
        f"<b>Культуры:</b>\n"
    )
    for key, (name, emoji, value, grow, ymin, ymax) in CROPS.items():
        text += f"{emoji} {name}: {value} {CURRENCY_EMOJI} | {grow // 60} мин | {ymin}–{ymax} шт\n"
    text += f"\nМакс. грядок: {MAX_PLOTS}"
    await c.message.edit_text(text, reply_markup=back_menu_kb(), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data == "plant_menu")
async def cb_plant_menu(c: CallbackQuery):
    inv = get_inventory(c.from_user.id)
    free = MAX_PLOTS - count_plots(c.from_user.id)
    await c.message.edit_text(
        f"🌱 <b>Посадка</b>\nСвободных грядок: <b>{free}</b>",
        reply_markup=plant_menu_kb(inv),
        parse_mode="HTML"
    )
    await c.answer()


@dp.callback_query(F.data.startswith("pc:"))
async def cb_plant_crop(c: CallbackQuery):
    crop = c.data.split(":")[1]
    if crop not in CROPS:
        await c.answer("Нет такой культуры", show_alert=True)
        return
    inv = get_inventory(c.from_user.id)
    seeds = inv[crop]["seeds"]
    free = MAX_PLOTS - count_plots(c.from_user.id)
    max_can = min(seeds, free)
    name, emoji, value, grow, ymin, ymax = CROPS[crop]
    if max_can <= 0:
        await c.answer("Нет семян или грядок!", show_alert=True)
        return
    text = (
        f"{emoji} <b>{name}</b>\n"
        f"Рост: {grow // 60} мин | Урожай: {ymin}–{ymax}\n"
        f"Цена 1 шт: {value} {CURRENCY_EMOJI}\n\n"
        f"Семян: {seeds} | Свободно: {free}\n"
        f"Сколько посадить?"
    )
    await c.message.edit_text(text, reply_markup=plant_amount_kb(crop, max_can), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data.startswith("dp:"))
async def cb_do_plant(c: CallbackQuery):
    _, crop, amount_s = c.data.split(":")
    amount = int(amount_s)
    inv = get_inventory(c.from_user.id)
    free = MAX_PLOTS - count_plots(c.from_user.id)
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


@dp.callback_query(F.data == "harvest")
async def cb_harvest(c: CallbackQuery):
    now = time.time()
    plots = get_plots(c.from_user.id)
    ready = [p for p in plots if p["ready_at"] <= now]
    if not ready:
        await c.answer("Ещё нечего собирать 🌱", show_alert=True)
        return
    harvested = {}
    total_v = 0
    ids = []
    for p in ready:
        crop = p["crop_key"]
        _, _, value, _, ymin, ymax = CROPS[crop]
        amt = random.randint(ymin, ymax)
        harvested[crop] = harvested.get(crop, 0) + amt
        total_v += amt * value
        ids.append(p["id"])
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
    await c.message.edit_text("\n".join(lines), reply_markup=farm_kb(), parse_mode="HTML")
    await c.answer("Готово!")


@dp.callback_query(F.data == "shop")
async def cb_shop(c: CallbackQuery):
    ensure_player(c.from_user)
    p = get_player(c.from_user.id)
    await c.message.edit_text(
        f"🛒 <b>Магазин</b>\nУ тебя: {CURRENCY_EMOJI} <b>{p['vaimiki']}</b>",
        reply_markup=shop_kb(),
        parse_mode="HTML"
    )
    await c.answer()


@dp.callback_query(F.data.startswith("bs:"))
async def cb_buy_seed(c: CallbackQuery):
    crop = c.data.split(":")[1]
    name, emoji, value, *_ = CROPS[crop]
    price = value * 2
    await c.message.edit_text(
        f"{emoji} <b>{name}</b>\nЦена: {price} {CURRENCY_EMOJI} / семя\nСколько купить?",
        reply_markup=buy_amount_kb(crop),
        parse_mode="HTML"
    )
    await c.answer()


@dp.callback_query(F.data.startswith("db:"))
async def cb_do_buy(c: CallbackQuery):
    _, crop, amount_s = c.data.split(":")
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
        "UPDATE inventory SET seeds = seeds + ? WHERE user_id = ? AND crop_key = ?",
        (amount, c.from_user.id, crop)
    )
    db.commit()
    name, emoji, *_ = CROPS[crop]
    p = get_player(c.from_user.id)
    await c.answer(f"+{amount} {emoji} {name} за {cost}!", show_alert=True)
    await c.message.edit_text(
        f"🛒 <b>Магазин</b>\nУ тебя: {CURRENCY_EMOJI} <b>{p['vaimiki']}</b>\n✅ Куплено!",
        reply_markup=shop_kb(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "tops")
async def cb_tops(c: CallbackQuery):
    await c.message.edit_text(
        "🏆 <b>Топы</b>\nВыбери:",
        reply_markup=tops_kb(),
        parse_mode="HTML"
    )
    await c.answer()


@dp.callback_query(F.data.startswith("top:"))
async def cb_top(c: CallbackQuery):
    key = c.data.split(":")[1]
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
    await c.message.edit_text("\n".join(lines), reply_markup=back_tops_kb(), parse_mode="HTML")
    await c.answer()


# ==================== ЗАПУСК ====================
async def main():
    if not TOKEN or "ВСТАВЬ" in str(TOKEN):
        raise SystemExit("Укажи токен в TOKEN")

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
