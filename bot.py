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

# Если на Railway не установлен BOT_TOKEN - используем fallback
if not API_TOKEN:
    # Это только для локальной разработки
    try:
        from dotenv import load_dotenv
        load_dotenv()
        API_TOKEN = os.getenv('BOT_TOKEN')
    except ImportError:
        pass

# Проверяем, есть ли токен
if not API_TOKEN:
    logging.error("❌ BOT_TOKEN не найден!")
    logging.error("Добавьте BOT_TOKEN в переменные окружения на Railway")
    logging.error("Или создайте .env файл для локальной разработки")
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
            welcome_sent BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
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

def mark_group_as_processed(group_id):
    """Помечаем группу как обработанную (приветствие отправлено)"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
    group = cursor.fetchone()
    
    if group:
        cursor.execute('UPDATE groups SET welcome_sent = 1 WHERE group_id = ?', (group_id,))
    else:
        cursor.execute('INSERT INTO groups (group_id, welcome_sent) VALUES (?, 1)', (group_id,))
    
    conn.commit()
    conn.close()

def is_group_processed(group_id):
    """Проверяем, было ли отправлено приветствие в группе"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT welcome_sent FROM groups WHERE group_id = ?', (group_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def set_group_active(group_id, active):
    """Устанавливаем статус активности группы"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
    group = cursor.fetchone()
    
    if group:
        cursor.execute('UPDATE groups SET is_active = ? WHERE group_id = ?', (1 if active else 0, group_id))
    else:
        cursor.execute('INSERT INTO groups (group_id, is_active) VALUES (?, ?)', (group_id, 1 if active else 0))
    
    conn.commit()
    conn.close()

def is_group_active(group_id):
    """Проверяем активна ли группа"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_active FROM groups WHERE group_id = ?', (group_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

class UserStates(StatesGroup):
    choosing_language = State()
    main_menu = State()

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

init_db()
logger.info("База данных инициализирована")

async def check_bot_permissions(chat_id):
    """Проверяет права бота в чате"""
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        can_send = bot_member.can_send_messages if hasattr(bot_member, 'can_send_messages') else False
        is_admin = bot_member.status in ['administrator', 'creator']
        return can_send and is_admin
    except Exception as e:
        logger.error(f"Ошибка проверки прав в чате {chat_id}: {e}")
        return False

async def send_welcome_message(group_id, group_title):
    """Отправляет приветственное сообщение с выбором языка"""
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
        
        # Помечаем, что приветствие отправлено
        mark_group_as_processed(group_id)
        logger.info(f"✅ Приветствие отправлено в группу {group_id}")
        return True
    except Exception as e:
        logger.warning(f"Не могу отправить приветствие в группу {group_id}: {e}")
        return False

# Словарь для хранения активных задач по группам
active_tasks = {}

async def keep_trying_to_send_welcome(group_id, group_title):
    """Бесконечно пытается отправить приветствие каждые 2 секунды"""
    logger.info(f"🚀 Начинаю попытки отправки приветствия в группу {group_id}")
    
    while True:
        try:
            # Проверяем активность группы
            if not is_group_active(group_id):
                logger.info(f"Группа {group_id} неактивна, прекращаю попытки")
                break
                
            # Проверяем, не было ли уже отправлено приветствие
            if is_group_processed(group_id):
                logger.info(f"Приветствие уже отправлено в группу {group_id}, прекращаю попытки")
                break
                
            # Проверяем права
            has_permissions = await check_bot_permissions(group_id)
            
            if has_permissions:
                logger.info(f"✅ Бот имеет права в группе {group_id}, пытаюсь отправить приветствие")
                success = await send_welcome_message(group_id, group_title)
                if success:
                    logger.info(f"✅ Приветствие успешно отправлено в группу {group_id}")
                    break
                else:
                    logger.warning(f"Не удалось отправить приветствие в группу {group_id}, пробую снова через 2 секунды")
            else:
                logger.info(f"⏳ Бот не имеет прав в группе {group_id}, жду 2 секунды")
            
            # Ждем 2 секунды перед следующей попыткой
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Ошибка при попытке отправить приветствие в группу {group_id}: {e}")
            await asyncio.sleep(2)
    
    # Удаляем задачу из словаря активных задач
    if group_id in active_tasks:
        del active_tasks[group_id]
    logger.info(f"Завершены попытки отправки приветствия в группу {group_id}")

