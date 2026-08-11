import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- SOZLAMALAR ---
BOT_TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"
CHANNEL_ID = -1004136665979  # Yangi kanal ID raqamingiz o'rnatildi
ADMIN_ID = 4301284199  # Sizning ID raqamingiz
DB_NAME = "animelar.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddAnimeState(StatesGroup):
    waiting_for_video = State()
    waiting_for_title = State()
    waiting_for_episode = State()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS animes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL COLLATE NOCASE
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
    conn.commit()
    conn.close()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Salom, {message.from_user.first_name}!\n"
        "Animix botiga xush kelibsiz. Ko'rmoqchi bo'lgan animengiz nomini yozing (masalan: Naruto).\n\n"
        "📹 *Admin uchun:* Bazaga video qo'shish uchun /add buyrug'ini bosing."
    )

# --- ADMIN: VIDEO QO'SHISH ---
@dp.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Kechirasiz, bu buyruq faqat admin uchun.")
        return
    
    await message.answer("🎬 Iltimos, bazaga qo'shmoqchi bo'lgan **videoni** yuboring:")
    await state.set_state(AddAnimeState.waiting_for_video)

@dp.message(AddAnimeState.waiting_for_video, F.video)
async def process_video(message: types.Message, state: FSMContext):
    file_id = message.video.file_id
    await state.update_data(file_id=file_id)
    
    await message.answer("✍️ Endi bu anime nomini yozing (masalan: Naruto):")
    await state.set_state(AddAnimeState.waiting_for_title)

@dp.message(AddAnimeState.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    anime_title = message.text.strip()
    await state.update_data(anime_title=anime_title)
    
    await message.answer("🔢 Endi bu videoning **nechanchi qism** ekanini raqamda yozing (masalan: 1):")
    await state.set_state(AddAnimeState.waiting_for_episode)

@dp.message(AddAnimeState.waiting_for_episode)
async def process_episode(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Iltimos, faqat raqam kiriting (masalan: 1):")
        return
    
    ep_num = int(message.text)
    data = await state.get_data()
    file_id = data["file_id"]
    anime_title = data["anime_title"]
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM animes WHERE title LIKE ?", (anime_title,))
    anime = cursor.fetchone()
    
    if anime:
        anime_id = anime[0]
    else:
        cursor.execute("INSERT INTO animes (title) VALUES (?)", (anime_title,))
        conn.commit()
        anime_id = cursor.lastrowid
    
    cursor.execute(
        "INSERT INTO episodes (anime_id, episode_number, file_id) VALUES (?, ?, ?)", 
        (anime_id, ep_num, file_id)
    )
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(f"✅ Muvaffaqiyatli saqlandi!\n🎬 Anime: {anime_title}\n📌 Qism: {ep_num}-qism")

# --- FOYDALANUVCHILAR UCHUN: ANIME QIDIRISH ---
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
    
    cursor.execute(
        "SELECT file_id FROM episodes WHERE anime_id = ? AND episode_number = 1", 
        (anime_id,)
    )
    episode = cursor.fetchone()
    
    if not episode:
        conn.close()
        await message.answer(f"🎬 <b>{anime_title}</b> topildi, lekin 1-qismi hali bazaga yuklanmagan.", parse_mode="HTML")
        return
    
    file_id = episode[0]
    
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = 2", (anime_id,))
    has_next = cursor.fetchone()[0] > 0
    conn.close()
    
    caption = f"🎬 <b>{anime_title} — 1-qism</b>"
    if has_next:
        caption += "\n\n👉 Ikkinchi qismni ko'rmoqchi bo'lsangiz, <b>2</b> raqamini yuboring."
    
    try:
        await message.answer_video(video=file_id, caption=caption, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Videoni yuborishda xatolik: {e}")

async def main():
    init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
