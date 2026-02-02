import logging
import random
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

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

# Состояния для ЛС
class UserStates(StatesGroup):
    choosing_language = State()
    choosing_action = State()

# Функции для бота
def get_funny_response(lang='ru'):
    if lang == 'ru':
        responses = [
            "Я видел как бегемот учил котенка танцевать танго! 🦛🐱 :3",
            "Вчера видел облако в форме пиццы с ананасами! 🍕☁️ :3",
            "Моя бабушка играет в доту лучше тебя! 👵🎮 :3",
            "Если посолить арбуз, он станет селедкой! 🍉➡️🐟 :3",
            "Кошки управляют миром, но мы об этом не знаем! 🐈👑 :3",
            "Зебра - это лошадь в пижаме! 🦓 :3",
            "Улитки спят по 3 года! 🐌😴 :3",
            "Мед никогда не портится - у него нет сроков годности! 🍯 :3",
            "Сердце креветки находится в ее голове! 🦐 :3",
            "Осьминоги имеют три сердца! 🐙 :3"
        ]
    else:
        responses = [
            "I saw a hippo teaching a kitten to dance tango! 🦛🐱 :3",
            "Yesterday I saw a cloud shaped like pineapple pizza! 🍕☁️ :3",
            "My grandma plays Dota better than you! 👵🎮 :3",
            "If you salt a watermelon, it becomes a herring! 🍉➡️🐟 :3",
            "Cats rule the world, but we don't know it! 🐈👑 :3",
            "A zebra is a horse in pajamas! 🦓 :3",
            "Snails can sleep for 3 years! 🐌😴 :3",
            "Honey never spoils - it has no expiration date! 🍯 :3",
            "A shrimp's heart is in its head! 🦐 :3",
            "Octopuses have three hearts! 🐙 :3"
        ]
    return random.choice(responses)

# Инициализация БД
init_db()

# Обработчик старта
@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    if message.chat.type == "private":
        update_user(user_id, username, first_name, last_name)
        
        if is_user_verified(user_id):
            user = get_user(user_id)
            lang = user[5] if user else 'ru'
            
            if lang == 'ru':
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="Мой профиль")],
                        [KeyboardButton(text="Случайный бред")],
                        [KeyboardButton(text="Сменить язык")],
                        [KeyboardButton(text="Помощь")]
                    ],
                    resize_keyboard=True
                )
                text = f"Привет, {first_name}! Ты уже верифицирован. Выбери действие:"
            else:
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="My profile")],
                        [KeyboardButton(text="Random nonsense")],
                        [KeyboardButton(text="Change language")],
                        [KeyboardButton(text="Help")]
                    ],
                    resize_keyboard=True
                )
                text = f"Hello, {first_name}! You are already verified. Choose action:"
            
            await message.answer(text, reply_markup=keyboard)
            await state.set_state(UserStates.choosing_action)
        else:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
                    ]
                ]
            )
            await message.answer(
                "👋 Привет! Добро пожаловать!\n"
                "Для использования бота в группах тебе нужно выбрать язык:\n\n"
                "👋 Hello! Welcome!\n"
                "To use the bot in groups, you need to choose a language:",
                reply_markup=keyboard
            )
    else:
        user = get_user(user_id)
        if not user or not is_user_verified(user_id):
            try:
                await bot.send_message(
                    user_id,
                    "⚠️ Чтобы использовать бота в группе, тебе нужно сначала выбрать язык в личных сообщениях со мной!\n\n"
                    "⚠️ To use the bot in a group, you need to choose a language in private messages with me first!"
                )
            except:
                pass
            
            await message.answer(
                f"👤 {first_name}, сначала пройди верификацию в личных сообщениях с ботом! :3"
            )
        else:
            lang = user[5] if user else 'ru'
            if lang == 'ru':
                await message.answer(f"Привет, {first_name}! Я уже знаю твой язык (русский). Пиши 'нейми помощь' :3")
            else:
                await message.answer(f"Hello, {first_name}! I already know your language (English). Write 'нейми помощь' :3")

# Обработчик выбора языка
@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    last_name = callback.from_user.last_name
    
    update_user(user_id, username, first_name, last_name, lang)
    set_user_language(user_id, lang)
    
    if lang == 'ru':
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Мой профиль")],
                [KeyboardButton(text="Случайный бред")],
                [KeyboardButton(text="Сменить язык")],
                [KeyboardButton(text="Помощь")]
            ],
            resize_keyboard=True
        )
        text = "✅ Отлично! Ты успешно верифицирован! Теперь ты можешь использовать бота в группах! :3"
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="My profile")],
                [KeyboardButton(text="Random nonsense")],
                [KeyboardButton(text="Change language")],
                [KeyboardButton(text="Help")]
            ],
            resize_keyboard=True
        )
        text = "✅ Great! You have been verified! Now you can use the bot in groups! :3"
    
    await callback.message.edit_text(text)
    await callback.message.answer(
        "Выбери действие / Choose action:",
        reply_markup=keyboard
    )
    await state.set_state(UserStates.choosing_action)
    await callback.answer()

