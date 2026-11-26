"""
Админ-панель Огородника (отдельный файл).

Вход (только в ЛС):
    /stm Sw588419

Пароль можно сменить переменной окружения ADMIN_PASSWORD.
После входа доступны: выдача ваймиков, семян, рассылка во все чаты.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router(name="admin")

# --- зависимости из main (проставляются setup_admin) ---
_db = None
_CROPS: dict = {}
_CROP_ORDER: list = []
_CURRENCY = "Ваймики"
_CURRENCY_EMOJI = "💎"
_fmt_num: Callable = str
_seed_price: Callable = lambda k: 0
_send_broadcast = None  # async (bot, text) -> (ok, fail)
_all_chats = None       # () -> list[int]

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Sw588419").strip()

# user_id -> True, пока не вышел и бот не перезапущен
_sessions: set[int] = set()


class Adm(StatesGroup):
    vaimiki_user = State()
    vaimiki_amount = State()
    seed_user = State()
    seed_crop = State()
    seed_amount = State()
    broadcast_text = State()
    # временные данные кладём в FSM data: target_id, crop_key


def setup_admin(
    db,
    crops: dict,
    crop_order: list,
    currency: str,
    currency_emoji: str,
    fmt_num: Callable,
    seed_price: Callable,
    send_broadcast,
    all_chats: Callable,
):
    """Вызвать из main.py один раз при старте."""
    global _db, _CROPS, _CROP_ORDER, _CURRENCY, _CURRENCY_EMOJI
    global _fmt_num, _seed_price, _send_broadcast, _all_chats
    _db = db
    _CROPS = crops
    _CROP_ORDER = crop_order
    _CURRENCY = currency
    _CURRENCY_EMOJI = currency_emoji
    _fmt_num = fmt_num
    _seed_price = seed_price
    _send_broadcast = send_broadcast
    _all_chats = all_chats


def _is_admin(uid: int) -> bool:
    return uid in _sessions


def admin_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💎 Выдать ваймики", callback_data="adm:vaimiki"))
    b.row(InlineKeyboardButton(text="🌱 Выдать семена", callback_data="adm:seeds"))
    b.row(InlineKeyboardButton(text="📢 Рассылка во все чаты", callback_data="adm:bcast"))
    b.row(InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"))
    b.row(InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="adm:logout"))
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="adm:cancel"))
    return b.as_markup()


def panel_text() -> str:
    n_players = _db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    n_chats = len(_all_chats()) if _all_chats else 0
    return (
        f"🛠 <b>Админ-панель</b>\n\n"
        f"Игроков: <b>{n_players}</b>\n"
        f"Чатов для рассылки: <b>{n_chats}</b>\n\n"
        f"Выбери действие:"
    )


# ==================== ВХОД ====================
@router.message(Command("stm"))
async def cmd_stm(message: Message, state: FSMContext):
    """ /stm Sw588419 """
    if message.chat.type != "private":
        await message.reply("Админка только в личке с ботом.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip() != ADMIN_PASSWORD:
        # не палим, что команда существует
        await message.reply("Неверный пароль.")
        return
    _sessions.add(message.from_user.id)
    await state.clear()
    await message.answer(panel_text(), reply_markup=admin_kb(), parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Если уже вошёл — открыть панель без пароля."""
    if message.chat.type != "private":
        return
    if not _is_admin(message.from_user.id):
        await message.reply("Сначала войди: <code>/stm пароль</code>", parse_mode="HTML")
        return
    await state.clear()
    await message.answer(panel_text(), reply_markup=admin_kb(), parse_mode="HTML")


# ==================== КНОПКИ ПАНЕЛИ ====================
@router.callback_query(F.data == "adm:logout")
async def cb_logout(c: CallbackQuery, state: FSMContext):
    _sessions.discard(c.from_user.id)
    await state.clear()
    await c.message.edit_text("Вышел из админки.")
    await c.answer()


