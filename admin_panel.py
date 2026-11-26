"""
Админ-панель Огородника (отдельный файл).

Вход (только в ЛС):
    /stm Sw588419

Пароль: переменная ADMIN_PASSWORD (по умолчанию Sw588419).
"""

from __future__ import annotations

import os
from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router(name="admin")

_db = None
_CROPS: dict = {}
_CROP_ORDER: list = []
_CURRENCY = "Ваймики"
_CURRENCY_EMOJI = "💎"
_fmt_num: Callable = str
_seed_price: Callable = lambda k: 0
_send_broadcast = None
_all_chats = None

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Sw588419").strip()
_sessions: set[int] = set()

PLAYERS_PER_PAGE = 15


class Adm(StatesGroup):
    vaimiki_user = State()
    vaimiki_amount = State()
    seed_user = State()
    seed_crop = State()
    seed_amount = State()
    take_seed_user = State()
    take_seed_crop = State()
    take_seed_amount = State()
    lookup_user = State()
    broadcast_text = State()


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
    b.row(
        InlineKeyboardButton(text="💎 + Ваймики", callback_data="adm:vaimiki"),
        InlineKeyboardButton(text="💎 − Ваймики", callback_data="adm:take_vaimiki"),
    )
    b.row(
        InlineKeyboardButton(text="🌱 + Семена", callback_data="adm:seeds"),
        InlineKeyboardButton(text="🌱 − Семена", callback_data="adm:take_seeds"),
    )
    b.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:bcast"))
    b.row(
        InlineKeyboardButton(text="👥 Игроки / ID", callback_data="adm:players:0"),
        InlineKeyboardButton(text="💬 Чаты бота", callback_data="adm:chats"),
    )
    b.row(
        InlineKeyboardButton(text="🔍 Игрок по ID", callback_data="adm:lookup"),
        InlineKeyboardButton(text="📊 Стата", callback_data="adm:stats"),
    )
    b.row(InlineKeyboardButton(text="🚪 Выйти", callback_data="adm:logout"))
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="adm:cancel"))
    return b.as_markup()


def back_panel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ В панель", callback_data="adm:cancel"))
    return b.as_markup()


def panel_text() -> str:
    n_players = _db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    n_chats = len(_all_chats()) if _all_chats else 0
    return (
        f"🛠 <b>Админ-панель</b>\n\n"
        f"Игроков: <b>{n_players}</b>\n"
        f"Чатов: <b>{n_chats}</b>\n\n"
        f"Выбери действие:"
    )


def _player_card(uid: int) -> str:
    row = _db.execute(
        "SELECT user_id, name, vaimiki, plots_limit FROM players WHERE user_id = ?",
        (uid,),
    ).fetchone()
    if not row:
        return "Игрок не найден."
    inv = _db.execute(
        "SELECT crop_key, seeds, harvested FROM inventory WHERE user_id = ? AND (seeds > 0 OR harvested > 0)",
        (uid,),
    ).fetchall()
    plots = _db.execute(
        "SELECT crop_key, ready_at FROM plots WHERE user_id = ?", (uid,)
    ).fetchall()
    lines = [
        f"👤 <b>{row['name']}</b>",
        f"ID: <code>{row['user_id']}</code>",
        f"{_CURRENCY_EMOJI} {_CURRENCY}: <b>{_fmt_num(row['vaimiki'])}</b>",
        f"Грядок: <b>{row['plots_limit']}</b> (занято {len(plots)})",
        "",
        "📦 Инвентарь (семена / собрано):",
    ]
    if not inv:
        lines.append("пусто")
    else:
        for r in inv[:40]:
            key = r["crop_key"]
            if key not in _CROPS:
                continue
            name, emoji, *_ = _CROPS[key]
            lines.append(f"{emoji} {name}: семян {r['seeds']} | собр. {r['harvested']}")
    return "\n".join(lines)