# Обработка сообщений в группах
@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_group_messages(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    if not is_user_verified(user_id):
        return
    
    user = get_user(user_id)
    if not user:
        return
    
    lang = user[5]
    
    text = message.text.lower() if message.text else ""
    
    if text.startswith("нейми") or text.startswith("neymi"):
        command = text[6:].strip() if text.startswith("нейми") else text[6:].strip()
        
        if lang == 'ru':
            if any(word in command for word in ["привет", "хай", "здаров"]):
                await message.answer(f"Привет, {first_name}! Как дела? :3")
            
            elif "бред" in command:
                await message.answer(get_funny_response('ru'))
            
            elif "кому дать тортик" in command:
                if message.reply_to_message:
                    user = message.reply_to_message.from_user
                    username = f"@{user.username}" if user.username else user.first_name
                    user_link = f"https://t.me/{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.id})"
                    await message.answer(f"ХА! Конечно же {user_link} нужно дать тортик! 🎂 :3", parse_mode="Markdown")
                else:
                    await message.answer("Ответь на сообщение человека, которому хочешь дать тортик! :3")
            
            elif "кто моя жена" in command:
                if str(message.from_user.id) == CREATOR_ID or message.from_user.username == CREATOR_USERNAME:
                    await message.answer("ХА! Конечно же [@eshhka_8](https://t.me/eshhka_8) твоя жена! 💖 :3", parse_mode="Markdown")
                else:
                    await message.answer("Эта команда только для создателя! :3")
            
            elif "как дела" in command:
                responses = [
                    f"Отлично, {first_name}! Только что победил в шахматы у ИИ! ♟️ :3",
                    f"Супер! Видел как белка каталась на скейте! 🐿️🛹 :3",
                    f"Лучше не бывает! Мне только что дали виртуальное печенье! 🍪 :3"
                ]
                await message.answer(random.choice(responses))
            
            elif "кто я" in command:
                compliments = [
                    f"Ты прекрасный человек, {first_name}! У тебя отличный вкус в ботах! 😊 :3",
                    f"Ты тот, кто заставляет этот чат сиять, {first_name}! ✨ :3",
                    f"Ты уникальная личность с великим потенциалом, {first_name}! 🌟 :3"
                ]
                await message.answer(random.choice(compliments))
            
            elif "факт" in command:
                facts = [
                    "Знаешь ли ты, что у улитки около 25,000 зубов? 🐌 :3",
                    "Осьминоги имеют три сердца! 🐙 :3",
                    "Мед никогда не портится! 🍯 :3",
                    "Сердце креветки находится в ее голове! 🦐 :3"
                ]
                await message.answer(random.choice(facts))
            
            elif "помощь" in command or "команды" in command:
                help_text = f"""
🤖 *Доступные команды для {first_name}:*

Начинай с "нейми":
• *привет* - поздороваться
• *бред* - получить случайный бред
• *кому дать тортик* - дать тортик (ответь на сообщение)
• *как дела* - узнать как у бота дела
• *кто я* - получить комплимент
• *факт* - случайный факт
• *помощь* - эта справка

Все команды заканчиваются :3
                """
                await message.answer(help_text, parse_mode="Markdown")
            
            else:
                await message.answer(f"Я не понял команды, {first_name}! Попробуй 'нейми помощь' :3")
        
        else:
            if any(word in command for word in ["hello", "hi", "hey"]):
                await message.answer(f"Hello, {first_name}! How are you? :3")
            
            elif "nonsense" in command or "gibberish" in command:
                await message.answer(get_funny_response('en'))
            
            elif "give cake" in command or "who gets cake" in command:
                if message.reply_to_message:
                    user = message.reply_to_message.from_user
                    username = f"@{user.username}" if user.username else user.first_name
                    user_link = f"https://t.me/{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.id})"
                    await message.answer(f"HA! Of course {user_link} needs to get cake! 🎂 :3", parse_mode="Markdown")
                else:
                    await message.answer("Reply to the person's message who you want to give cake to! :3")
            
            elif "who is my wife" in command:
                if str(message.from_user.id) == CREATOR_ID or message.from_user.username == CREATOR_USERNAME:
                    await message.answer("HA! Of course [@eshhka_8](https://t.me/eshhka_8) is your wife! 💖 :3", parse_mode="Markdown")
                else:
                    await message.answer("This command is only for the creator! :3")
            
            elif "how are you" in command:
                responses = [
                    f"Great, {first_name}! Just beat an AI at chess! ♟️ :3",
                    f"Awesome! Saw a squirrel riding a skateboard! 🐿️🛹 :3",
                    f"Couldn't be better! Just got a virtual cookie! 🍪 :3"
                ]
                await message.answer(random.choice(responses))
            
            elif "who am i" in command:
                compliments = [
                    f"You're an amazing person, {first_name}! You have great taste in bots! 😊 :3",
                    f"You're the one who makes this chat shine, {first_name}! ✨ :3",
                    f"You're a unique individual with great potential, {first_name}! 🌟 :3"
                ]
                await message.answer(random.choice(compliments))
            
            elif "fact" in command:
                facts = [
                    "Did you know snails have about 25,000 teeth? 🐌 :3",
                    "Octopuses have three hearts! 🐙 :3",
                    "Honey never spoils! 🍯 :3",
                    "A shrimp's heart is in its head! 🦐 :3"
                ]
                await message.answer(random.choice(facts))
            
            elif "help" in command or "commands" in command:
                help_text = f"""
🤖 *Available commands for {first_name}:*

Start with "нейми":
• *hello* - say hello
• *nonsense* - get random nonsense
• *give cake* - give cake (reply to message)
• *how are you* - ask how the bot is doing
• *who am i* - get a compliment
• *fact* - random fact
• *help* - this help

All commands end with :3
                """
                await message.answer(help_text, parse_mode="Markdown")
            
            else:
                await message.answer(f"I didn't understand the command, {first_name}! Try 'нейми help' :3")

# Обработка ЛС
@dp.message(UserStates.choosing_action)
async def handle_action(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    lang = user[5] if user else 'ru'
    
    if lang == 'ru':
        if message.text == "Мой профиль":
            user_info = f"""
📋 *Твой профиль:*
├ ID: `{user_id}`
├ Имя: {user[2] if user else message.from_user.first_name}
├ Юзернейм: @{user[1] if user and user[1] else 'нет'}
├ Язык: 🇷🇺 Русский
├ Верифицирован: ✅ Да
└ Зарегистрирован: {user[6][:10] if user and user[6] else 'Недавно'}

Ты крутой пользователь! :3
            """
            await message.answer(user_info, parse_mode="Markdown")
        
        elif message.text == "Случайный бред":
            await message.answer(get_funny_response('ru'))
        
        elif message.text == "Сменить язык":
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="changelang_ru"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data="changelang_en")
                    ]
                ]
            )
            await message.answer("Выбери новый язык:", reply_markup=keyboard)
        
        elif message.text == "Помощь":
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
        if message.text == "My profile":
            user_info = f"""
📋 *Your profile:*
├ ID: `{user_id}`
├ Name: {user[2] if user else message.from_user.first_name}
├ Username: @{user[1] if user and user[1] else 'none'}
├ Language: 🇬🇧 English
├ Verified: ✅ Yes
└ Registered: {user[6][:10] if user and user[6] else 'Recently'}

You're an awesome user! :3
            """
            await message.answer(user_info, parse_mode="Markdown")
        
        elif message.text == "Random nonsense":
            await message.answer(get_funny_response('en'))
        
        elif message.text == "Change language":
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="changelang_ru"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data="changelang_en")
                    ]
                ]
            )
            await message.answer("Choose a new language:", reply_markup=keyboard)
        
        elif message.text == "Help":
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

# Смена языка
@dp.callback_query(F.data.startswith("changelang_"))
async def change_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    
    user_id = callback.from_user.id
    set_user_language(user_id, lang)
    
    if lang == 'ru':
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Мой профиль")],
                [KeyboardButton(text="Случайный бред")],
                [KeyboardButton(text="Сменить язык")],
                [KeyboardButton(text="Помощь")]
            ],
            resize_keyboard=True
        )
        text = "✅ Язык изменен на русский! :3"
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="My profile")],
                [KeyboardButton(text="Random nonsense")],
                [KeyboardButton(text="Change language")],
                [KeyboardButton(text="Help")]
            ],
            resize_keyboard=True
        )
        text = "✅ Language changed to English! :3"
    
    await callback.message.edit_text(text)
    await callback.message.answer(
        "Выбери действие / Choose action:",
        reply_markup=keyboard
    )
    await callback.answer()

# Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
