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

# Твои данные
API_TOKEN = '8506993378:AAEFg37n8nV1rhQGJXXPAQUeKrbUe6t5QJ8'
CREATOR_USERNAME = 'whitestrings'
CREATOR_ID = '8019499675'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# База данных
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
            welcome_message INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(user_id, username, first_name, last_name, language='ru'):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        cursor.execute('''
            UPDATE users SET 
            username = ?, first_name = ?, last_name = ?, 
            language = ?, last_seen = ?, verified = 1
            WHERE user_id = ?
        ''', (username, first_name, last_name, language, datetime.now(), user_id))
    else:
        cursor.execute('''
            INSERT INTO users 
            (user_id, username, first_name, last_name, language, verified, registered_date, last_seen) 
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        ''', (user_id, username, first_name, last_name, language, datetime.now(), datetime.now()))
    
    conn.commit()
    conn.close()

def set_user_language(user_id, language):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
    conn.commit()
    conn.close()

def is_user_verified(user_id):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT verified FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def get_group_language(group_id):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM groups WHERE group_id = ?', (group_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_group_language(group_id, language):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
    group = cursor.fetchone()
    
    if group:
        cursor.execute('UPDATE groups SET language = ? WHERE group_id = ?', (language, group_id))
    else:
        cursor.execute('INSERT INTO groups (group_id, language) VALUES (?, ?)', (group_id, language))
    
    conn.commit()
    conn.close()

# Состояния для ЛС
class UserStates(StatesGroup):
    choosing_language = State()
    main_menu = State()

# Функции для бота
def get_funny_response(lang='ru'):
    if lang == 'ru':
        responses = [
            "Я видел как бегемот учил котенка танцевать танго! 🦛🐱",
            "Вчера видел облако в форме пиццы с ананасами! 🍕☁️",
            "Моя бабушка играет в доту лучше тебя! 👵🎮",
            "Если посолить арбуз, он станет селедкой! 🍉➡️🐟",
            "Кошки управляют миром, но мы об этом не знаем! 🐈👑",
            "Зебра - это лошадь в пижаме! 🦓",
            "Улитки спят по 3 года! 🐌😴",
            "Мед никогда не портится - у него нет сроков годности! 🍯",
            "Сердце креветки находится в ее голове! 🦐",
            "Осьминоги имеют три сердца! 🐙"
        ]
    else:
        responses = [
            "I saw a hippo teaching a kitten to dance tango! 🦛🐱",
            "Yesterday I saw a cloud shaped like pineapple pizza! 🍕☁️",
            "My grandma plays Dota better than you! 👵🎮",
            "If you salt a watermelon, it becomes a herring! 🍉➡️🐟",
            "Cats rule the world, but we don't know it! 🐈👑",
            "A zebra is a horse in pajamas! 🦓",
            "Snails can sleep for 3 years! 🐌😴",
            "Honey never spoils - it has no expiration date! 🍯",
            "A shrimp's heart is in its head! 🦐",
            "Octopuses have three hearts! 🐙"
        ]
    return random.choice(responses) + " :3"

# Инициализация БД
init_db()

# Глобальная переменная для хранения сообщений о добавлении бота
group_welcome_messages = {}

