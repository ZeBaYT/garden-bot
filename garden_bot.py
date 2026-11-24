"""
Игровой бот для Телеграма: собираешь урожай, продаёшь, улучшаешь грядки, смотришь топ.

Запуск:
    pip install aiogram
    export BOT_TOKEN="токен от @BotFather"     # Windows: set BOT_TOKEN=токен
    python garden_bot.py

Чтобы бот понимал обычные слова ("Сбор", "Продать все") в группе,
в @BotFather: /mybots -> твой бот -> Bot Settings -> Group Privacy -> Turn off.
Команды (/collect и т.д.) работают и без этого.
"""

import asyncio
import logging
import os
import random
import sqlite3
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import BotCommand, Message

TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "game.db"
COOLDOWN_SECONDS = 60  # пауза между сборами; для 30 минут поставь 1800
PRICE_PER_ITEM = 1     # сколько монет дают за одну единицу урожая

dp = Dispatcher()

# ---------- база данных ----------

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
db.execute(
    """
    CREATE TABLE IF NOT EXISTS players (
        user_id      INTEGER PRIMARY KEY,
        name         TEXT    NOT NULL,
        crops        INTEGER NOT NULL DEFAULT 0,
        coins        INTEGER NOT NULL DEFAULT 0,
        level        INTEGER NOT NULL DEFAULT 1,
        last_collect REAL    NOT NULL DEFAULT 0
    )
    """
)
db.commit()


def get_player(user) -> sqlite3.Row:
    """Находит игрока по Telegram ID, а если его нет, создаёт."""
    db.execute(
        "INSERT OR IGNORE INTO players (user_id, name) VALUES (?, ?)",
        (user.id, user.full_name),
    )
    db.execute("UPDATE players SET name = ? WHERE user_id = ?", (user.full_name, user.id))
    db.commit()
    return db.execute("SELECT * FROM players WHERE user_id = ?", (user.id,)).fetchone()


# ---------- вспомогательное ----------


def upgrade_cost(level: int) -> int:
    return 10 * level * level


def fmt_time(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    return f"{minutes} мин {sec} сек" if minutes else f"{sec} сек"


# ---------- команды ----------


@dp.message(Command("start", "help"))
async def help_cmd(message: Message):
    get_player(message.from_user)
    await message.answer(
        "🌱 Огородик: выращивай урожай и богатей!\n\n"
        "/collect (или слово «Сбор»): собрать урожай\n"
        "/sell (или «Продать все»): продать урожай за монеты\n"
        "/shop: магазин\n"
        "/upgrade: улучшить грядки (урожай растёт)\n"
        "/balance: твой баланс\n"
        "/top: топ игроков"
    )


@dp.message(Command("collect"))
@dp.message(F.text.casefold() == "сбор")
async def collect_cmd(message: Message):
    p = get_player(message.from_user)
    wait = int(p["last_collect"] + COOLDOWN_SECONDS - time.time())
    if wait > 0:
        await message.answer(f"🌱 Урожай ещё растёт. Подожди {fmt_time(wait)}")
        return

    gain = random.randint(p["level"] * 3, p["level"] * 5)
    db.execute(
        "UPDATE players SET crops = crops + ?, last_collect = ? WHERE user_id = ?",
        (gain, time.time(), p["user_id"]),
    )
    db.commit()
    await message.answer(
        f"✂️ Ты собрал урожай: +{gain} 🥕\n\nУ тебя: {p['crops'] + gain} 🥕"
    )


@dp.message(Command("sell"))
@dp.message(F.text.casefold().in_({"продать все", "продать всё"}))
async def sell_cmd(message: Message):
    p = get_player(message.from_user)
    if p["crops"] == 0:
        await message.answer("Продавать нечего. Сначала собери урожай: /collect")
        return

    earned = p["crops"] * PRICE_PER_ITEM
    db.execute(
        "UPDATE players SET crops = 0, coins = coins + ? WHERE user_id = ?",
        (earned, p["user_id"]),
    )
    db.commit()
    await message.answer(
        f"💰 Ты продал {p['crops']} 🥕 за {earned} 🪙\n\n"
        f"У тебя: 0 🥕\nУ тебя: {p['coins'] + earned} 🪙"
    )


@dp.message(Command("shop"))
async def shop_cmd(message: Message):
    p = get_player(message.from_user)
    cost = upgrade_cost(p["level"])
    await message.answer(
        "🛒 Магазин\n\n"
        f"⬆️ Улучшить грядки до уровня {p['level'] + 1}: {cost} 🪙\n"
        f"Твой баланс: {p['coins']} 🪙\n\n"
        "Купить: /upgrade"
    )


@dp.message(Command("upgrade"))
async def upgrade_cmd(message: Message):
    p = get_player(message.from_user)
    cost = upgrade_cost(p["level"])
    if p["coins"] < cost:
        await message.answer(f"Не хватает монет: нужно {cost} 🪙, у тебя {p['coins']} 🪙")
        return

    db.execute(
        "UPDATE players SET coins = coins - ?, level = level + 1 WHERE user_id = ?",
        (cost, p["user_id"]),
    )
    db.commit()
    await message.answer(f"⬆️ Грядки улучшены! Твой уровень: {p['level'] + 1}")


@dp.message(Command("balance"))
async def balance_cmd(message: Message):
    p = get_player(message.from_user)
    await message.answer(
        f"👤 {p['name']}\n\n"
        f"Уровень грядок: {p['level']}\n"
        f"Урожай: {p['crops']} 🥕\n"
        f"Монеты: {p['coins']} 🪙"
    )


@dp.message(Command("top"))
async def top_cmd(message: Message):
    rows = db.execute(
        "SELECT name, coins FROM players ORDER BY coins DESC LIMIT 10"
    ).fetchall()
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 Топ богачей\n"]
    for i, row in enumerate(rows):
        place = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{place} {row['name']}: {row['coins']} 🪙")
    await message.answer("\n".join(lines))


# ---------- запуск ----------


async def main():
    if not TOKEN:
        raise SystemExit("Не задан токен. Выполни: export BOT_TOKEN=твой_токен")

    logging.basicConfig(level=logging.INFO)
    bot = Bot(TOKEN)
    await bot.set_my_commands(
        [
            BotCommand(command="collect", description="✂️ Собрать урожай"),
            BotCommand(command="sell", description="💰 Продать всё"),
            BotCommand(command="shop", description="🛒 Магазин"),
            BotCommand(command="upgrade", description="⬆️ Улучшить грядки"),
            BotCommand(command="balance", description="👤 Баланс"),
            BotCommand(command="top", description="🏆 Топ игроков"),
            BotCommand(command="help", description="🌱 Помощь"),
        ]
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
