import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ContentType

# --- SOZLAMALAR ---
TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"
CHANNEL_ID = -1004301284199  # Sizning kanal ID raqamingiz

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 1. Ma'lumotlar bazasini yaratish (Animelar va Qismlar jadvali)
def db_start():
    conn = sqlite3.connect("animelar.db")
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
    conn.commit()
    conn.close()

# 2. Kanalga video tashlansa, avtomatik bazaga saqlash
# Izoh formati shunday bo'lishi kerak: Anime Nomi | Qism Raqami (Masalan: Naruto | 1)
@dp.channel_post(F.content_type == ContentType.VIDEO)
async def auto_save_anime(message: types.Message):
    if message.chat.id == CHANNEL_ID:
        caption = message.caption
        if not caption or "|" not in caption:
            return  # Agar format mos kelmasa tashlab yuboradi
        
        try:
            parts = caption.split("|")
            anime_title = parts[0].strip().lower()
            ep_num = int(parts[1].strip())
            file_id = message.video.file_id
        except Exception:
            return

        conn = sqlite3.connect("animelar.db")
        cursor = conn.cursor()
        
        # Animeni bazadan qidiramiz, yo'q bo'lsa ochamiz
        cursor.execute("SELECT id FROM animes WHERE title = ?", (anime_title,))
        anime = cursor.fetchone()
        
        if anime:
            anime_id = anime[0]
        else:
            cursor.execute("INSERT INTO animes (title) VALUES (?)", (anime_title,))
            conn.commit()
            anime_id = cursor.lastrowid
            
        # Qismni bazaga yozamiz (agar shu qism oldin yozilgan bo'lmasa)
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
            print(f"Yangi qo'shildi: {anime_title} — {ep_num}-qism")
            
        conn.close()

# 3. Foydalanuvchi botga yozganda (Anime nomi yoki qism raqami)
@dp.message(F.text & ~F.text.startswith("/"))
async def search_anime(message: types.Message):
    text = message.text.strip().lower()
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    
    # Agar foydalanuvchi raqam yozgan bo'lsa (masalan: "2", "3")
    if text.isdigit():
        target_ep = int(text)
        # Hozircha oddiy qidiruv: shu qism raqami bor bo'lgan animelarni tekshiramiz
        cursor.execute("""
            SELECT A.id, A.title, E.file_id 
            FROM episodes E 
            JOIN animes A ON E.anime_id = A.id 
            WHERE E.episode_number = ?
        """, (target_ep,))
        # Soddaroq ishlashi uchun oxirgi qidirilgan yoki mos kelganini olamiz
        results = cursor.fetchall()
        
        if results and len(results) == 1:
            anime_id, anime_title, file_id = results[0]
            
            # Undan keyingi qism borligini tekshiramiz
            cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = ?", (anime_id, target_ep + 1))
            has_next = cursor.fetchone()[0] > 0
            conn.close()
            
            caption = f"🎬 <b>{anime_title.title()}</b> — {target_ep}-qism\n\n@barcha_animelar_shuyerda_bot"
            if has_next:
                caption += f"\n\n👉 Keyingi qismni ({target_ep + 1}-qism) ko'rmoqchi bo'lsangiz, <b>{target_ep + 1}</b> raqamini yuboring."
                
            await message.answer_video(video=file_id, caption=caption, parse_mode="HTML")
            return
        else:
            conn.close()
            await message.answer("❌ Bu raqamdagi qism topilmadi yoki bir nechta mos keldi. Iltimos, avval anime nomini to'liq yuboring.")
            return

    # Odatiy holat: Foydalanuvchi anime nomini yozdi (masalan: Naruto)
    cursor.execute("SELECT id, title FROM animes WHERE title LIKE ?", (f"%{text}%",))
    anime = cursor.fetchone()
    
    if not anime:
        conn.close()
        await message.answer("❌ Kechirasiz, bu nomdagi anime topilmadi.")
        return
        
    anime_id, anime_title = anime
    
    # Har doim faqat 1-qismni olamiz
    cursor.execute(
        "SELECT file_id FROM episodes WHERE anime_id = ? AND episode_number = 1", 
        (anime_id,)
    )
    episode = cursor.fetchone()
    
    if not episode:
        conn.close()
        await message.answer(f"🎬 <b>{anime_title.title()}</b> topildi, lekin 1-qismi hali yuklanmagan.", parse_mode="HTML")
        return
        
    file_id = episode[0]
    
    # 2-qism borligini tekshiramiz
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_id = ? AND episode_number = 2", (anime_id,))
    has_next = cursor.fetchone()[0] > 0
    conn.close()
    
    caption = f"🎬 <b>{anime_title.title()}</b> — 1-qism\n\n@barcha_animelar_shuyerda_bot"
    if has_next:
        caption += "\n\n👉 Ikkinchi qismni ko'rmoqchi bo'lsangiz, <b>2</b> raqamini yuboring."
        
    await message.answer_video(video=file_id, caption=caption, parse_mode="HTML")

# Botni ishga tushirish
async def main():
    db_start()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
    
