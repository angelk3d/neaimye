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
        
        # Логируем детальную информацию о правах
        logger.info(f"Проверка прав в группе {group_id}. Статус: {chat_member.status}, can_send_messages: {chat_member.can_send_messages if hasattr(chat_member, 'can_send_messages') else 'N/A'}")
        
        # Проверяем, что бот админ и может писать
        is_admin = chat_member.status in ['administrator', 'creator']
        can_send = getattr(chat_member, 'can_send_messages', False)
        
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
            return True, "sent"
        elif is_admin and not can_send:
            logger.warning(f"⚠️ Бот админ, но НЕ МОЖЕТ отправлять сообщения в группе {group_id}!")
            return False, "admin_no_send"
        else:
            logger.info(f"❌ Бот не админ в группе {group_id}. Статус: {chat_member.status}")
            return False, "not_admin"
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при отправке в группу {group_id}: {error_msg}")
        
        # Если бот был кикнут или забанен
        if "kicked" in error_msg or "banned" in error_msg or "bot was kicked" in error_msg:
            logger.info(f"🗑️ Бот удален из группы {group_id}, удаляю из списков")
            # Удаляем из списков
            if group_id in groups_to_welcome:
                del groups_to_welcome[group_id]
            if group_id in welcomed_groups:
                welcomed_groups.remove(group_id)
            return True, "kicked"  # Возвращаем True, чтобы остановить попытки
        
        return False, "error"

async def welcome_checker():
    """Фоновая задача, которая проверяет права и отправляет приветствия"""
    logger.info("🚀 Запускаю welcome_checker...")
    
    while True:
        try:
            # Копируем список групп, чтобы избежать изменений во время итерации
            groups_to_check = list(groups_to_welcome.items())
            
            if not groups_to_check:
                # Нет групп для проверки
                await asyncio.sleep(5)
                continue
            
            for group_id, group_title in groups_to_check:
                # Пропускаем группы, где уже отправили приветствие
                if group_id in welcomed_groups:
                    continue
                
                # Пытаемся отправить приветствие
                success, reason = await try_send_welcome(group_id, group_title)
                
                if success:
                    if reason == "sent":
                        # Успешно отправили приветствие
                        welcomed_groups.add(group_id)
                        # Удаляем из словаря ожидающих
                        if group_id in groups_to_welcome:
                            del groups_to_welcome[group_id]
                    elif reason == "kicked":
                        # Бот кикнут, уже удалили из списков
                        pass
                else:
                    if reason == "admin_no_send":
                        # Бот админ, но не может отправлять сообщения
                        # Ждем 10 секунд перед следующей проверкой
                        await asyncio.sleep(10)
                    else:
                        # Ждем 5 секунд перед следующей проверкой
                        await asyncio.sleep(5)
            
            # Ждем 5 секунд перед следующей проверкой всех групп
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Ошибка в welcome_checker: {e}")
            await asyncio.sleep(5)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    logger.info(f"Получен /start от {user_id} ({first_name})")
    
    if message.chat.type == "private":
        await message.answer(
            f"👋 Привет, {first_name}!\n\n"
            f"✅ Теперь ты можешь использовать меня в группах!\n\n"
            f"**ВНИМАНИЕ:**\n"
            f"Когда добавляешь меня в группу:\n"
            f"1. Добавь меня в группу\n"
            f"2. Дай права **администратора**\n"
            f"3. **ОБЯЗАТЕЛЬНО** включи разрешение **'Отправка сообщений'**\n"
            f"4. Я сам предложу выбрать язык\n"
            f"5. Используй команды с 'нейми'\n\n"
            f"Если не включить 'Отправка сообщений' - я не смогу писать! :3"
        )
    else:
        # В группе - проверяем права и отправляем инструкцию
        chat_id = message.chat.id
        try:
            chat_member = await bot.get_chat_member(chat_id, bot.id)
            is_admin = chat_member.status in ['administrator', 'creator']
            can_send = getattr(chat_member, 'can_send_messages', False)
            
            if is_admin and can_send:
                await message.answer("✅ У меня есть права! Я уже должен был отправить приветствие с выбором языка.")
            elif is_admin and not can_send:
                await message.answer("⚠️ Я администратор, но НЕ МОГУ отправлять сообщения! Включите разрешение 'Отправка сообщений' в настройках администратора!")
            else:
                await message.answer("❌ Я не администратор! Дайте мне права администратора с разрешением 'Отправка сообщений'.")
        except Exception as e:
            await message.answer("❌ Не могу проверить свои права в этой группе.")

@dp.message()
async def handle_all_messages(message: types.Message):
    """Обработчик всех сообщений"""
    chat_id = message.chat.id
    text = message.text or ""
    
    # Если это сообщение в группе/супергруппе
    if message.chat.type in ["group", "supergroup"]:
        # Если бота добавили в группу вручную (например, написали что-то)
        if chat_id not in groups_to_welcome and chat_id not in welcomed_groups:
            logger.info(f"🤖 Бот обнаружен в группе: {chat_id} - {message.chat.title}")
            groups_to_welcome[chat_id] = message.chat.title or "Группа"
            
        # Обработка команд с "нейми" (только после приветствия)
        if text.lower().startswith("нейми"):
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
            elif "проверка" in cmd:
                # Проверка прав бота
                try:
                    chat_member = await bot.get_chat_member(chat_id, bot.id)
                    is_admin = chat_member.status in ['administrator', 'creator']
                    can_send = getattr(chat_member, 'can_send_messages', False)
                    
                    if is_admin and can_send:
                        await message.answer("✅ Я администратор и могу отправлять сообщения!")
                    elif is_admin and not can_send:
                        await message.answer("⚠️ Я администратор, но НЕ МОГУ отправлять сообщения! Включите разрешение 'Отправка сообщений'!")
                    else:
                        await message.answer("❌ Я не администратор! Дайте мне права администратора.")
                except Exception as e:
                    await message.answer("❌ Ошибка проверки прав")

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
                await callback.message.edit_text("✅ Отлично! Теперь я буду общаться на русском!\n\nИспользуй 'нейми' перед командами. Например: 'нейми привет' :3")
            else:
                await callback.message.edit_text("✅ Great! Now I will communicate in English!\n\nUse 'нейми' before commands. For example: 'нейми hello' :3")
    
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