@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added_to_group(event: ChatMemberUpdated):
    if event.new_chat_member.user.id == bot.id:
        group_id = event.chat.id
        group_title = event.chat.title
        
        logger.info(f"🤖 Бот добавлен в группу: {group_id} - {group_title}")
        
        # Помечаем группу как активную
        set_group_active(group_id, True)
        
        # Если для этой группы уже есть активная задача, отменяем ее
        if group_id in active_tasks:
            try:
                active_tasks[group_id].cancel()
                logger.info(f"Отменена предыдущая задача для группы {group_id}")
            except:
                pass
        
        # Запускаем новую задачу для этой группы
        task = asyncio.create_task(keep_trying_to_send_welcome(group_id, group_title))
        active_tasks[group_id] = task
        
        logger.info(f"Запущена задача для группы {group_id}")

@dp.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_bot_removed_from_group(event: ChatMemberUpdated):
    if event.old_chat_member.user.id == bot.id:
        group_id = event.chat.id
        
        logger.info(f"🗑️ Бот удален из группы: {group_id}")
        
        # Помечаем группу как неактивную
        set_group_active(group_id, False)
        
        # Отменяем задачу для этой группы, если она существует
        if group_id in active_tasks:
            try:
                active_tasks[group_id].cancel()
                logger.info(f"Отменена задача для удаленной группы {group_id}")
                del active_tasks[group_id]
            except:
                pass

@dp.callback_query(F.data.startswith("group_lang_"))
async def set_group_language_handler(callback: types.CallbackQuery):
    data = callback.data.split("_")
    lang = data[2]
    group_id = int(data[3])
    
    set_group_language(group_id, lang)
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
            pass
    
    await callback.answer()

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    logger.info(f"Команда /start от пользователя {user_id} ({first_name}) в чате {message.chat.type}")
    
    if message.chat.type == "private":
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
        # В группе - просто игнорируем
        pass

@dp.callback_query(F.data.startswith("start_lang_"))
async def start_language_handler(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[2]
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    last_name = callback.from_user.last_name
    
    logger.info(f"Пользователь {user_id} выбрал язык: {lang}")
    
    # Сохраняем пользователя
    update_user(user_id, username, first_name, last_name, lang)
    
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
            f"Теперь ты можешь использовать бота в группах!\n\n"
            f"📋 *Твои данные:*\n"
            f"├ ID: `{user_id}`\n"
            f"├ Имя: {first_name}\n"
            f"├ Юзернейм: @{username if username else 'нет'}\n"
            f"├ Язык: 🇷🇺 Русский\n"
            f"└ Статус: ✅ Верифицирован\n\n"
            f"Используй кнопки ниже! :3",
            parse_mode="Markdown",
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
            f"Now you can use the bot in groups!\n\n"
            f"📋 *Your data:*\n"
            f"├ ID: `{user_id}`\n"
            f"├ Name: {first_name}\n"
            f"├ Username: @{username if username else 'none'}\n"
            f"├ Language: 🇬🇧 English\n"
            f"└ Status: ✅ Verified\n\n"
            f"Use buttons below! :3",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    await state.set_state(UserStates.main_menu)
    await callback.answer()

@dp.message(F.chat.type == "private")
async def handle_private_messages(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    logger.info(f"Личное сообщение от {user_id}: {message.text}")
    
    if message.text in ["/start", "/help", "/start@neaimybot", "/help@neaimybot"]:
        await cmd_start(message, state)
        return
    
    if not is_user_verified(user_id):
        await message.answer("Сначала пройди верификацию! Напиши /start :3")
        return
    
    user = get_user(user_id)
    lang = user[5] if user else 'ru'
    
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

Ты крутой пользователь! Продолжай в том же духе! :3
            """
            await message.answer(user_info, parse_mode="Markdown")
        
        elif message.text == "🎲 Случайный бред":
            await message.answer(get_funny_response('ru'))
        
        elif message.text == "🌍 Сменить язык":
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="change_lang_ru"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data="change_lang_en")
                    ]
                ]
            )
            await message.answer("Выбери новый язык:", reply_markup=keyboard)
        
        elif message.text == "📋 Помощь":
            help_text = """
📚 *Помощь по боту:*

*Верификация:*
• Выбери язык в ЛС
• После этого можешь использовать бота в группах

*В личных сообщениях:*
• Можешь посмотреть свой профиль
• Получить случайный бред
• Сменить язык

*В группах:*
• Бот сам предложит выбрать язык при добавлении
• Используй команды после выбора языка
• Ты должен быть верифицирован
            """
            await message.answer(help_text, parse_mode="Markdown")
        
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

You're an awesome user! Keep it up! :3
            """
            await message.answer(user_info, parse_mode="Markdown")
        
        elif message.text == "🎲 Random nonsense":
            await message.answer(get_funny_response('en'))
        
        elif message.text == "🌍 Change language":
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="change_lang_ru"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data="change_lang_en")
                    ]
                ]
            )
            await message.answer("Choose a new language:", reply_markup=keyboard)
        
        elif message.text == "📋 Help":
            help_text = """
📚 *Bot Help:*

*Verification:*
• Choose language in PM
• After that you can use bot in groups

*In private messages:*
• View your profile
• Get random nonsense
• Change language

*In groups:*
• Bot will suggest language when added
• Use commands after language selection
• You must be verified
            """
            await message.answer(help_text, parse_mode="Markdown")
        
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

