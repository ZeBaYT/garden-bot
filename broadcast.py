"""
Рассылка от лица бота во все чаты из базы.

На bothost (в консоли бота):
    python broadcast.py Привет всем из Огородника!

Или многострочно:
    python broadcast.py "Строка 1
Строка 2"

Чаты берутся из таблицы user_chats (туда попадают ЛС и группы, где кто-то писал боту).
Токен — из BOT_TOKEN или token.txt, база — /app/data/game.db (как у main.py).
"""

import asyncio
import os
import sqlite3
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


def load_token() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token and os.path.exists("token.txt"):
        with open("token.txt", encoding="utf-8") as f:
            token = f.read().strip()
    return token


def db_path() -> str:
    data_dir = os.environ.get("DATA_DIR", "/app/data")
    path = os.path.join(data_dir, "game.db")
    if os.path.exists(path):
        return path
    if os.path.exists("game.db"):
        return "game.db"
    # старые имена
    for name in ("game.db",):
        if os.path.exists(name):
            return name
    import glob
    found = sorted(glob.glob(os.path.join(data_dir, "game_*.db")) + glob.glob("game_*.db"))
    if found:
        return found[-1]
    return path


def all_chat_ids(path: str) -> list[int]:
    if not os.path.exists(path):
        print(f"База не найдена: {path}")
        return []
    con = sqlite3.connect(path)
    chats = set()
    try:
        for (cid,) in con.execute("SELECT DISTINCT chat_id FROM user_chats"):
            chats.add(int(cid))
    except sqlite3.OperationalError:
        print("Таблица user_chats ещё пустая — пусть кто-нибудь напишет боту в нужных чатах.")
    # на всякий случай лички игроков
    try:
        for (uid,) in con.execute("SELECT user_id FROM players"):
            chats.add(int(uid))
    except sqlite3.OperationalError:
        pass
    con.close()
    return sorted(chats)


async def main():
    if len(sys.argv) < 2:
        print("Использование: python broadcast.py Текст сообщения")
        print('Пример: python broadcast.py "Обновление фермы завтра в 18:00"')
        sys.exit(1)

    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print("Пустой текст")
        sys.exit(1)

    token = load_token()
    if not token:
        print("Нет BOT_TOKEN (и нет token.txt)")
        sys.exit(1)

    path = db_path()
    chats = all_chat_ids(path)
    print(f"База: {path}")
    print(f"Чатов: {len(chats)}")
    if not chats:
        print("Некуда слать. Напиши боту /start в ЛС и в группах.")
        sys.exit(1)

    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    ok = fail = 0
    for chat_id in chats:
        try:
            await bot.send_message(chat_id, text)
            ok += 1
            print(f"  OK  {chat_id}")
        except Exception as e:
            fail += 1
            print(f"  FAIL {chat_id}: {e}")
        await asyncio.sleep(0.05)  # не упираться в лимиты Telegram

    await bot.session.close()
    print(f"Готово: отправлено {ok}, ошибок {fail}")


if __name__ == "__main__":
    asyncio.run(main())
