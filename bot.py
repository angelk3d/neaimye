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

# Состояния
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

# Функция для отправки сообщений в группе без создания топиков
async def safe_group_send(chat_id: int, text: str, reply_markup=None, parse_mode=None, message_thread_id=None):
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            message_thread_id=message_thread_id
        )
        return True
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return False

# Приветственное сообщение при добавлении бота в группу
@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added_to_group(event: ChatMemberUpdated):
    if event.new_chat_member.user.id == bot.id:
        group_id = event.chat.id
        group_title = event.chat.title
        
        # Ждем 1 секунду перед проверкой прав
        await asyncio.sleep(1)
        
        # Проверяем права бота
        try:
            bot_member = await bot.get_chat_member(group_id, bot.id)
            
            if not bot_member.can_send_messages:
                # У бота нет прав на отправку сообщений
                success = await safe_group_send(
                    group_id,
                    "БЛИННН 😫 Я не могу писать в эту группу, потому что у меня нет прав администратора!\n\n"
                    "Пожалуйста, дайте мне права на отправку сообщений, чтобы я мог работать :3"
                )
                
                # Если не получилось отправить (нет прав), ничего не делаем
                if not success:
                    pass
            else:
                # Бот может писать, предлагаем выбрать язык группы
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"group_lang_ru_{group_id}"),
                            InlineKeyboardButton(text="🇬🇧 English", callback_data=f"group_lang_en_{group_id}")
                        ]
                    ]
                )
                
                await safe_group_send(
                    group_id,
                    f"👋 Приветствую в группе '{group_title}'!\n\n"
                    f"Выберите язык для общения со мной:\n\n"
                    f"👋 Welcome to group '{group_title}'!\n"
                    f"Choose language for communication with me:",
                    reply_markup=keyboard
                )
                
        except Exception as e:
            logging.error(f"Error checking bot permissions: {e}")

# Выбор языка для группы
@dp.callback_query(F.data.startswith("group_lang_"))
async def set_group_language_handler(callback: types.CallbackQuery):
    data = callback.data.split("_")
    lang = data[2]  # ru или en
    group_id = int(data[3])
    
    set_group_language(group_id, lang)
    
    if lang == 'ru':
        text = "✅ Отлично! Я буду общаться на русском языке в этой группе! :3"
    else:
        text = "✅ Great! I will communicate in English in this group! :3"
    
    try:
        await callback.message.edit_text(text)
    except:
        await safe_group_send(group_id, text)
    
    await callback.answer()

# Обработчик старта в ЛС
@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    if message.chat.type == "private":
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
        
        await state.set_state(UserStates.choosing_language)
    else:
        # В группе проверяем верификацию, но только если сообщение начинается с команды
        if message.text and message.text.startswith('/'):
            user = get_user(user_id)
            if not user or not is_user_verified(user_id):
                await safe_group_send(
                    message.chat.id,
                    f"👤 {first_name}, для использования бота сначала пройди верификацию в личных сообщениях! :3",
                    message_thread_id=message.message_thread_id
                )
            else:
                lang = user[5] if user else 'ru'
                group_lang = get_group_language(message.chat.id)
                
                if group_lang == 'ru' or (group_lang is None and lang == 'ru'):
                    await safe_group_send(
                        message.chat.id,
                        f"Привет, {first_name}! Я уже знаю твой язык. Используй 'нейми' для команд :3",
                        message_thread_id=message.message_thread_id
                    )
                else:
                    await safe_group_send(
                        message.chat.id,
                        f"Hello, {first_name}! I already know your language. Use 'нейми' for commands :3",
                        message_thread_id=message.message_thread_id
                    )

