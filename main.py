import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ContentType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- SOZLAMALAR ---
TOKEN = "8905864709:AAHz1g4blQ9SzBb3WNTBu_MnneeCXM7VSj8"
CHANNEL_ID = -1004301284199
REQUIRED_CHANNEL_ID = -1004301284199
INVITE_LINK = "https://t.me/+RmKZ8tZOEwFlZmZi"
ADMIN_ID = 8113271428

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Holatlar (FSM)
class Form(StatesGroup):
    waiting_for_admin_message = State()
    waiting_for_zayafka = State()
    adding_title = State()
    adding_photo = State()
    adding_desc = State()
    ep_anime_id = State()
    ep_number = State()
    ep_file = State()

# Ma'lumotlar bazasini yaratish
def db_start():
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS join_requests (
            user_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            photo_file_id TEXT,
            description TEXT
        )
    """)
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
    @dp.chat_join_request()
async def handle_join_request(update: types.ChatJoinRequest):
    if update.chat.id == REQUIRED_CHANNEL_ID:
        user_id = update.from_user.id
        conn = sqlite3.connect("animelar.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO join_requests (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()

async def check_subscription(user_id: int) -> bool:
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM join_requests WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return True
        
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
    except Exception:
        pass
        
    return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        builder = InlineKeyboardBuilder()
        builder.button(text="📢 Kanalga qo'shilish so'rovi (Zayafka)", url=INVITE_LINK)
        builder.button(text="🔄 Tekshirish", callback_data="check_sub")
        builder.adjust(1)
        
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanalimizga zayafka tashlang va keyin 'Tekshirish' tugmasini bosing:",
            reply_markup=builder.as_markup()
        )
        return

    await show_main_menu(message)

@dp.callback_query(F.data == "check_sub")
async def verify_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        await callback.answer("❌ Siz hali kanalga zayafka tashlamagansiz!", show_alert=True)
        return
    
    await callback.message.delete()
    await callback.message.answer("Rahmat! Zayafkangiz tasdiqlandi. Endi botdan foydalanishingiz mumkin.")
    await show_main_menu(callback.message)
    await callback.answer()

async def show_main_menu(message: types.Message):
    user_id = message.from_user.id
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Anime qidiruv", callback_data="search_anime_menu")
    builder.button(text="📝 Zayafka qoldirish", callback_data="make_zayafka")
    builder.button(text="👨‍💻 Admin bilan bog'lanish", callback_data="contact_admin")
    
    if user_id == ADMIN_ID:
        builder.button(text="➕ Anime qo'shish", callback_data="admin_add_anime")
        builder.button(text="➕ Qism (Seriya) qo'shish", callback_data="admin_add_episode")
        
    builder.adjust(1)
    
    await message.answer(
        "Salom! Botimizga xush kelibsiz. Kerakli bo'limni tanlang:",
        reply_markup=builder.as_markup()
    )

# --- ADMIN: ANIME VA QISM QO'SHISH ---
@dp.callback_query(F.data == "admin_add_anime")
async def start_add_anime(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer("🎬 Yangi anime nomini kiriting:")
    await state.set_state(Form.adding_title)
    await callback.answer()

@dp.message(Form.adding_title)
async def process_anime_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("🖼 Endi anime uchun rasm (foto) yuboring:")
    await state.set_state(Form.adding_photo)

@dp.message(Form.adding_photo, F.content_types == ContentType.PHOTO)
async def process_anime_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await message.answer("📝 Anime haqida qisqacha ma'lumot yuboring:")
    await state.set_state(Form.adding_desc)

@dp.message(Form.adding_desc)
async def process_anime_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data.get("title")
    photo = data.get("photo")
    desc = message.text
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO anime (title, photo_file_id, description) VALUES (?, ?, ?)", (title, photo, desc))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ <b>{title}</b> animeri bazaga muvaffaqiyatli qo'shildi!")
    await state.clear()

@dp.callback_query(F.data == "admin_add_episode")
async def start_add_episode(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM anime")
    animelar = cursor.fetchall()
    conn.close()
    
    if not animelar:
        await callback.answer("❌ Avval bazaga anime qo'shishingiz kerak!", show_alert=True)
        return
        
    builder = InlineKeyboardBuilder()
    for anime_id, title in animelar:
        builder.button(text=title, callback_data=f"select_anime_for_ep_{anime_id}")
    builder.adjust(1)
    
    await callback.message.answer("Qaysi animega qism qo'shmoqchisiz? Tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("select_anime_for_ep_"))
async def select_anime_ep(callback: types.CallbackQuery, state: FSMContext):
    anime_id = callback.data.split("_")[-1]
    await state.update_data(anime_id=anime_id)
    await callback.message.answer("🔢 Nechanchi qism ekanini raqam bilan yozing (masalan: 1):")
    await state.set_state(Form.ep_number)
    await callback.answer()

@dp.message(Form.ep_number)
async def process_ep_number(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Iltimos, faqat raqam kiriting (masalan: 1):")
        return
    await state.update_data(ep_num=int(message.text))
    await message.answer("📹 Endi o'sha qismning video faylini yuboring:")
    await state.set_state(Form.ep_file)

@dp.message(Form.ep_file, F.content_types == ContentType.VIDEO)
async def process_ep_file(message: types.Message, state: FSMContext):
    file_id = message.video.file_id
    data = await state.get_data()
    anime_id = data.get("anime_id")
    ep_num = data.get("ep_num")
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO episodes (anime_id, episode_number, file_id) VALUES (?, ?, ?)", (anime_id, ep_num, file_id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Anime uchun {ep_num}-qism muvaffaqiyatli qo'shildi!")
    await state.clear()
        @dp.callback_query(F.data == "make_zayafka")
async def start_zayafka(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Qaysi animeni ko'rishni xohlaysiz? Anime nomini va qismlarini yozib yuboring:")
    await state.set_state(Form.waiting_for_zayafka)
    await callback.answer()

@dp.callback_query(F.data == "contact_admin")
async def ask_admin_message(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Adminga yubormoqchi bo'lgan xabaringizni yozib yuboring:")
    await state.set_state(Form.waiting_for_admin_message)
    await callback.answer()

@dp.message(F.text)
async def receive_zayafka_or_admin(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == "Form:waiting_for_zayafka":
        user = message.from_user
        zayafka_text = f"📋 <b>Yangi Anime Zayavkasi!</b>\n\n👤 <b>Kimdan:</b> {user.full_name} (@{user.username or 'yo\'q'})\n🆔 <b>ID:</b> <code>{user.id}</code>\n\n🎬 <b>Mazmuni:</b> {message.text}"
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=zayafka_text)
            await message.answer("✅ Zayafkangiz adminga yuborildi!")
        except Exception:
            await message.answer("❌ Xatolik yuz berdi.")
        await state.clear()
    elif current_state == "Form:waiting_for_admin_message":
        user = message.from_user
        user_info = f"📩 <b>Yangi xabar keldi!</b>\n\n👤 <b>Kimdan:</b> {user.full_name} (@{user.username or 'yo\'q'}) \n🆔 <b>ID:</b> <code>{user.id}</code>\n\n💬 <b>Xabar:</b> {message.text}"
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=user_info)
            await message.answer("✅ Xabaringiz adminga yuborildi!")
        except Exception:
            await message.answer("❌ Xatolik yuz berdi.")
        await state.clear()

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
        builder.button(text=title, callback_data=f"anime_{anime_id}")
    
    builder.adjust(1)
    await callback.message.edit_text("📋 Mavjud animelar ro'yxati:", reply_markup=builder.as_markup())

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
        builder.button(text="▶️ Tomosha qilish", callback_data=f"episodes_{anime_id}_0")
        builder.adjust(1)
        
        caption = f"🎬 <b>{title}</b>\n\n{desc or ''}"
        
        if photo_id:
            await callback.message.answer_photo(photo=photo_id, caption=caption, reply_markup=builder.as_markup())
        else:
            await callback.message.answer(text=caption, reply_markup=builder.as_markup())
            
        await callback.answer()

@dp.callback_query(F.data.startswith("episodes_"))
async def show_episodes(callback: types.CallbackQuery):
    data = callback.data.split("_")
    anime_id = data[1]
    offset = int(data[2])
    
    conn = sqlite3.connect("animelar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT episode_number, file_id FROM episodes WHERE anime_id = ? LIMIT 10 OFFSET ?", (anime_id, offset))
    episodes = cursor.fetchall()
    conn.close()
    
    if not episodes:
        await callback.answer("❌ Bu animening boshqa qismlari yo'q.", show_alert=True)
        return
    
    for ep_num, file_id in episodes:
        await callback.message.answer_video(video=file_id, caption=f"{ep_num}-qism")
    
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

async def main():
    db_start()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
