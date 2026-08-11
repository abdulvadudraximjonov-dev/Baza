import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- SOZLAMALAR ---
BOT_TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"
CHANNEL_ID = "-1004301284199"
DB_NAME = "animelar.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZANI TEKSHIRISH ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS animes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER,
            episode_number INTEGER,
            file_id TEXT NOT NULL,
            FOREIGN KEY (anime_id) REFERENCES animes (id)
        )
    """)
    
    # Test uchun bitta anime va 3 ta qism qo'shamiz (agar bazada bo'lmasa)
    cursor.execute("SELECT COUNT(*) FROM animes")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO animes (title) VALUES ('Naruto')")
        anime_id = cursor.lastrowid
        # Bu yerga o'zingizning test file_id laringizni qo'yishingiz mumkin
        cursor.execute("INSERT INTO episodes (anime_id, episode_number, file_id) VALUES (?, 1, 'TEST_FILE_ID_1')", (anime_id,))
        cursor.execute("INSERT INTO episodes (anime_id, episode_number, file_id) VALUES (?, 2, 'TEST_FILE_ID_2')", (anime_id,))
        cursor.execute("INSERT INTO episodes (anime_id, episode_number, file_id) VALUES (?, 3, 'TEST_FILE_ID_3')", (anime_id,))
        conn.commit()
        
    conn.close()

# --- START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Salom, {message.from_user.first_name}!\n"
        "Animix botiga xush kelibsiz. Ko'rmoqchi bo'lgan animengiz nomini yozing (masalan: Naruto)."
    )

# --- ANIME QIDIRISH (Faqat 1-qismni chiqarish) ---
@dp.message(F.text & ~F.text.startswith("/"))
async def search_anime(message: types.Message):
    query_text = message.text.strip()
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM animes WHERE title LIKE ?", (f"%{query_text}%",))
    anime = cursor.fetchone()
    
    if not anime:
        conn.close()
        await message.answer("❌ Bunday nomdagi anime topilmadi.")
        return
    
    anime_id, anime_title = anime
    
    # Faqat 1-qismni olamiz
    cursor.execute(
        "SELECT episode_number, file_id FROM episodes WHERE anime_id = ? AND episode_number = 1", 
        (anime_id,)
    )
    episode = cursor.fetchone()
    conn.close()
    
    if not episode:
        await message.answer(f"🎬 **{anime_title}** topildi, lekin 1-qismi hali yuklanmagan.")
        return
    
    ep_num, file_id = episode
    
    # Keyingi qism (2-qism) mavjudligini tekshiramiz
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = ?", (anime_id, ep_num + 1))
    has_next = cursor.fetchone()[0] > 0
    conn.close()
    
    # Tugma yasaymiz
    builder = InlineKeyboardBuilder()
    if has_next:
        builder.button(text=f"➡️ {ep_num + 1}-qismga o'tish", callback_data=f"ep_{anime_id}_{ep_num + 1}")
    
    try:
        await message.answer_video(
            video=file_id, 
            caption=f"🎬 {anime_title} — {ep_num}-qism", 
            reply_markup=builder.as_markup() if has_next else None
        )
    except Exception:
        # Agar test file_id ishlamasa, matn sifatida ko'rsatib turadi
        await message.answer(
            f"🎬 {anime_title} — {ep_num}-qism (Video fayl topilmadi, lekin qism bazada bor)", 
            reply_markup=builder.as_markup() if has_next else None
        )

# --- TUGMA BOSILGANDA KEYINGI QISMNI CHIQARISH ---
@dp.callback_query(F.data.startswith("ep_"))
async def show_next_episode(callback: types.CallbackQuery):
    data = callback.data.split("_")
    anime_id = data[1]
    target_ep = int(data[2])
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Anime nomini olish
    cursor.execute("SELECT title FROM animes WHERE id = ?", (anime_id,))
    anime_res = cursor.fetchone()
    anime_title = anime_res[0] if anime_res else "Anime"
    
    # Kerakli qismni olish
    cursor.execute(
        "SELECT file_id FROM episodes WHERE anime_id = ? AND episode_number = ?", 
        (anime_id, target_ep)
    )
    ep = cursor.fetchone()
    
    if not ep:
        conn.close()
        await callback.answer("❌ Bu qism topilmadi yoki tugadi.", show_alert=True)
        return
    
    file_id = ep[0]
    
    # Undan keyingi qism bor-yo'qligini tekshirish
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = ?", (anime_id, target_ep + 1))
    has_next = cursor.fetchone()[0] > 0
    conn.close()
    
    # Yangi tugma yasash
    builder = InlineKeyboardBuilder()
    if has_next:
        builder.button(text=f"➡️ {target_ep + 1}-qismga o'tish", callback_data=f"ep_{anime_id}_{target_ep + 1}")
    
    try:
        await callback.message.answer_video(
            video=file_id, 
            caption=f"🎬 {anime_title} — {target_ep}-qism", 
            reply_markup=builder.as_markup() if has_next else None
        )
    except Exception:
        await callback.message.answer(
            f"🎬 {anime_title} — {target_ep}-qism", 
            reply_markup=builder.as_markup() if has_next else None
        )
    
    await callback.answer()

async def main():
    init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