@dp.callback_query(F.data.startswith("change_lang_"))
async def change_language_handler(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[2]
    
    user_id = callback.from_user.id
    set_user_language(user_id, lang)
    
    user = get_user(user_id)
    first_name = user[2] if user else callback.from_user.first_name
    
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
        
        await callback.message.edit_text("✅ Язык изменен на русский! :3")
        await callback.message.answer(
            f"Привет, {first_name}! Теперь я буду общаться с тобой на русском :3",
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
        
        await callback.message.edit_text("✅ Language changed to English! :3")
        await callback.message.answer(
            f"Hello, {first_name}! Now I will communicate with you in English :3",
            reply_markup=keyboard
        )
    
    await state.set_state(UserStates.main_menu)
    await callback.answer()

@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_group_messages(message: types.Message):
    text = (message.text or "").lower()
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, начинается ли с "нейми"
    if text.startswith("нейми") or text.startswith("neymi"):
        # Проверяем права бота
        has_permissions = await check_bot_permissions(chat_id)
        
        if not has_permissions:
            # Бот не может писать, пропускаем
            logger.warning(f"Бот не может писать в чат {chat_id}")
            return
        
        # Проверяем, выбран ли язык для группы
        group_lang = get_group_language(chat_id)
        if group_lang is None:
            # Язык не выбран, предлагаем выбрать
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"group_lang_ru_{chat_id}"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data=f"group_lang_en_{chat_id}")
                    ]
                ]
            )
            
            await message.answer(
                "🌍 Пожалуйста, выберите язык для бота в этой группе:\n\n"
                "🌍 Please choose language for bot in this group:",
                reply_markup=keyboard
            )
            return
        
        # Проверяем, верифицирован ли пользователь
        if not is_user_verified(user_id):
            await message.answer(
                f"👤 {message.from_user.first_name}, для использования бота сначала пройди верификацию в личных сообщениях! Напиши /start :3"
            )
            return
        
        # Получаем команду после "нейми"
        command = text[6:].strip().lower() if text.startswith("нейми") else text[6:].strip().lower()
        
        if not command:
            await message.answer("Я тута :3")
            return
        
        # Получаем язык пользователя
        user = get_user(user_id)
        user_lang = user[5] if user else group_lang
        response_lang = group_lang if group_lang else user_lang
        
        # Приветствие
        if any(word in command for word in ["привет", "hello", "hi", "хай"]):
            if response_lang == 'ru':
                await message.answer(f"Привет, {message.from_user.first_name}! Как дела? :3")
            else:
                await message.answer(f"Hello, {message.from_user.first_name}! How are you? :3")
        
        # Бред
        elif "бред" in command or "nonsense" in command:
            await message.answer(get_funny_response(response_lang))
        
        # Кому дать тортик
        elif "кому дать тортик" in command or "give cake" in command:
            if message.reply_to_message:
                user = message.reply_to_message.from_user
                user_link = f"https://t.me/{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.id})"
                if response_lang == 'ru':
                    await message.answer(
                        f"ХА! Конечно же {user_link} нужно дать тортик! 🎂 :3",
                        parse_mode="Markdown"
                    )
                else:
                    await message.answer(
                        f"HA! Of course {user_link} needs to get cake! 🎂 :3",
                        parse_mode="Markdown"
                    )
            else:
                if response_lang == 'ru':
                    await message.answer("Ответь на сообщение человека, которому хочешь дать тортик! :3")
                else:
                    await message.answer("Reply to the person's message who you want to give cake to! :3")
        
        # Приватная команда для создателя
        elif "кто моя жена" in command or "who is my wife" in command:
            if str(message.from_user.id) == CREATOR_ID or message.from_user.username == CREATOR_USERNAME:
                await message.answer(
                    "ХА! Конечно же [@eshhka_8](https://t.me/eshhka_8) твоя жена! 💖 :3",
                    parse_mode="Markdown"
                )
            else:
                if response_lang == 'ru':
                    await message.answer("Эта команда только для создателя! :3")
                else:
                    await message.answer("This command is only for the creator! :3")
        
        # Помощь
        elif "помощь" in command or "help" in command:
            if response_lang == 'ru':
                help_text = f"""
🤖 *Доступные команды для {message.from_user.first_name}:*

Начинай с "нейми":
• привет - поздороваться
• бред - получить случайный бред
• кому дать тортик - дать тортик (ответь на сообщение)
                """
            else:
                help_text = f"""
🤖 *Available commands for {message.from_user.first_name}:*

Start with "нейми":
• hello - say hello
• nonsense - get random nonsense
• give cake - give cake (reply to message)
                """
            
            await message.answer(help_text, parse_mode="Markdown")
        
        # Неизвестная команда
        else:
            if response_lang == 'ru':
                await message.answer(f"Я не понял команды, {message.from_user.first_name}! Попробуй 'нейми помощь' :3")
            else:
                await message.answer(f"I didn't understand the command, {message.from_user.first_name}! Try 'нейми help' :3")