# Выбор языка при старте
@dp.callback_query(F.data.startswith("start_lang_"))
async def start_language_handler(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[2]  # ru или en
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    last_name = callback.from_user.last_name
    
    # Сохраняем пользователя
    update_user(user_id, username, first_name, last_name, lang)
    
    if lang == 'ru':
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 Мой профиль")],
                [KeyboardButton(text="🎲 Случайный бред")],
                [KeyboardButton(text="🌍 Сменить язык")]
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
            f"Используй кнопки ниже или команды в группах! :3",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 My profile")],
                [KeyboardButton(text="🎲 Random nonsense")],
                [KeyboardButton(text="🌍 Change language")]
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
            f"Use buttons below or commands in groups! :3",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    await state.set_state(UserStates.main_menu)
    await callback.answer()

# Обработка ЛС - главное меню
@dp.message(UserStates.main_menu)
async def handle_main_menu(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    lang = user[5] if user else 'ru'
    
    if lang == 'ru':
        if message.text == "👤 Мой профиль":
            # Полная информация о профиле
            user_info = f"""
📋 *Твой профиль:*

*Основное:*
├ 🆔 ID: `{user_id}`
├ 👤 Имя: {user[2] if user else message.from_user.first_name}
├ 🏷️ Юзернейм: @{user[1] if user and user[1] else 'не установлен'}
├ 🌍 Язык: 🇷🇺 Русский
├ ✅ Статус: Верифицирован
└ 📅 Регистрация: {user[6][:10] if user and user[6] else 'сегодня'}

*Статистика:*
├ 📊 Уровень активности: {random.randint(1, 100)}%
├ 🏆 Ранг: {random.choice(['Новичок', 'Активный', 'Ветеран'])}
└ 🌟 Репутация: {random.randint(1, 1000)} очков

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
        
        else:
            await message.answer("Используй кнопки ниже! :3")
    
    else:
        # English version
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

*Statistics:*
├ 📊 Activity level: {random.randint(1, 100)}%
├ 🏆 Rank: {random.choice(['Beginner', 'Active', 'Veteran'])}
└ 🌟 Reputation: {random.randint(1, 1000)} points

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
        
        else:
            await message.answer("Use the buttons below! :3")

# Смена языка в ЛС
@dp.callback_query(F.data.startswith("change_lang_"))
async def change_language_handler(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[2]  # ru или en
    
    user_id = callback.from_user.id
    set_user_language(user_id, lang)
    
    user = get_user(user_id)
    first_name = user[2] if user else callback.from_user.first_name
    
    if lang == 'ru':
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 Мой профиль")],
                [KeyboardButton(text="🎲 Случайный бред")],
                [KeyboardButton(text="🌍 Сменить язык")]
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
                [KeyboardButton(text="🌍 Change language")]
            ],
            resize_keyboard=True
        )
        
        await callback.message.edit_text("✅ Language changed to English! :3")
        await callback.message.answer(
            f"Hello, {first_name}! Now I will communicate with you in English :3",
            reply_markup=keyboard
        )
    
    await callback.answer()

# Обработка сообщений в группах - ТОЛЬКО КОМАНДЫ С "НЕЙМИ"
@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_group_messages(message: types.Message):
    # Проверяем, начинается ли сообщение с "нейми"
    text = message.text or ""
    
    if not text.lower().startswith("нейми") and not text.lower().startswith("neymi"):
        return  # Игнорируем сообщения без "нейми"
    
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # Проверяем, может ли бот писать
    try:
        bot_member = await bot.get_chat_member(message.chat.id, bot.id)
        if not bot_member.can_send_messages:
            # Бот не может писать, ничего не делаем
            return
    except Exception as e:
        logging.error(f"Error checking bot permissions: {e}")
        return
    
    # Получаем язык группы
    group_lang = get_group_language(message.chat.id)
    if group_lang is None:
        # Если язык группы не установлен, предлагаем выбрать
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"group_lang_ru_{message.chat.id}"),
                    InlineKeyboardButton(text="🇬🇧 English", callback_data=f"group_lang_en_{message.chat.id}")
                ]
            ]
        )
        
        try:
            await safe_group_send(
                message.chat.id,
                "🌍 Пожалуйста, выберите язык для бота в этой группе:\n\n"
                "🌍 Please choose language for bot in this group:",
                reply_markup=keyboard,
                message_thread_id=message.message_thread_id
            )
        except:
            pass
        return
    
    # Проверяем верификацию пользователя
    if not is_user_verified(user_id):
        try:
            await safe_group_send(
                message.chat.id,
                f"👤 {first_name}, для использования бота сначала пройди верификацию в личных сообщениях! :3",
                message_thread_id=message.message_thread_id
            )
        except:
            pass
        return
    
    # Получаем язык пользователя
    user = get_user(user_id)
    user_lang = user[5] if user else group_lang
    
    # Определяем язык ответа (приоритет: язык группы > язык пользователя)
    response_lang = group_lang if group_lang else user_lang
    
    # Извлекаем команду
    command = text[6:].strip().lower()
    
    # Приветствие
    if any(word in command for word in ["привет", "hello", "hi", "хай"]):
        if response_lang == 'ru':
            await safe_group_send(
                message.chat.id,
                f"Привет, {first_name}! Как дела? :3",
                message_thread_id=message.message_thread_id
            )
        else:
            await safe_group_send(
                message.chat.id,
                f"Hello, {first_name}! How are you? :3",
                message_thread_id=message.message_thread_id
            )
    
    # Бред
    elif "бред" in command or "nonsense" in command:
        await safe_group_send(
            message.chat.id,
            get_funny_response(response_lang),
            message_thread_id=message.message_thread_id
        )
    
    # Кому дать тортик
    elif "кому дать тортик" in command or "give cake" in command:
        if message.reply_to_message:
            user = message.reply_to_message.from_user
            user_link = f"https://t.me/{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.id})"
            if response_lang == 'ru':
                await safe_group_send(
                    message.chat.id,
                    f"ХА! Конечно же {user_link} нужно дать тортик! 🎂 :3",
                    parse_mode="Markdown",
                    message_thread_id=message.message_thread_id
                )
            else:
                await safe_group_send(
                    message.chat.id,
                    f"HA! Of course {user_link} needs to get cake! 🎂 :3",
                    parse_mode="Markdown",
                    message_thread_id=message.message_thread_id
                )
        else:
            if response_lang == 'ru':
                await safe_group_send(
                    message.chat.id,
                    "Ответь на сообщение человека, которому хочешь дать тортик! :3",
                    message_thread_id=message.message_thread_id
                )
            else:
                await safe_group_send(
                    message.chat.id,
                    "Reply to the person's message who you want to give cake to! :3",
                    message_thread_id=message.message_thread_id
                )
    
    # Приватная команда для создателя
    elif "кто моя жена" in command or "who is my wife" in command:
        if str(message.from_user.id) == CREATOR_ID or message.from_user.username == CREATOR_USERNAME:
            await safe_group_send(
                message.chat.id,
                "ХА! Конечно же [@eshhka_8](https://t.me/eshhka_8) твоя жена! 💖 :3",
                parse_mode="Markdown",
                message_thread_id=message.message_thread_id
            )
        else:
            if response_lang == 'ru':
                await safe_group_send(
                    message.chat.id,
                    "Эта команда только для создателя! :3",
                    message_thread_id=message.message_thread_id
                )
            else:
                await safe_group_send(
                    message.chat.id,
                    "This command is only for the creator! :3",
                    message_thread_id=message.message_thread_id
                )
    
    # Профиль
    elif "профиль" in command or "profile" in command:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👤 Личный профиль" if response_lang == 'ru' else "👤 Personal profile", 
                        callback_data=f"personal_profile_{user_id}"
                    ),
                    InlineKeyboardButton(
                        text="👥 Профиль в группе" if response_lang == 'ru' else "👥 Group profile", 
                        callback_data=f"group_profile_{user_id}_{message.chat.id}"
                    )
                ]
            ]
        )
        
        if response_lang == 'ru':
            await safe_group_send(
                message.chat.id,
                f"📊 {first_name}, какой профиль показать? :3",
                reply_markup=keyboard,
                message_thread_id=message.message_thread_id
            )
        else:
            await safe_group_send(
                message.chat.id,
                f"📊 {first_name}, which profile to show? :3",
                reply_markup=keyboard,
                message_thread_id=message.message_thread_id
            )
    
    # Помощь
    elif "помощь" in command or "help" in command:
        if response_lang == 'ru':
            help_text = f"""
🤖 *Доступные команды для {first_name}:*

Начинай с "нейми":
• *привет* - поздороваться
• *бред* - получить случайный бред
• *кому дать тортик* - дать тортик (ответь на сообщение)
• *профиль* - показать профиль
• *как дела* - узнать как у бота дела
• *факт* - случайный факт

Пиши "нейми" и команду! :3
            """
        else:
            help_text = f"""
🤖 *Available commands for {first_name}:*

Start with "нейми":
• *hello* - say hello
• *nonsense* - get random nonsense
• *give cake* - give cake (reply to message)
• *profile* - show profile
• *how are you* - ask how the bot is doing
• *fact* - random fact

Write "нейми" and command! :3
            """
        
        await safe_group_send(
            message.chat.id,
            help_text,
            parse_mode="Markdown",
            message_thread_id=message.message_thread_id
        )
    
    # Как дела
    elif "как дела" in command or "how are you" in command:
        if response_lang == 'ru':
            responses = [
                f"Отлично, {first_name}! Только что победил в шахматы у ИИ! ♟️ :3",
                f"Супер! Видел как белка каталась на скейте! 🐿️🛹 :3",
                f"Лучше не бывает! Мне только что дали виртуальное печенье! 🍪 :3"
            ]
        else:
            responses = [
                f"Great, {first_name}! Just beat an AI at chess! ♟️ :3",
                f"Awesome! Saw a squirrel riding a skateboard! 🐿️🛹 :3",
                f"Couldn't be better! Just got a virtual cookie! 🍪 :3"
            ]
        await safe_group_send(
            message.chat.id,
            random.choice(responses),
            message_thread_id=message.message_thread_id
        )
    
    # Факт
    elif "факт" in command or "fact" in command:
        if response_lang == 'ru':
            facts = [
                "Знаешь ли ты, что у улитки около 25,000 зубов? 🐌 :3",
                "Осьминоги имеют три сердца! 🐙 :3",
                "Мед никогда не портится! 🍯 :3",
                "Сердце креветки находится в ее голове! 🦐 :3"
            ]
        else:
            facts = [
                "Did you know snails have about 25,000 teeth? 🐌 :3",
                "Octopuses have three hearts! 🐙 :3",
                "Honey never spoils! 🍯 :3",
                "A shrimp's heart is in its head! 🦐 :3"
            ]
        await safe_group_send(
            message.chat.id,
            random.choice(facts),
            message_thread_id=message.message_thread_id
        )
    
    # Неизвестная команда
    else:
        if response_lang == 'ru':
            await safe_group_send(
                message.chat.id,
                f"Я не понял команды, {first_name}! Попробуй 'нейми помощь' :3",
                message_thread_id=message.message_thread_id
            )
        else:
            await safe_group_send(
                message.chat.id,
                f"I didn't understand the command, {first_name}! Try 'нейми help' :3",
                message_thread_id=message.message_thread_id
            )

# Обработка кнопок профиля в группе
@dp.callback_query(F.data.startswith("personal_profile_"))
async def show_personal_profile(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    # Проверяем, что запрашивает свой профиль
    if callback.from_user.id != user_id:
        await callback.answer("Это не твой профиль! :3", show_alert=True)
        return
    
    user = get_user(user_id)
    lang = user[5] if user else 'ru'
    
    if lang == 'ru':
        user_info = f"""
📋 *Твой личный профиль:*

*Основное:*
├ 🆔 ID: `{user_id}`
├ 👤 Имя: {user[2] if user else callback.from_user.first_name}
├ 🏷️ Юзернейм: @{user[1] if user and user[1] else 'не установлен'}
├ 🌍 Язык: 🇷🇺 Русский
├ ✅ Статус: Верифицирован
└ 📅 Регистрация: {user[6][:10] if user and user[6] else 'сегодня'}

Отправлено в личные сообщения! :3
        """
    else:
        user_info = f"""
📋 *Your personal profile:*

*Basic info:*
├ 🆔 ID: `{user_id}`
├ 👤 Name: {user[2] if user else callback.from_user.first_name}
├ 🏷️ Username: @{user[1] if user and user[1] else 'not set'}
├ 🌍 Language: 🇬🇧 English
├ ✅ Status: Verified
└ 📅 Registered: {user[6][:10] if user and user[6] else 'today'}

Sent to private messages! :3
        """
    
    try:
        await bot.send_message(user_id, user_info, parse_mode="Markdown")
        await callback.answer("✅ Профиль отправлен в ЛС!" if lang == 'ru' else "✅ Profile sent to PM!", show_alert=False)
    except:
        await callback.answer("❌ Не могу отправить сообщение! Разблокируй бота в ЛС :3" if lang == 'ru' else "❌ Can't send message! Unblock bot in PM :3", show_alert=True)

@dp.callback_query(F.data.startswith("group_profile_"))
async def show_group_profile(callback: types.CallbackQuery):
    data = callback.data.split("_")
    user_id = int(data[2])
    group_id = int(data[3])
    
    # Проверяем, что запрашивает свой профиль
    if callback.from_user.id != user_id:
        await callback.answer("Это не твой профиль! :3", show_alert=True)
        return
    
    user = get_user(user_id)
    lang = user[5] if user else 'ru'
    
    try:
        # Получаем информацию о пользователе в группе
        member = await bot.get_chat_member(group_id, user_id)
        role = "👑 Создатель" if member.status == "creator" else "⚡ Админ" if member.status == "administrator" else "👤 Участник"
        
        if lang == 'ru':
            profile_text = f"""
👥 *Твой профиль в группе:*

*Информация:*
├ 👤 Имя: {member.user.first_name}
├ 🏷️ Юзернейм: @{member.user.username if member.user.username else 'нет'}
├ 🎭 Роль: {role}
├ 📅 Дата присоединения: Недавно
└ 🏆 Статус: Активный

Ты отлично вливаешься в коллектив! :3
            """
        else:
            profile_text = f"""
👥 *Your group profile:*

*Information:*
├ 👤 Name: {member.user.first_name}
├ 🏷️ Username: @{member.user.username if member.user.username else 'none'}
├ 🎭 Role: {"👑 Creator" if member.status == "creator" else "⚡ Admin" if member.status == "administrator" else "👤 Member"}
├ 📅 Join date: Recently
└ 🏆 Status: Active

You're doing great in the group! :3
            """
        
        await safe_group_send(
            callback.message.chat.id,
            profile_text,
            parse_mode="Markdown",
            message_thread_id=callback.message.message_thread_id
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting group member: {e}")
        await callback.answer("❌ Ошибка получения информации :3" if lang == 'ru' else "❌ Error getting information :3", show_alert=True)

# Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
