import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- SOZLAMALAR ---
BOT_TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"
CHANNEL_ID = "-1004301284199"
ADMIN_ID = 8113271428  # Sizning Telegram ID raqamingiz
DB_NAME = "animelar.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Holatlar (FSM) - Video qo'shish jarayoni uchun
class AddAnimeState(StatesGroup):
    waiting_for_title = State()
    waiting_for_episode = State()

# --- BAZANI YARATISH ---
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
    conn.close()

# --- START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Salom, {message.from_user.first_name}!\n"
        "Animix botiga xush kelibsiz. Ko'rmoqchi bo'lgan animengiz nomini yozing (masalan: Naruto).\n\n"
        "📹 *Admin uchun:* Bazaga video qo'shish uchun /add buyrug'ini bosing."
    )

# --- ADMIN: VIDEO QO'SHISHNI BOSHLASH ---
@dp.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Kechirasiz, bu buyruq faqat admin uchun.")
        return
    
    await message.answer("🎬 Iltimos, bazaga qo'shmoqchi bo'lgan **videoni** yuboring (yoki kanaldan forward qilib tashlang):")
    # Videoni kutish holatiga o'tamiz
    dp.message.register(receive_video, F.video)

# Videoni qabul qilish
async def receive_video(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    file_id = message.video.file_id
    await state.update_data(file_id=file_id)
    
    await message.answer("✍️ Endi bu anime nomini yozing (masalan: Naruto):")
    await state.set_state(AddAnimeState.waiting_for_title)

# Anime nomini olish
@dp.message(AddAnimeState.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    anime_title = message.text.strip()
    await state.update_data(anime_title=anime_title)
    
    await message.answer("🔢 Endi bu videoning **nechanchi qism** ekanini raqamda yozing (masalan: 1):")
    await state.set_state(AddAnimeState.waiting_for_episode)

# Qism raqamini olish va bazaga saqlash
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
    
    # Animeni bazadan qidiramiz, yo'q bo'lsa yangi qo'shamiz
    cursor.execute("SELECT id FROM animes WHERE title LIKE ?", (anime_title,))
    anime = cursor.fetchone()
    
    if anime:
        anime_id = anime[0]
    else:
        cursor.execute("INSERT INTO animes (title) VALUES (?)", (anime_title,))
        conn.commit()
        anime_id = cursor.lastrowid
    
    # Qismni bazaga yozamiz
    cursor.execute(
        "INSERT INTO episodes (anime_id, episode_number, file_id) VALUES (?, ?, ?)", 
        (anime_id, ep_num, file_id)
    )
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(f"✅ Muvaffaqiyatli saqlandi!\n🎬 Anime: {anime_title}\n📌 Qism: {ep_num}-qism")

# --- ANIME QIDIRISH (Foydalanuvchilar uchun) ---
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
    
    # Keyingi qism borligini tekshiramiz
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = ?", (anime_id, ep_num + 1))
    has_next = cursor.fetchone()[0] > 0
    conn.close()
    
    builder = InlineKeyboardBuilder()
    if has_next:
        builder.button(text=f"➡️ {ep_num + 1}-qismga o'tish", callback_data=f"ep_{anime_id}_{ep_num + 1}")
    
    try:
        await message.answer_video(
            video=file_id, 
            caption=f"🎬 {anime_title} — {ep_num}-qism", 
            reply_markup=builder.as_markup() if has_next else None
        )
    except Exception as e:
        await message.answer(f"Xatolik: {e}")

# --- TUGMA BOSILGANDA KEYINGI QISMNI CHIQARISH ---
@dp.callback_query(F.data.startswith("ep_"))
async def show_next_episode(callback: types.CallbackQuery):
    data = callback.data.split("_")
    anime_id = data[1]
    target_ep = int(data[2])
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT title FROM animes WHERE id = ?", (anime_id,))
    anime_res = cursor.fetchone()
    anime_title = anime_res[0] if anime_res else "Anime"
    
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
    
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = ?", (anime_id, target_ep + 1))
    has_next = cursor.fetchone()[0] > 0
    conn.close()
    
    builder = InlineKeyboardBuilder()
    if has_next:
        builder.button(text=f"➡️ {target_ep + 1}-qismga o'tish", callback_data=f"ep_{anime_id}_{target_ep + 1}")
    
    try:
        await callback.message.answer_video(
            video=file_id, 
            caption=f"🎬 {anime_title} — {target_ep}-qism", 
            reply_markup=builder.as_markup() if has_next else None
        )
    except Exception as e:
        await callback.message.answer(f"Xatolik: {e}")
    
    await callback.answer()

async def main():
    init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