# ==================== ВХОД ====================
@router.message(Command("stm"))
async def cmd_stm(message: Message, state: FSMContext):
    if message.chat.type != "private":
        await message.reply("Админка только в личке с ботом.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip() != ADMIN_PASSWORD:
        await message.reply("Неверный пароль.")
        return
    _sessions.add(message.from_user.id)
    await state.clear()
    await message.answer(panel_text(), reply_markup=admin_kb(), parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return
    if not _is_admin(message.from_user.id):
        await message.reply("Сначала: <code>/stm пароль</code>", parse_mode="HTML")
        return
    await state.clear()
    await message.answer(panel_text(), reply_markup=admin_kb(), parse_mode="HTML")


# ==================== ПАНЕЛЬ ====================
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
    await c.answer()


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
        "SELECT user_id, name, vaimiki FROM players ORDER BY vaimiki DESC LIMIT 10"
    ).fetchall()
    lines = [
        "📊 <b>Статистика</b>",
        f"Игроков: <b>{players}</b>",
        f"Грядок: <b>{plots}</b>",
        f"Чатов: <b>{chats}</b>",
        f"Всего {_CURRENCY_EMOJI}: <b>{_fmt_num(total_v)}</b>",
        "",
        "Топ-10:",
    ]
    for i, r in enumerate(top, 1):
        lines.append(
            f"{i}. {r['name']} — {_fmt_num(r['vaimiki'])} {_CURRENCY_EMOJI} "
            f"(<code>{r['user_id']}</code>)"
        )
    await c.message.edit_text("\n".join(lines), reply_markup=back_panel_kb(), parse_mode="HTML")
    await c.answer()


# ---------- игроки / база ----------
@router.callback_query(F.data.startswith("adm:players:"))
async def cb_players(c: CallbackQuery):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    page = int(c.data.split(":")[2])
    total = _db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    pages = max(1, (total + PLAYERS_PER_PAGE - 1) // PLAYERS_PER_PAGE)
    page = max(0, min(page, pages - 1))
    rows = _db.execute(
        "SELECT user_id, name, vaimiki, plots_limit FROM players "
        "ORDER BY vaimiki DESC LIMIT ? OFFSET ?",
        (PLAYERS_PER_PAGE, page * PLAYERS_PER_PAGE),
    ).fetchall()
    lines = [f"👥 <b>Игроки</b> (стр. {page + 1}/{pages}, всего {total})\n"]
    if not rows:
        lines.append("Пусто")
    for r in rows:
        lines.append(
            f"• <code>{r['user_id']}</code> — {r['name']}\n"
            f"  {_CURRENCY_EMOJI} {_fmt_num(r['vaimiki'])} · грядок {r['plots_limit']}"
        )
    b = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm:players:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm:players:{page + 1}"))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="◀️ В панель", callback_data="adm:cancel"))
    await c.message.edit_text("\n".join(lines), reply_markup=b.as_markup(), parse_mode="HTML")
    await c.answer()


@router.callback_query(F.data == "adm:chats")
async def cb_chats(c: CallbackQuery):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    # user_chats + игроки (лички)
    rows = _db.execute(
        """
        SELECT uc.chat_id, uc.user_id, p.name
        FROM user_chats uc
        LEFT JOIN players p ON p.user_id = uc.user_id
        ORDER BY uc.chat_id
        """
    ).fetchall()
    lines = ["💬 <b>Чаты, где бот что-то писал / видел игрока</b>\n"]
    if not rows:
        lines.append(
            "Пока пусто.\n"
            "Чат попадает сюда, когда кто-то пишет боту в этом чате."
        )
    else:
        # группируем по chat_id
        by_chat: dict[int, list] = {}
        for r in rows:
            by_chat.setdefault(int(r["chat_id"]), []).append(r)
        for chat_id, members in list(by_chat.items())[:40]:
            kind = "👤 ЛС" if chat_id > 0 else "👥 Группа"
            names = ", ".join(
                (m["name"] or "?") + f" (<code>{m['user_id']}</code>)" for m in members[:5]
            )
            lines.append(f"{kind} <code>{chat_id}</code>\n  {names}")
        if len(by_chat) > 40:
            lines.append(f"\n…и ещё {len(by_chat) - 40} чатов")
    lines.append(f"\nВсего уникальных chat_id: <b>{len({int(r['chat_id']) for r in rows})}</b>")
    await c.message.edit_text("\n".join(lines), reply_markup=back_panel_kb(), parse_mode="HTML")
    await c.answer()


@router.callback_query(F.data == "adm:lookup")
async def cb_lookup(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.lookup_user)
    await c.message.edit_text(
        "🔍 Пришли <b>Telegram ID</b> игрока — покажу баланс, семена, грядки.",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


@router.message(StateFilter(Adm.lookup_user), F.text)
async def adm_lookup(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.reply("Нужен числовой ID.")
        return
    await state.clear()
    await message.answer(_player_card(int(raw)), reply_markup=admin_kb(), parse_mode="HTML")


# ---------- выдать / забрать ваймики ----------
@router.callback_query(F.data == "adm:vaimiki")
async def cb_vaimiki(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.vaimiki_user)
    await state.update_data(vaimiki_mode="add")
    await c.message.edit_text(
        "💎 <b>Выдать ваймики</b>\nПришли ID игрока.",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


@router.callback_query(F.data == "adm:take_vaimiki")
async def cb_take_vaimiki(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.vaimiki_user)
    await state.update_data(vaimiki_mode="take")
    await c.message.edit_text(
        "💎 <b>Забрать ваймики</b>\nПришли ID игрока.",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


@router.message(StateFilter(Adm.vaimiki_user), F.text)
async def adm_vaimiki_user(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.reply("Нужен числовой ID.")
        return
    uid = int(raw)
    row = _db.execute("SELECT name, vaimiki FROM players WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        await message.reply("Игрок не найден (нужен /start у бота).")
        return
    data = await state.get_data()
    mode = data.get("vaimiki_mode", "add")
    await state.update_data(target_id=uid)
    await state.set_state(Adm.vaimiki_amount)
    action = "добавить" if mode == "add" else "забрать"
    await message.reply(
        f"Игрок: <b>{row['name']}</b>\nСейчас: {_fmt_num(row['vaimiki'])} {_CURRENCY_EMOJI}\n"
        f"Сколько <b>{action}</b>?",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(Adm.vaimiki_amount), F.text)
async def adm_vaimiki_amount(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        amount = abs(int(message.text.strip().replace(" ", "")))
    except ValueError:
        await message.reply("Введи целое число.")
        return
    data = await state.get_data()
    uid = data["target_id"]
    mode = data.get("vaimiki_mode", "add")
    delta = amount if mode == "add" else -amount
    _db.execute(
        "UPDATE players SET vaimiki = MAX(0, vaimiki + ?) WHERE user_id = ?",
        (delta, uid),
    )
    _db.commit()
    row = _db.execute("SELECT name, vaimiki FROM players WHERE user_id = ?", (uid,)).fetchone()
    await state.clear()
    sign = "+" if delta >= 0 else "−"
    await message.answer(
        f"✅ {row['name']}: {sign}{_fmt_num(amount)} {_CURRENCY_EMOJI}\n"
        f"Баланс: <b>{_fmt_num(row['vaimiki'])}</b>",
        parse_mode="HTML",
        reply_markup=admin_kb(),
    )


# ---------- выдать семена ----------
@router.callback_query(F.data == "adm:seeds")
async def cb_seeds(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.seed_user)
    await c.message.edit_text(
        "🌱 <b>Выдать семена</b>\nПришли ID игрока.",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


@router.message(StateFilter(Adm.seed_user), F.text)
async def adm_seed_user(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.reply("Нужен числовой ID.")
        return
    uid = int(message.text.strip())
    row = _db.execute("SELECT name FROM players WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        await message.reply("Игрок не найден.")
        return
    await state.update_data(target_id=uid, target_name=row["name"])
    await state.set_state(Adm.seed_crop)
    sample = ", ".join(_CROP_ORDER[:10])
    await message.reply(
        f"Игрок: <b>{row['name']}</b>\nКлюч культуры, например <code>carrot</code>\n"
        f"<code>{sample}</code>…",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(Adm.seed_crop), F.text)
async def adm_seed_crop(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    key = message.text.strip().lower()
    if key not in _CROPS:
        await message.reply("Нет такой культуры.")
        return
    await state.update_data(crop_key=key)
    await state.set_state(Adm.seed_amount)
    name, emoji, *_ = _CROPS[key]
    await message.reply(f"{emoji} {name}\nСколько семян выдать?", reply_markup=cancel_kb())


@router.message(StateFilter(Adm.seed_amount), F.text)
async def adm_seed_amount(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.reply("Число.")
        return
    if amount < 1:
        await message.reply("Нужно > 0")
        return
    data = await state.get_data()
    uid, crop = data["target_id"], data["crop_key"]
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
        f"✅ {data.get('target_name')}: +{amount} {emoji} {name}",
        reply_markup=admin_kb(),
    )


# ---------- забрать семена ----------
@router.callback_query(F.data == "adm:take_seeds")
async def cb_take_seeds(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.take_seed_user)
    await c.message.edit_text(
        "🌱 <b>Забрать семена</b>\nПришли ID игрока.",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


@router.message(StateFilter(Adm.take_seed_user), F.text)
async def adm_take_seed_user(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.reply("Нужен числовой ID.")
        return
    uid = int(message.text.strip())
    row = _db.execute("SELECT name FROM players WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        await message.reply("Игрок не найден.")
        return
    inv = _db.execute(
        "SELECT crop_key, seeds FROM inventory WHERE user_id = ? AND seeds > 0",
        (uid,),
    ).fetchall()
    await state.update_data(target_id=uid, target_name=row["name"])
    await state.set_state(Adm.take_seed_crop)
    lines = [f"Игрок: <b>{row['name']}</b>\nСемена у него:"]
    if not inv:
        lines.append("нет семян")
    else:
        for r in inv[:30]:
            if r["crop_key"] not in _CROPS:
                continue
            name, emoji, *_ = _CROPS[r["crop_key"]]
            lines.append(f"{emoji} <code>{r['crop_key']}</code> — {r['seeds']} шт")
    lines.append("\nПришли ключ культуры:")
    await message.reply("\n".join(lines), parse_mode="HTML", reply_markup=cancel_kb())


@router.message(StateFilter(Adm.take_seed_crop), F.text)
async def adm_take_seed_crop(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    key = message.text.strip().lower()
    if key not in _CROPS:
        await message.reply("Нет такой культуры.")
        return
    data = await state.get_data()
    row = _db.execute(
        "SELECT seeds FROM inventory WHERE user_id = ? AND crop_key = ?",
        (data["target_id"], key),
    ).fetchone()
    have = row["seeds"] if row else 0
    await state.update_data(crop_key=key)
    await state.set_state(Adm.take_seed_amount)
    name, emoji, *_ = _CROPS[key]
    await message.reply(
        f"{emoji} {name}: сейчас {have} шт\nСколько забрать? (или <code>all</code> = все)",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(Adm.take_seed_amount), F.text)
async def adm_take_seed_amount(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    uid, crop = data["target_id"], data["crop_key"]
    row = _db.execute(
        "SELECT seeds FROM inventory WHERE user_id = ? AND crop_key = ?",
        (uid, crop),
    ).fetchone()
    have = row["seeds"] if row else 0
    raw = message.text.strip().lower()
    if raw in ("all", "все", "всё"):
        amount = have
    else:
        try:
            amount = int(raw)
        except ValueError:
            await message.reply("Число или all")
            return
    amount = max(0, min(amount, have))
    if amount == 0:
        await message.reply("Нечего забирать.")
        await state.clear()
        await message.answer(panel_text(), reply_markup=admin_kb(), parse_mode="HTML")
        return
    _db.execute(
        "UPDATE inventory SET seeds = seeds - ? WHERE user_id = ? AND crop_key = ?",
        (amount, uid, crop),
    )
    _db.commit()
    name, emoji, *_ = _CROPS[crop]
    await state.clear()
    await message.answer(
        f"✅ У {data.get('target_name')}: −{amount} {emoji} {name}",
        reply_markup=admin_kb(),
    )


# ---------- рассылка ----------
@router.callback_query(F.data == "adm:bcast")
async def cb_bcast(c: CallbackQuery, state: FSMContext):
    if not _is_admin(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(Adm.broadcast_text)
    n = len(_all_chats()) if _all_chats else 0
    await c.message.edit_text(
        f"📢 <b>Рассылка</b>\nЧатов: <b>{n}</b>\n\nПришли текст сообщения.",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await c.answer()


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
        f"✅ Готово.\nОтправлено: <b>{ok}</b>\nОшибок: <b>{fail}</b>",
        parse_mode="HTML",
        reply_markup=admin_kb(),
    )
