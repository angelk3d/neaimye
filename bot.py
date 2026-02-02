import os
import logging
import random
import sqlite3
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated

# Получаем токен из переменных окружения
API_TOKEN = os.getenv('BOT_TOKEN')
CREATOR_USERNAME = os.getenv('CREATOR_USERNAME', 'whitestrings')
CREATOR_ID = os.getenv('CREATOR_ID', '8019499675')

if not API_TOKEN:
    logging.error("❌ BOT_TOKEN не найден!")
    exit(1)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language TEXT DEFAULT 'ru',
            verified INTEGER DEFAULT 0,
            registered_date TIMESTAMP,
            last_seen TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT NULL,
            welcome_sent BOOLEAN DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()
logger.info("База данных инициализирована")

# Хранилище для групп, которые ждут приветствия
pending_groups = {}

async def send_welcome_message(group_id, group_title):
    """Пытается отправить приветственное сообщение"""
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"group_lang_ru_{group_id}"),
                    InlineKeyboardButton(text="🇬🇧 English", callback_data=f"group_lang_en_{group_id}")
                ]
            ]
        )
        
        await bot.send_message(
            group_id,
            f"👋 Приветствую в группе '{group_title}'!\n\n"
            f"Выберите язык для общения со мной:\n\n"
            f"👋 Welcome to group '{group_title}'!\n"
            f"Choose language for communication with me:",
            reply_markup=keyboard
        )
        
        # Помечаем в БД, что приветствие отправлено
        conn = sqlite3.connect('bot_users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO groups (group_id, welcome_sent) 
            VALUES (?, 1)
        ''', (group_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Приветствие отправлено в группу {group_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке в группу {group_id}: {e}")
        return False

async def check_and_send_welcome():
    """Проверяет права и отправляет приветствие для всех ожидающих групп"""
    logger.info("🚀 Запущена фоновая задача check_and_send_welcome")
    
    while True:
        try:
            if not pending_groups:
                # Нет групп для проверки, ждем
                await asyncio.sleep(2)
                continue
            
            groups_to_remove = []
            
            for group_id, data in list(pending_groups.items()):
                group_title = data.get('title', 'Группа')
                
                try:
                    # Проверяем права бота
                    bot_member = await bot.get_chat_member(group_id, bot.id)
                    can_send = bot_member.can_send_messages if hasattr(bot_member, 'can_send_messages') else False
                    is_admin = bot_member.status in ['administrator', 'creator']
                    
                    if can_send and is_admin:
                        logger.info(f"✅ Бот имеет права в группе {group_id}")
                        success = await send_welcome_message(group_id, group_title)
                        if success:
                            groups_to_remove.append(group_id)
                    else:
                        logger.info(f"⏳ Бот не имеет прав в группе {group_id} (can_send={can_send}, is_admin={is_admin})")
                except Exception as e:
                    logger.error(f"Ошибка проверки прав в группе {group_id}: {e}")
                    # Если бота нет в группе, удаляем из ожидания
                    if "Chat not found" in str(e) or "bot was kicked" in str(e) or "not found" in str(e):
                        logger.info(f"Бота нет в группе {group_id}, удаляю из ожидания")
                        groups_to_remove.append(group_id)
            
            # Удаляем обработанные группы
            for group_id in groups_to_remove:
                if group_id in pending_groups:
                    del pending_groups[group_id]
            
            # Ждем 2 секунды
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Ошибка в основном цикле проверки: {e}")
            await asyncio.sleep(2)

@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added_to_group(event: ChatMemberUpdated):
    logger.info(f"🔄 Сработал обработчик on_bot_added_to_group")
    
    if event.new_chat_member.user.id == bot.id:
        group_id = event.chat.id
        group_title = event.chat.title
        
        logger.info(f"🤖 Бот добавлен в группу: {group_id} - {group_title}")
        
        # Добавляем группу в список ожидающих
        pending_groups[group_id] = {'title': group_title}
        
        # Сразу пытаемся отправить приветствие
        try:
            bot_member = await bot.get_chat_member(group_id, bot.id)
            can_send = bot_member.can_send_messages if hasattr(bot_member, 'can_send_messages') else False
            is_admin = bot_member.status in ['administrator', 'creator']
            
            if can_send and is_admin:
                logger.info(f"✅ Бот сразу получил права в группе {group_id}")
                await send_welcome_message(group_id, group_title)
                if group_id in pending_groups:
                    del pending_groups[group_id]
            else:
                logger.info(f"⚠️ Бот добавлен без прав (can_send={can_send}, is_admin={is_admin}), жду предоставления прав")
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении бота в группу {group_id}: {e}")

@dp.callback_query(F.data.startswith("group_lang_"))
async def set_group_language_handler(callback: types.CallbackQuery):
    data = callback.data.split("_")
    lang = data[2]
    group_id = int(data[3])
    
    # Сохраняем язык в БД
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO groups (group_id, language) 
        VALUES (?, ?)
    ''', (group_id, lang))
    conn.commit()
    conn.close()
    
    logger.info(f"Язык группы {group_id} установлен: {lang}")
    
    if lang == 'ru':
        text = "✅ Отлично! Я буду общаться на русском языке в этой группе! :3"
    else:
        text = "✅ Great! I will communicate in English in this group! :3"
    
    try:
        await callback.message.edit_text(text)
    except:
        try:
            await bot.send_message(group_id, text)
        except:
            logger.error(f"Не могу отправить сообщение в группу {group_id}")
    
    await callback.answer()

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    logger.info(f"Команда /start от пользователя {user_id} в чате {message.chat.type}")
    
    if message.chat.type == "private":
        # Проверяем пользователя в БД
        conn = sqlite3.connect('bot_users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user:
            # Пользователь уже есть
            lang = user[4] if len(user) > 4 else 'ru'
            
            if lang == 'ru':
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="👤 Мой профиль")],
                        [KeyboardButton(text="🎲 Случайный бред")],
                        [KeyboardButton(text="🌍 Сменить язык")],
                        [KeyboardButton(text="📋 Помощь")]
                    ],
                    resize_keyboard=True
                )
                await message.answer(
                    f"С возвращением, {first_name}! 👋\n"
                    f"Используй кнопки ниже:",
                    reply_markup=keyboard
                )
            else:
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="👤 My profile")],
                        [KeyboardButton(text="🎲 Random nonsense")],
                        [KeyboardButton(text="🌍 Change language")],
                        [KeyboardButton(text="📋 Help")]
                    ],
                    resize_keyboard=True
                )
                await message.answer(
                    f"Welcome back, {first_name}! 👋\n"
                    f"Use buttons below:",
                    reply_markup=keyboard
                )
        else:
            # Новый пользователь
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="start_lang_ru"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data="start_lang_en")
                    ]
                ]
            )
            
            await message.answer(
                "👋 Привет! Добро пожаловать!\n"
                "Пожалуйста, выберите язык:\n\n"
                "👋 Hello! Welcome!\n"
                "Please choose language:",
                reply_markup=keyboard
            )

