import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ContentType
from aiogram.filters import Command

# --- SOZLAMALAR ---
TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"
CHANNEL_ID = -1004136665979  # Sizning kanal ID raqamingiz

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 1. Ma'lumotlar bazasini yaratish (Animes va Episodes jadvallari)
def db_start():
    conn = sqlite3.connect("animelar.db")
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

# 2. /START BOSGANDA QO'LLANMA CHIQARISH
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    guide_text = (
        f"Salom, {message.from_user.first_name}!\n\n"
        "<b>Qoʻllanma!!!</b>\n\n"
        "1️⃣ Anime nomini yozasiz.\n\n"
        "2️⃣ Keyingi qismni koʻrish uchun qism raqamini yuborasiz. "
        "Masalan: <b>1</b> desangiz 1-qism tashlanadi, <b>2</b> desangiz 2-qism tashlanadi va hokazo...\n\n"
        "3️⃣ Animelardan rohatlaning! 🍿"
    )
    await message.answer(guide_text, parse_mode="HTML")

# 3. Kanalga video tashlansa, avtomatik bazaga saqlash
@dp.channel_post(F.content_type == ContentType.VIDEO)
async def auto_save_anime(message: types.Message):
    if message.chat.id == CHANNEL_ID:
        caption = message.caption or ""
        file_id = message.video.file_id
        
        anime_title = ""
        ep_num = 1
        
        # Izohdan nom va qismni ajratib olish (Masalan: "Naruto | 1" yoki "Naruto [1-qism]")
        if "|" in caption:
            parts = caption.split("|")
            anime_title = parts[0].strip()
            digits = "".join(filter(str.isdigit, parts[1]))
            if digits:
                ep_num = int(digits)
        elif "[" in caption and "]" in caption:
            anime_title = caption.split("[")[0].strip()
            digits = "".join(filter(str.isdigit, caption.split("[")[1]))
            if digits:
                ep_num = int(digits)
        else:
            anime_title = caption.strip() or "nomsiz anime"

        conn = sqlite3.connect("animelar.db")
        cursor = conn.cursor()
        
        # Animeni bazadan qidiramiz, yo'q bo'lsa qo'shamiz
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
            "SELECT id FROM episodes WHERE anime_id = ? AND episode_number = ?", 
            (anime_id, ep_num)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO episodes (anime_id, episode_number, file_id) VALUES (?, ?, ?)", 
                (anime_id, ep_num, file_id)
            )
            conn.commit()
            print(f"Avtomatik saqlandi: {anime_title} — {ep_num}-qism")
            
        conn.close()

# 4. Foydalanuvchi botga yozganda (Anime nomi yoki qism raqami)
@dp.message(F.text & ~F.text.startswith("/"))
async def search_anime(message: types.Message):
    text = message.text.strip()
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    
    # Agar foydalanuvchi faqat raqam yozgan bo'lsa (masalan: "2", "3")
    if text.isdigit():
        target_ep = int(text)
        cursor.execute("""
            SELECT A.id, A.title, E.file_id 
            FROM episodes E 
            JOIN animes A ON E.anime_id = A.id 
            WHERE E.episode_number = ?
        """, (target_ep,))
        results = cursor.fetchall()
        
        if results and len(results) == 1:
            anime_id, anime_title, file_id = results[0]
            
            # Keyingi qism borligini tekshiramiz
            cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = ?", (anime_id, target_ep + 1))
            has_next = cursor.fetchone()[0] > 0
            conn.close()
            
            caption = f"🎬 <b>{anime_title}</b> — {target_ep}-qism\n\n@barcha_animelar_shuyerda_bot"
            if has_next:
                caption += f"\n\n👉 Keyingi qismni ({target_ep + 1}-qism) ko'rmoqchi bo'lsangiz, <b>{target_ep + 1}</b> raqamini yuboring."
                
            await message.answer_video(video=file_id, caption=caption, parse_mode="HTML")
            return
        else:
            conn.close()
            await message.answer("❌ Bu raqamdagi qism topilmadi. Iltimos, avval anime nomini yuboring.")
            return

    # Odatiy holat: Anime nomini yozganda (masalan: Naruto) -> 1-qismni chiqarish
    cursor.execute("SELECT id, title FROM animes WHERE title LIKE ?", (f"%{text}%",))
    anime = cursor.fetchone()
    
    if not anime:
        conn.close()
        await message.answer("❌ Kechirasiz, bu nomdagi anime topilmadi.")
        return
        
    anime_id, anime_title = anime
    
    # Har doim 1-qismni olamiz
    cursor.execute(
        "SELECT file_id FROM episodes WHERE anime_id = ? AND episode_number = 1", 
        (anime_id,)
    )
    episode = cursor.fetchone()
    
    if not episode:
        conn.close()
        await message.answer(f"🎬 <b>{anime_title}</b> topildi, lekin 1-qismi hali yuklanmagan.", parse_mode="HTML")
        return
        
    file_id = episode[0]
    
    # 2-qism borligini tekshiramiz
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = 2", (anime_id,))
    has_next = cursor.fetchone()[0] > 0
    conn.close()
    
    caption = f"🎬 <b>{anime_title}</b> — 1-qism\n\n@barcha_animelar_shuyerda_bot"
    if has_next:
        caption += "\n\n👉 Ikkinchi qismni ko'rmoqchi bo'lsangiz, <b>2</b> raqamini yuboring."
        
    await message.answer_video(video=file_id, caption=caption, parse_mode="HTML")

# Botni ishga tushirish
async def main():
    db_start()
    print("Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
    