# Приветственное сообщение при добавлении бота в группу
@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added_to_group(event: ChatMemberUpdated):
    if event.new_chat_member.user.id == bot.id:
        group_id = event.chat.id
        group_title = event.chat.title
        
        logging.info(f"Бот добавлен в группу {group_id} - {group_title}")
        
        # Проверяем права бота - ОБЯЗАТЕЛЬНО ПРОВЕРЯЕМ
        try:
            bot_member = await bot.get_chat_member(group_id, bot.id)
            
            # Проверяем все важные права
            can_send_messages = bot_member.can_send_messages if hasattr(bot_member, 'can_send_messages') else False
            can_send_media_messages = bot_member.can_send_media_messages if hasattr(bot_member, 'can_send_media_messages') else False
            
            logging.info(f"Права бота в группе {group_id}: can_send_messages={can_send_messages}, can_send_media_messages={can_send_media_messages}")
            
            if not can_send_messages:
                # У бота нет прав на отправку сообщений
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"group_lang_ru_{group_id}"),
                            InlineKeyboardButton(text="🇬🇧 English", callback_data=f"group_lang_en_{group_id}")
                        ]
                    ]
                )
                
                # Сохраняем сообщение для возможности его редактировать позже
                try:
                    msg = await bot.send_message(
                        group_id,
                        f"👋 Приветствую в группе '{group_title}'!\n\n"
                        f"⚠️ *ВНИМАНИЕ:* У меня нет прав администратора!\n\n"
                        f"Пожалуйста, дайте мне права администратора с разрешением:\n"
                        f"• Отправка сообщений\n"
                        f"• Отправка медиа\n\n"
                        f"После этого я смогу полноценно работать! :3\n\n"
                        f"👋 Welcome to group '{group_title}'!\n\n"
                        f"⚠️ *ATTENTION:* I don't have admin rights!\n\n"
                        f"Please give me administrator rights with permissions:\n"
                        f"• Send messages\n"
                        f"• Send media\n\n"
                        f"After that I can work fully! :3",
                        parse_mode="Markdown"
                    )
                    
                    # Сохраняем ID сообщения для возможности его редактировать
                    group_welcome_messages[group_id] = msg.message_id
                    
                except Exception as e:
                    logging.error(f"Не могу отправить сообщение в группу {group_id}: {e}")
            else:
                # Бот может писать, сразу предлагаем выбрать язык
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"group_lang_ru_{group_id}"),
                            InlineKeyboardButton(text="🇬🇧 English", callback_data=f"group_lang_en_{group_id}")
                        ]
                    ]
                )
                
                msg = await bot.send_message(
                    group_id,
                    f"👋 Приветствую в группе '{group_title}'!\n\n"
                    f"Выберите язык для общения со мной:\n\n"
                    f"👋 Welcome to group '{group_title}'!\n"
                    f"Choose language for communication with me:",
                    reply_markup=keyboard
                )
                
                group_welcome_messages[group_id] = msg.message_id
                
        except Exception as e:
            logging.error(f"Ошибка проверки прав бота в группе {group_id}: {e}")

# Функция проверки прав бота
async def check_bot_permissions(chat_id):
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        
        # Проверяем основные права
        permissions = {
            'can_send_messages': bot_member.can_send_messages if hasattr(bot_member, 'can_send_messages') else False,
            'can_send_media_messages': bot_member.can_send_media_messages if hasattr(bot_member, 'can_send_media_messages') else False,
            'can_send_polls': bot_member.can_send_polls if hasattr(bot_member, 'can_send_polls') else False,
            'can_send_other_messages': bot_member.can_send_other_messages if hasattr(bot_member, 'can_send_other_messages') else False,
            'can_add_web_page_previews': bot_member.can_add_web_page_previews if hasattr(bot_member, 'can_add_web_page_previews') else False,
            'can_change_info': bot_member.can_change_info if hasattr(bot_member, 'can_change_info') else False,
            'can_invite_users': bot_member.can_invite_users if hasattr(bot_member, 'can_invite_users') else False,
            'can_pin_messages': bot_member.can_pin_messages if hasattr(bot_member, 'can_pin_messages') else False,
        }
        
        return True, permissions
    except Exception as e:
        logging.error(f"Ошибка проверки прав в чате {chat_id}: {e}")
        return False, {}

# Команда для проверки прав бота
@dp.message(F.chat.type.in_(["group", "supergroup"]) & Command("check_permissions"))
async def cmd_check_permissions(message: types.Message):
    """Проверка прав бота в группе"""
    success, permissions = await check_bot_permissions(message.chat.id)
    
    if success:
        permissions_text = "📋 *Права бота в этой группе:*\n\n"
        
        for perm, value in permissions.items():
            emoji = "✅" if value else "❌"
            perm_name = perm.replace('_', ' ').title()
            permissions_text += f"{emoji} {perm_name}: {'Да' if value else 'Нет'}\n"
        
        permissions_text += "\nДля нормальной работы нужны:\n✅ can_send_messages\n✅ can_send_media_messages :3"
        
        await message.answer(permissions_text, parse_mode="Markdown")
    else:
        await message.answer("❌ Не удалось проверить права бота :3")

# Выбор языка для группы
@dp.callback_query(F.data.startswith("group_lang_"))
async def set_group_language_handler(callback: types.CallbackQuery):
    data = callback.data.split("_")
    lang = data[2]  # ru или en
    group_id = int(data[3])
    
    # Проверяем права бота перед установкой языка
    success, permissions = await check_bot_permissions(group_id)
    
    if success and permissions.get('can_send_messages', False):
        set_group_language(group_id, lang)
        
        if lang == 'ru':
            text = "✅ Отлично! Теперь я буду общаться на русском языке в этой группе! :3\n\nДля справки напиши 'нейми помощь'"
        else:
            text = "✅ Great! Now I will communicate in English in this group! :3\n\nFor help write 'нейми help'"
        
        try:
            # Пробуем редактировать существующее сообщение
            if group_id in group_welcome_messages:
                await bot.edit_message_text(
                    chat_id=group_id,
                    message_id=group_welcome_messages[group_id],
                    text=text
                )
            else:
                await bot.send_message(group_id, text)
                
            # Удаляем сообщение из словаря после успешной обработки
            if group_id in group_welcome_messages:
                del group_welcome_messages[group_id]
                
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.answer("✅ Язык установлен! :3")
    
    await callback.answer()