@dp.callback_query(F.data.startswith("start_lang_"))
async def start_language_handler(callback: types.CallbackQuery):
    lang = callback.data.split("_")[2]
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    last_name = callback.from_user.last_name
    
    logger.info(f"Пользователь {user_id} выбрал язык: {lang}")
    
    # Сохраняем пользователя
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, last_name, language, verified, registered_date, last_seen) 
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
    ''', (user_id, username, first_name, last_name, lang, datetime.now(), datetime.now()))
    conn.commit()
    conn.close()
    
    if lang == 'ru':
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 Мой профиль")],
                [KeyboardButton(text="🎲 Случайный бред")],
                [KeyboardButton(text="🌍 Сменить язык")],
                [KeyboardButton(text="📋 Помощь")]
            ],
            resize_keyboard=True
        )
        
        await callback.message.edit_text("✅ Язык выбран! Теперь ты можешь использовать бота :3")
        await callback.message.answer(
            f"Привет, {first_name}! 👋\n"
            f"Теперь ты можешь использовать бота в группах! :3",
            reply_markup=keyboard
        )
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 My profile")],
                [KeyboardButton(text="🎲 Random nonsense")],
                [KeyboardButton(text="🌍 Change language")],
                [KeyboardButton(text="📋 Help")]
            ],
            resize_keyboard=True
        )
        
        await callback.message.edit_text("✅ Language selected! Now you can use the bot :3")
        await callback.message.answer(
            f"Hello, {first_name}! 👋\n"
            f"Now you can use the bot in groups! :3",
            reply_markup=keyboard
        )
    
    await callback.answer()

@dp.message(F.chat.type == "private")
async def handle_private_messages(message: types.Message):
    user_id = message.from_user.id
    
    if message.text in ["/start", "/help", "/start@neaimybot", "/help@neaimybot"]:
        await cmd_start(message)
        return
    
    # Проверяем пользователя
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await message.answer("Сначала пройди верификацию! Напиши /start :3")
        return
    
    lang = user[4] if len(user) > 4 else 'ru'
    
    if lang == 'ru':
        if message.text == "👤 Мой профиль":
            user_info = f"""
📋 *Твой профиль:*

*Основное:*
├ 🆔 ID: `{user_id}`
├ 👤 Имя: {user[2] if user else message.from_user.first_name}
├ 🏷️ Юзернейм: @{user[1] if user and user[1] else 'не установлен'}
├ 🌍 Язык: 🇷🇺 Русский
├ ✅ Статус: Верифицирован
└ 📅 Регистрация: {user[6][:10] if user and user[6] else 'сегодня'}

Ты крутой пользователь! :3
            """
            await message.answer(user_info, parse_mode="Markdown")
        else:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="👤 Мой профиль")],
                    [KeyboardButton(text="🎲 Случайный бред")],
                    [KeyboardButton(text="🌍 Сменить язык")],
                    [KeyboardButton(text="📋 Помощь")]
                ],
                resize_keyboard=True
            )
            await message.answer("Используй кнопки ниже! :3", reply_markup=keyboard)
    else:
        if message.text == "👤 My profile":
            user_info = f"""
📋 *Your profile:*

*Basic info:*
├ 🆔 ID: `{user_id}`
├ 👤 Name: {user[2] if user else message.from_user.first_name}
├ 🏷️ Username: @{user[1] if user and user[1] else 'not set'}
├ 🌍 Language: 🇬🇧 English
├ ✅ Status: Verified
└ 📅 Registered: {user[6][:10] if user and user[6] else 'today'}

You're awesome! :3
            """
            await message.answer(user_info, parse_mode="Markdown")
        else:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="👤 My profile")],
                    [KeyboardButton(text="🎲 Random nonsense")],
                    [KeyboardButton(text="🌍 Change language")],
                    [KeyboardButton(text="📋 Help")]
                ],
                resize_keyboard=True
            )
            await message.answer("Use buttons below! :3", reply_markup=keyboard)

async def main():
    logger.info("Запуск бота на Railway...")
    
    try:
        me = await bot.get_me()
        logger.info(f"Бот запущен: @{me.username} (ID: {me.id})")
        logger.info(f"Создатель: @{CREATOR_USERNAME} (ID: {CREATOR_ID})")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return
    
    # Запускаем фоновую задачу для проверки прав
    asyncio.create_task(check_and_send_welcome())
    logger.info("✅ Фоновая задача check_and_send_welcome запущена")
    
    # Запускаем поллинг
    await dp.start_polling(bot, skip_updates=True)
    logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())
