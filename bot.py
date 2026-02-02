import os
import logging
import random
import sqlite3
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Получаем токен
API_TOKEN = os.getenv('BOT_TOKEN')
if not API_TOKEN:
    logging.error("❌ BOT_TOKEN не найден!")
    exit(1)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Словарь для хранения групп: {group_id: group_title}
groups_to_welcome = {}
# Словарь для групп, где уже отправили приветствие
welcomed_groups = set()

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language TEXT DEFAULT 'ru',
            registered_date TIMESTAMP
        )
    ''')
    
    # Таблица групп
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'ru'
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

async def try_send_welcome(group_id, group_title):
    """Пытается отправить приветствие в группу"""
    try:
        # Проверяем права бота
        chat_member = await bot.get_chat_member(group_id, bot.id)
        
        # Проверяем, что бот админ и может писать
        is_admin = chat_member.status in ['administrator', 'creator']
        can_send = chat_member.can_send_messages if hasattr(chat_member, 'can_send_messages') else False
        
        if is_admin and can_send:
            # Создаем клавиатуру для выбора языка
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"lang_ru_{group_id}"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data=f"lang_en_{group_id}")
                    ]
                ]
            )
            
            # Отправляем сообщение
            await bot.send_message(
                group_id,
                f"👋 Привет! Я бот 'нейми'!\n\n"
                f"Пожалуйста, выберите язык для общения:\n\n"
                f"👋 Hello! I'm 'нейми' bot!\n"
                f"Please choose language:",
                reply_markup=keyboard
            )
            
            logger.info(f"✅ Приветствие отправлено в группу: {group_id}")
            return True
        else:
            logger.info(f"❌ Нет прав в группе {group_id}. is_admin: {is_admin}, can_send: {can_send}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при отправке в группу {group_id}: {e}")
        return False

async def welcome_checker():
    """Фоновая задача, которая проверяет права и отправляет приветствия"""
    logger.info("🚀 Запускаю welcome_checker...")
    
    while True:
        try:
            # Копируем список групп, чтобы избежать изменений во время итерации
            groups_to_check = list(groups_to_welcome.items())
            
            if not groups_to_check:
                # Нет групп для проверки
                await asyncio.sleep(2)
                continue
            
            for group_id, group_title in groups_to_check:
                # Пропускаем группы, где уже отправили приветствие
                if group_id in welcomed_groups:
                    continue
                
                # Пытаемся отправить приветствие
                success = await try_send_welcome(group_id, group_title)
                
                if success:
                    # Помечаем как обработанную
                    welcomed_groups.add(group_id)
                    
                    # Удаляем из словаря ожидающих
                    if group_id in groups_to_welcome:
                        del groups_to_welcome[group_id]
            
            # Ждем 2 секунды перед следующей проверкой
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Ошибка в welcome_checker: {e}")
            await asyncio.sleep(2)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    logger.info(f"Получен /start от {user_id} ({first_name})")
    
    if message.chat.type == "private":
        # Сохраняем пользователя в БД
        conn = sqlite3.connect('bot_users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, language, registered_date) 
            VALUES (?, ?, ?, 'ru', ?)
        ''', (user_id, username, first_name, datetime.now()))
        
        conn.commit()
        conn.close()
        
        await message.answer(
            f"👋 Привет, {first_name}!\n\n"
            f"✅ Теперь ты можешь использовать меня в группах!\n\n"
            f"Как использовать:\n"
            f"1. Добавь меня в группу\n"
            f"2. Дай права администратора\n"
            f"3. Я сам предложу выбрать язык\n"
            f"4. Используй команды с 'нейми'\n\n"
            f"Например: 'нейми привет' :3"
        )
    else:
        # В группе
        await message.answer("🤖 Привет! Я бот 'нейми'. Сначала дайте мне права администратора!")

@dp.message()
async def handle_all_messages(message: types.Message):
    """Обработчик всех сообщений"""
    chat_id = message.chat.id
    text = message.text or ""
    
    # Если это сообщение в группе/супергруппе
    if message.chat.type in ["group", "supergroup"]:
        # Если бота добавили в группу вручную (например, написали что-то)
        if chat_id not in groups_to_welcome and chat_id not in welcomed_groups:
            logger.info(f"Бот обнаружен в группе: {chat_id}")
            groups_to_welcome[chat_id] = message.chat.title or "Группа"
            
        # Обработка команд с "нейми" (только после приветствия)
        if chat_id in welcomed_groups and text.lower().startswith("нейми"):
            cmd = text[5:].strip().lower()
            
            if not cmd:
                await message.answer("Я тута :3")
            elif "привет" in cmd:
                await message.answer(f"Привет, {message.from_user.first_name}! :3")
            elif "бред" in cmd:
                responses = [
                    "Кошки управляют миром! 🐱",
                    "Улитки спят по 3 года! 🐌",
                    "Осьминоги имеют три сердца! 🐙",
                    "Если посолить арбуз, он станет селедкой! 🍉"
                ]
                await message.answer(random.choice(responses) + " :3")

@dp.callback_query()
async def handle_callbacks(callback: types.CallbackQuery):
    """Обработчик всех callback-запросов"""
    data = callback.data
    
    if data.startswith("lang_"):
        # Обработка выбора языка
        parts = data.split("_")
        if len(parts) >= 3:
            lang = parts[1]  # ru или en
            group_id = int(parts[2])
            
            # Сохраняем язык в БД
            conn = sqlite3.connect('bot_users.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO groups (group_id, language) 
                VALUES (?, ?)
            ''', (group_id, lang))
            
            conn.commit()
            conn.close()
            
            if lang == 'ru':
                await callback.message.edit_text("✅ Отлично! Теперь я буду общаться на русском! :3")
            else:
                await callback.message.edit_text("✅ Great! Now I will communicate in English! :3")
    
    await callback.answer()

async def main():
    """Основная функция запуска"""
    logger.info("🚀 Запускаю бота...")
    
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот запущен: @{me.username} (ID: {me.id})")
        
        # Запускаем фоновую задачу
        asyncio.create_task(welcome_checker())
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    asyncio.run(main())
