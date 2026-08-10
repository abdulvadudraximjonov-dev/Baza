import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ContentType

# --- SOZLAMALAR ---
TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"  # Yangilangan token
CHANNEL_ID = -1004301284199  # Sizning kanal ID raqamingiz

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 1. Ma'lumotlar bazasini yaratish
def db_start():
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            file_id TEXT
        )
    """)
    conn.commit()
    conn.close()

# 2. Kanalga video tashlansa, avtomatik bazaga saqlash
@dp.channel_post(F.content_type == ContentType.VIDEO)
async def auto_save_anime(message: types.Message):
    if message.chat.id == CHANNEL_ID:
        file_id = message.video.file_id
        title = message.caption or "Nomsiz anime"
        
        conn = sqlite3.connect("animelar.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO movies (title, file_id) VALUES (?, ?)", (title.lower(), file_id))
        conn.commit()
        conn.close()
        
        print(f"Yangi anime bazaga qo'shildi: {title}")

# 3. Foydalanuvchi botga yozganda qidirib topib berish
@dp.message(F.text & ~F.text.startswith("/"))
async def search_anime(message: types.Message):
    query = message.text.lower()
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, file_id FROM movies WHERE title LIKE ?", (f"%{query}%",))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        title, file_id = result
        await message.answer_video(
            video=file_id,
            caption=f"🎬 <b>{title}</b>\n\n@barcha_animelar_shuyerda_bot"
        )
    else:
        await message.answer("❌ Kechirasiz, bu nomdagi anime topilmadi.")

# Botni ishga tushirish
async def main():
    db_start()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
    