async def restart_stuck_groups():
    """Перезапускает задачи для групп, которые могли застрять"""
    while True:
        try:
            # Получаем все активные группы из БД
            conn = sqlite3.connect('bot_users.db')
            cursor = conn.cursor()
            cursor.execute('SELECT group_id FROM groups WHERE is_active = 1 AND welcome_sent = 0')
            groups = cursor.fetchall()
            conn.close()
            
            for group in groups:
                group_id = group[0]
                
                # Проверяем, есть ли уже задача для этой группы
                if group_id not in active_tasks:
                    try:
                        # Получаем информацию о группе
                        chat = await bot.get_chat(group_id)
                        
                        # Запускаем новую задачу
                        task = asyncio.create_task(keep_trying_to_send_welcome(group_id, chat.title))
                        active_tasks[group_id] = task
                        logger.info(f"Перезапущена задача для группы {group_id}")
                    except Exception as e:
                        # Если бота нет в группе, помечаем как неактивную
                        if "Chat not found" in str(e) or "bot was kicked" in str(e):
                            logger.info(f"Бота нет в группе {group_id}, помечаем как неактивную")
                            set_group_active(group_id, False)
            
            # Ждем 30 секунд перед следующей проверкой
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка в перезапуске задач: {e}")
            await asyncio.sleep(30)

async def main():
    logger.info("Запуск бота на Railway...")
    
    try:
        me = await bot.get_me()
        logger.info(f"Бот запущен: @{me.username} (ID: {me.id})")
        logger.info(f"Создатель: @{CREATOR_USERNAME} (ID: {CREATOR_ID})")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return
    
    # Запускаем задачу для перезапуска застрявших групп
    asyncio.create_task(restart_stuck_groups())
    
    # Запускаем поллинг
    await dp.start_polling(bot)
    logger.info("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
