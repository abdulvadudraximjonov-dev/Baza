import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- SOZLAMALAR ---
BOT_TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"
CHANNEL_ID = "-1004301284199"  # Telegram kanal ID raqamlari odatda oldiga -100 bilan yoziladi
DB_NAME = "animelar.db"

# Loggingni sozlash
logging.basicConfig(level=logging.INFO)

# Bot va Dispatcher yaratish
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZANI YARATISH VA TEKSHIRISH ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Animelar jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS animes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        )
    """)
    # Qismlar jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER,
            episode_number INTEGER,
            file_id TEXT NOT NULL,
            FOREIGN KEY (anime_id) REFERENCES animes (id)
        )
    """)
    conn.commit()
    conn.close()

# --- START BUYrug'i ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Salom, {message.from_user.first_name}!\n"
        "Animix botiga xush kelibsiz. Anime nomini yozing yoki qism tanlang."
    )

# --- ANIME QISMLARINI 10 TALIK QILIB CHIQARISH ---
@dp.callback_query(F.data.startswith("episodes_"))
async def show_episodes(callback: types.CallbackQuery):
    data = callback.data.split("_")
    anime_id = data[1]
    offset = int(data[2])
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Berilgan animening offset bo'yicha 10 talik qismlarini olamiz
    cursor.execute(
        "SELECT episode_number, file_id FROM episodes WHERE anime_id = ? ORDER BY episode_number ASC LIMIT 10 OFFSET ?", 
        (anime_id, offset)
    )
    episodes = cursor.fetchall()
    
    if not episodes:
        conn.close()
        await callback.answer("❌ Bu animening boshqa qismlari yo'q.", show_alert=True)
        return
    
    # 10 ta qismni ketma-ket yuboramiz
    for ep_num, file_id in episodes:
        try:
            await callback.message.answer_video(video=file_id, caption=f"🎬 {ep_num}-qism")
        except Exception as e:
            logging.error(f"Videoni yuborishda xatolik ({ep_num}-qism): {e}")
    
    # Keyingi 10 talik bormi yoki yo'qligini tekshiramiz
    next_offset = offset + 10
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number > ?", (anime_id, next_offset))
    count = cursor.fetchone()[0]
    conn.close()
    
    # Agar keyingi qismlar mavjud bo'lsa, tugma chiqaramiz
    if count > 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="➡️ Keyingi 10 talik", callback_data=f"episodes_{anime_id}_{next_offset}")
        await callback.message.answer("Boshqa qismlarni ko'rish uchun pastdagi tugmani bosing:", reply_markup=builder.as_markup())
    else:
        await callback.message.answer("🎉 Shu bilan anime qismlari tugadi!")
    
    await callback.answer()

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    init_db()  # Bazani tayyorlash
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