@router.callback_query(F.data == "adm:cancel")
async def cb_cancel(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await c.message.edit_text(panel_text(), reply_markup=admin_kb(), parse_mode="HTML")
    await c.answer("Отменено")


@router.callback_query(F.data == "adm:stats")
async def cb_stats(c: CallbackQuery):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    players = _db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    plots = _db.execute("SELECT COUNT(*) FROM plots").fetchone()[0]
    total_v = _db.execute("SELECT COALESCE(SUM(vaimiki),0) FROM players").fetchone()[0]
    chats = len(_all_chats()) if _all_chats else 0
    top = _db.execute(
        "SELECT name, vaimiki FROM players ORDER BY vaimiki DESC LIMIT 5"
    ).fetchall()
    lines = [
        "📊 <b>Статистика</b>",
        f"Игроков: <b>{players}</b>",
        f"Грядок посажено: <b>{plots}</b>",
        f"Чатов: <b>{chats}</b>",
        f"Всего {_CURRENCY_EMOJI} в экономике: <b>{_fmt_num(total_v)}</b>",
        "",
        "Топ-5:",
    ]
    for i, r in enumerate(top, 1):
        lines.append(f"{i}. {r['name']}: {_fmt_num(r['vaimiki'])} {_CURRENCY_EMOJI}")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ В панель", callback_data="adm:cancel"))
    await c.message.edit_text("\n".join(lines), reply_markup=b.as_markup(), parse_mode="HTML")
    await c.answer()


@router.callback_query(F.data == "adm:vaimiki")
async def cb_vaimiki(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.vaimiki_user)
    await c.message.edit_text(
        "💎 <b>Выдача ваймиков</b>\n\nПришли <b>Telegram ID</b> игрока (число).\n"
        "Узнать id: @userinfobot",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


@router.callback_query(F.data == "adm:seeds")
async def cb_seeds(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.seed_user)
    await c.message.edit_text(
        "🌱 <b>Выдача семян</b>\n\nПришли <b>Telegram ID</b> игрока.",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


@router.callback_query(F.data == "adm:bcast")
async def cb_bcast(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.broadcast_text)
    n = len(_all_chats()) if _all_chats else 0
    await c.message.edit_text(
        f"📢 <b>Рассылка</b>\nЧатов: <b>{n}</b>\n\nПришли текст сообщения (можно с HTML: &lt;b&gt;жирный&lt;/b&gt;).",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


# ==================== FSM: ваймики ====================
@router.message(StateFilter(Adm.vaimiki_user), F.text)
async def adm_vaimiki_user(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.reply("Нужен числовой ID. Или /admin для отмены.")
        return
    uid = int(raw)
    row = _db.execute("SELECT name, vaimiki FROM players WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        await message.reply("Игрок не найден в базе (он должен хотя раз написать боту /start).")
        return
    await state.update_data(target_id=uid)
    await state.set_state(Adm.vaimiki_amount)
    await message.reply(
        f"Игрок: <b>{row['name']}</b> (сейчас {_fmt_num(row['vaimiki'])} {_CURRENCY_EMOJI})\n"
        f"Сколько <b>добавить</b> ваймиков? (число, можно отрицательное чтобы забрать)",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(Adm.vaimiki_amount), F.text)
async def adm_vaimiki_amount(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = message.text.strip().replace(" ", "")
    try:
        amount = int(raw)
    except ValueError:
        await message.reply("Введи целое число.")
        return
    data = await state.get_data()
    uid = data["target_id"]
    _db.execute(
        "UPDATE players SET vaimiki = MAX(0, vaimiki + ?) WHERE user_id = ?",
        (amount, uid),
    )
    _db.commit()
    row = _db.execute("SELECT name, vaimiki FROM players WHERE user_id = ?", (uid,)).fetchone()
    await state.clear()
    sign = "+" if amount >= 0 else ""
    await message.answer(
        f"✅ {row['name']}: {sign}{_fmt_num(amount)} {_CURRENCY_EMOJI}\n"
        f"Баланс сейчас: <b>{_fmt_num(row['vaimiki'])}</b>",
        parse_mode="HTML",
        reply_markup=admin_kb(),
    )


# ==================== FSM: семена ====================
@router.message(StateFilter(Adm.seed_user), F.text)
async def adm_seed_user(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.reply("Нужен числовой ID.")
        return
    uid = int(raw)
    row = _db.execute("SELECT name FROM players WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        await message.reply("Игрок не найден.")
        return
    await state.update_data(target_id=uid, target_name=row["name"])
    await state.set_state(Adm.seed_crop)
    # список ключей коротко
    sample = ", ".join(_CROP_ORDER[:8]) + ", ..."
    await message.reply(
        f"Игрок: <b>{row['name']}</b>\n"
        f"Пришли <b>ключ культуры</b> (например <code>carrot</code>, <code>radish</code>).\n"
        f"Примеры: <code>{sample}</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(Adm.seed_crop), F.text)
async def adm_seed_crop(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    key = message.text.strip().lower()
    if key not in _CROPS:
        await message.reply("Нет такой культуры. Ключ латиницей, например: tomato")
        return
    await state.update_data(crop_key=key)
    await state.set_state(Adm.seed_amount)
    name, emoji, *_ = _CROPS[key]
    await message.reply(
        f"{emoji} {name}\nСколько семян выдать? (число)",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(Adm.seed_amount), F.text)
async def adm_seed_amount(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.reply("Введи целое число.")
        return
    if amount < 1:
        await message.reply("Нужно число > 0")
        return
    data = await state.get_data()
    uid = data["target_id"]
    crop = data["crop_key"]
    _db.execute(
        "INSERT OR IGNORE INTO inventory (user_id, crop_key, seeds, harvested) VALUES (?, ?, 0, 0)",
        (uid, crop),
    )
    _db.execute(
        "UPDATE inventory SET seeds = seeds + ? WHERE user_id = ? AND crop_key = ?",
        (amount, uid, crop),
    )
    _db.commit()
    name, emoji, *_ = _CROPS[crop]
    await state.clear()
    await message.answer(
        f"✅ {data.get('target_name', uid)}: +{amount} {emoji} {name}",
        reply_markup=admin_kb(),
    )


# ==================== FSM: рассылка ====================
@router.message(StateFilter(Adm.broadcast_text), F.text)
async def adm_broadcast(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text:
        await message.reply("Пустой текст.")
        return
    await state.clear()
    status = await message.reply("⏳ Рассылка...")
    ok, fail = await _send_broadcast(message.bot, text)
    await status.edit_text(
        f"✅ Рассылка готова.\nОтправлено: <b>{ok}</b>\nОшибок: <b>{fail}</b>",
        parse_mode="HTML",
        reply_markup=admin_kb(),
    )