# Обработчик старта в ЛС
@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    if message.chat.type == "private":
        # Проверяем, верифицирован ли пользователь
        if is_user_verified(user_id):
            user = get_user(user_id)
            lang = user[5] if user else 'ru'
            
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
                await state.set_state(UserStates.main_menu)
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
                await state.set_state(UserStates.main_menu)
        else:
            # Приветственное сообщение с выбором языка
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
    else:
        # В группе показываем информацию о боте
        success, permissions = await check_bot_permissions(message.chat.id)
        
        if success:
            group_lang = get_group_language(message.chat.id)
            
            if group_lang == 'ru':
                await message.answer(
                    "🤖 *Информация о боте:*\n\n"
                    "Используйте 'нейми' перед командами:\n"
                    "• нейми привет - поздороваться\n"
                    "• нейми помощь - справка\n"
                    "• нейми профиль - ваш профиль\n\n"
                    "Сначала нужно выбрать язык группы! :3",
                    parse_mode="Markdown"
                )
            else:
                await message.answer(
                    "🤖 *Bot Information:*\n\n"
                    "Use 'нейми' before commands:\n"
                    "• нейми hello - say hello\n"
                    "• нейми help - help\n"
                    "• нейми profile - your profile\n\n"
                    "First need to choose group language! :3",
                    parse_mode="Markdown"
                )

# [Добавь сюда все остальные функции из предыдущего кода]
# Выбор языка при старте, обработка ЛС, обработка групповых сообщений и т.д.
# Просто скопируй их из предыдущего кода без изменений

# Важная функция - проверка прав при каждой команде в группе
async def process_group_command(message: types.Message, command: str):
    """Обработка команд с проверкой прав"""
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # Проверяем права бота
    success, permissions = await check_bot_permissions(message.chat.id)
    
    if not success or not permissions.get('can_send_messages', False):
        # Пытаемся уведомить, если бот не может писать
        try:
            await message.answer(
                "😫 У меня нет прав для отправки сообщений!\n"
                "Пожалуйста, дайте мне права администратора с разрешением 'Отправка сообщений' :3"
            )
        except:
            pass
        return False
    
    # Проверяем язык группы
    group_lang = get_group_language(message.chat.id)
    if group_lang is None:
        # Предлагаем выбрать язык
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"group_lang_ru_{message.chat.id}"),
                    InlineKeyboardButton(text="🇬🇧 English", callback_data=f"group_lang_en_{message.chat.id}")
                ]
            ]
        )
        await message.answer(
            "🌍 Пожалуйста, выберите язык для бота в этой группе:\n\n"
            "🌍 Please choose language for bot in this group:",
            reply_markup=keyboard
        )
        return False
    
    # Проверяем верификацию пользователя
    if not is_user_verified(user_id):
        await message.answer(
            f"👤 {first_name}, для использования бота сначала пройди верификацию в личных сообщениях! Напиши /start :3"
        )
        return False
    
    return True

# Пример обработки команд в группе (добавь все свои команды сюда)
@dp.message(F.chat.type.in_(["group", "supergroup"]) & F.text.startswith("нейми"))
async def handle_neymi_commands(message: types.Message):
    text = message.text.lower()
    command = text[6:].strip() if text.startswith("нейми") else ""
    
    # Если команда пустая - отвечаем "Я тута :3"
    if not command:
        # Проверяем права
        success, permissions = await check_bot_permissions(message.chat.id)
        if success and permissions.get('can_send_messages', False):
            await message.answer("Я тута :3")
        return
    
    # Проверяем права перед обработкой команды
    if not await process_group_command(message, command):
        return
    
    # Получаем язык группы
    group_lang = get_group_language(message.chat.id)
    user = get_user(message.from_user.id)
    user_lang = user[5] if user else group_lang
    response_lang = group_lang if group_lang else user_lang
    
    # Обработка команд (добавь свои команды)
    if "привет" in command:
        if response_lang == 'ru':
            await message.answer(f"Привет, {message.from_user.first_name}! Как дела? :3")
        else:
            await message.answer(f"Hello, {message.from_user.first_name}! How are you? :3")
    
    # Добавь остальные команды...

# Запуск бота
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logging.info("Бот запускается...")
    
    # Проверяем доступность бота
    try:
        me = await bot.get_me()
        logging.info(f"Бот запущен: @{me.username} (ID: {me.id})")
    except Exception as e:
        logging.error(f"Ошибка получения информации о боте: {e}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
