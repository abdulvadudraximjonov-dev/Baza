import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ContentType
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- SOZLAMALAR ---
TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"
CHANNEL_ID = -1004301284199

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 1. Ma'lumotlar bazasini yaratish (Animelar va qismlar uchun)
def db_start():
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    # Anime bosh sahifasi uchun
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            photo_file_id TEXT,
            description TEXT
        )
    """)
    # Anime qismlari (seriyalari) uchun
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER,
            episode_number INTEGER,
            file_id TEXT
        )
    """)
    conn.commit()
    conn.close()

# 2. Start buyrug'i va Asosiy menyu (Tugmalar)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Anime qidiruv", callback_data="search_anime_menu")
    builder.adjust(1)
    
    await message.answer(
        "Salom! Botimizga xush kelibsiz. Anime ko'rish uchun quyidagi tugmani bosing:",
        reply_markup=builder.as_markup()
    )

# 3. "Anime qidiruv" tugmasi bosilganda mavjud animelar ro'yxatini chiqarish
@dp.callback_query(F.data == "search_anime_menu")
async def show_anime_list(callback: types.CallbackQuery):
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM anime")
    animelar = cursor.fetchall()
    conn.close()
    
    if not animelar:
        await callback.message.edit_text("❌ Hozircha bazada animelar mavjud emas.")
        return
    
    builder = InlineKeyboardBuilder()
    for anime_id, title in animelar:
        # Har bir anime uchun alohida tugma (bosilganda o'sha anime ID raqami ketadi)
        builder.button(text=title, callback_data=f"anime_{anime_id}")
    
    builder.adjust(1)
    await callback.message.edit_text("📋 Mavjud animelar ro'yxati:", reply_markup=builder.as_markup())

# 4. Anime tanlanganda uning rasmi va "Tomosha qilish" tugmasini yuborish
@dp.callback_query(F.data.startswith("anime_"))
async def show_anime_detail(callback: types.CallbackQuery):
    anime_id = callback.data.split("_")[1]
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, photo_file_id, description FROM anime WHERE id = ?", (anime_id,))
    anime = cursor.fetchone()
    conn.close()
    
    if anime:
        title, photo_id, desc = anime
        builder = InlineKeyboardBuilder()
        # Tomosha qilish tugmasi (1-sahifa, ya'ni 1-10 qismlar uchun)
        builder.button(text="▶️ Tomosha qilish", callback_data=f"episodes_{anime_id}_0")
        builder.adjust(1)
        
        caption = f"🎬 <b>{title}</b>\n\n{desc or ''}"
        
        if photo_id:
            await callback.message.answer_photo(photo=photo_id, caption=caption, reply_markup=builder.as_markup())
        else:
            await callback.message.answer(text=caption, reply_markup=builder.as_markup())
            
        await callback.answer()

# 5. Qismlarni 10 tadan qilib sahifalab yuborish (Pagination)
@dp.callback_query(F.data.startswith("episodes_"))
async def show_episodes(callback: types.CallbackQuery):
    data = callback.data.split("_")
    anime_id = data[1]
    offset = int(data[2])  # Nechanchi qismdan boshlanishi (0, 10, 20...)
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    # 10 tadan qismni olish
    cursor.execute("SELECT episode_number, file_id FROM episodes WHERE anime_id = ? LIMIT 10 OFFSET ?", (anime_id, offset))
    episodes = cursor.fetchall()
    conn.close()
    
    if not episodes:
        await callback.answer("❌ Bu animening boshqa qismlari yo'q.", show_alert=True)
        return
    
    # Qismlarni foydalanuvchiga ketma-ket yuborish
    for ep_num, file_id in episodes:
        await callback.message.answer_video(video=file_id, caption=f"{ep_num}-qism")
    
    # Agar 10 tadan ko'p qism qolgan bo'lsa, "Keyingi 10 talik" tugmasini chiqarish
    next_offset = offset + 10
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number > ?", (anime_id, next_offset - 10))
    count = cursor.fetchone()[0]
    conn.close()
    
    if count > 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="➡️ Keyingi 10 talik", callback_data=f"episodes_{anime_id}_{next_offset}")
        await callback.message.answer("Boshqa qismlarni ko'rish uchun bosing:", reply_markup=builder.as_markup())
    
    await callback.answer()

# Botni ishga tushirish
async def main():
    db_start()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
    
