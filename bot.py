import os
import logging
import random
import sqlite3
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated

load_dotenv()

API_TOKEN = os.getenv('BOT_TOKEN')
if not API_TOKEN:
    API_TOKEN = 'YOUR_BOT_TOKEN_HERE'
    logging.warning("Using hardcoded token! This is unsafe!")

CREATOR_USERNAME = 'whitestrings'
CREATOR_ID = '8019499675'

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
            has_admin BOOLEAN DEFAULT 0
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

def update_group_admin_status(group_id, has_admin):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
    group = cursor.fetchone()
    
    if group:
        cursor.execute('UPDATE groups SET has_admin = ? WHERE group_id = ?', (has_admin, group_id))
    else:
        cursor.execute('INSERT INTO groups (group_id, has_admin) VALUES (?, ?)', (group_id, has_admin))
    
    conn.commit()
    conn.close()

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

async def check_bot_permissions(group_id):
    try:
        bot_member = await bot.get_chat_member(group_id, bot.id)
        can_send = bot_member.can_send_messages if hasattr(bot_member, 'can_send_messages') else False
        is_admin = bot_member.status in ['administrator', 'creator']
        
        update_group_admin_status(group_id, is_admin and can_send)
        
        return {
            'can_send_messages': can_send,
            'is_admin': is_admin,
            'status': bot_member.status
        }
    except Exception as e:
        logger.error(f"Ошибка проверки прав в группе {group_id}: {e}")
        update_group_admin_status(group_id, False)
        return None

@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added_to_group(event: ChatMemberUpdated):
    if event.new_chat_member.user.id == bot.id:
        group_id = event.chat.id
        group_title = event.chat.title
        
        logger.info(f"Бот добавлен в группу: {group_id} - {group_title}")
        
        permissions = await check_bot_permissions(group_id)
        
        if permissions and permissions['can_send_messages']:
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
            logger.info(f"Приветствие отправлено в группу {group_id}")
        else:
            logger.warning(f"Бот добавлен в группу {group_id} без прав администратора")

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
        await bot.send_message(group_id, text)
    
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
        await message.answer("Для справки напиши 'нейми помощь' :3")

@dp.callback_query(F.data.startswith("start_lang_"))
async def start_language_handler(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[2]
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    last_name = callback.from_user.last_name
    
    logger.info(f"Пользователь {user_id} выбрал язык: {lang}")
    
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
        
        elif message.text == "📋 Помощь":
            help_text = """
📚 *Помощь по боту:*

*В группах:*
• Напиши "нейми" и команду
• Бот отвечает на твоем языке
• Ты должен быть верифицирован

*В личных сообщениях:*
• Можешь посмотреть свой профиль
• Получить случайный бред
• Сменить язык

*Верификация:*
• При первом использовании выбери язык
• После этого можешь использовать бота везде

Все команды заканчиваются :3
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
        
        elif message.text == "📋 Help":
            help_text = """
📚 *Bot Help:*

*In groups:*
• Write "нейми" and command
• Bot replies in your language
• You must be verified

*In private messages:*
• View your profile
• Get random nonsense
• Change language

*Verification:*
• Choose language on first use
• After that you can use bot everywhere

All commands end with :3
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

async def process_group_command(message: types.Message):
    text = (message.text or "").lower()
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    chat_id = message.chat.id
    
    if not (text.startswith("нейми") or text.startswith("neymi")):
        return False
    
    command = text[6:].strip().lower() if text.startswith("нейми") else text[6:].strip().lower()
    
    if not command:
        return False
    
    permissions = await check_bot_permissions(chat_id)
    
    if not permissions or not permissions['can_send_messages']:
        logger.warning(f"Бот не может писать в чат {chat_id}")
        return False
    
    group_lang = get_group_language(chat_id)
    if group_lang is None:
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
        return True
    
    if not is_user_verified(user_id):
        await message.answer(
            f"👤 {first_name}, для использования бота сначала пройди верификацию в личных сообщениях! Напиши /start :3"
        )
        return True
    
    user = get_user(user_id)
    user_lang = user[5] if user else group_lang
    response_lang = group_lang if group_lang else user_lang
    
    if any(word in command for word in ["привет", "hello", "hi", "хай"]):
        if response_lang == 'ru':
            await message.answer(f"Привет, {first_name}! Как дела? :3")
        else:
            await message.answer(f"Hello, {first_name}! How are you? :3")
    
    elif "бред" in command or "nonsense" in command:
        await message.answer(get_funny_response(response_lang))
    
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
                        callback_data=f"group_profile_{user_id}_{chat_id}"
                    )
                ]
            ]
        )
        
        if response_lang == 'ru':
            await message.answer(
                f"📊 {first_name}, какой профиль показать? :3",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                f"📊 {first_name}, which profile to show? :3",
                reply_markup=keyboard
            )
    
    elif "помощь" in command or "help" in command:
        if response_lang == 'ru':
            help_text = f"""
🤖 *Доступные команды для {first_name}:*

Начинай с "нейми":
• привет - поздороваться
• бред - получить случайный бред
• кому дать тортик - дать тортик (ответь на сообщение)
• профиль - показать профиль
• как дела - узнать как у бота дела
• факт - случайный факт

Пиши "нейми" и команду! :3
            """
        else:
            help_text = f"""
🤖 *Available commands for {first_name}:*

Start with "нейми":
• hello - say hello
• nonsense - get random nonsense
• give cake - give cake (reply to message)
• profile - show profile
• how are you - ask how the bot is doing
• fact - random fact

Write "нейми" and command! :3
            """
        
        await message.answer(help_text, parse_mode="Markdown")
    
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
        await message.answer(random.choice(responses))
    
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
        await message.answer(random.choice(facts))
    
    else:
        if response_lang == 'ru':
            await message.answer(f"Я не понял команды, {first_name}! Попробуй 'нейми помощь' :3")
        else:
            await message.answer(f"I didn't understand the command, {first_name}! Try 'нейми help' :3")
    
    return True

@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_group_messages(message: types.Message):
    text = (message.text or "").lower()
    
    if text.startswith("нейми") or text.startswith("neymi"):
        await process_group_command(message)

@dp.callback_query(F.data.startswith("personal_profile_"))
async def show_personal_profile(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
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
    
    if callback.from_user.id != user_id:
        await callback.answer("Это не твой профиль! :3", show_alert=True)
        return
    
    user = get_user(user_id)
    lang = user[5] if user else 'ru'
    
    try:
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
        
        await callback.message.answer(profile_text, parse_mode="Markdown")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error getting group member: {e}")
        await callback.answer("❌ Ошибка получения информации :3" if lang == 'ru' else "❌ Error getting information :3", show_alert=True)

async def main():
    logger.info("Запуск бота...")
    try:
        me = await bot.get_me()
        logger.info(f"Бот запущен: @{me.username} (ID: {me.id})")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
