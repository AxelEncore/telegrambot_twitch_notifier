import sqlite3
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from threading import Timer
import os

# Настройки
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_USERNAMES = ['axelencore', 'yatoencoree', 'julia_encore', 'aliseencore']
TWITCH_API_URL = 'https://api.twitch.tv/helix/streams'
CHECK_INTERVAL = 60  # Интервал проверки стримов (в секундах)
DB_FILE = 'subscriptions.db'  # Файл базы данных

# Логгирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Функция для подключения к базе данных SQLite
def connect_db():
    return sqlite3.connect(DB_FILE)

# Создание таблицы, если она не существует
def create_table():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        chat_id INTEGER PRIMARY KEY,
        streamers TEXT
    );
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Функция для загрузки подписок из базы данных
def load_subscriptions():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, streamers FROM subscriptions;")
    rows = cursor.fetchall()
    subscriptions = {row[0]: row[1].split(',') for row in rows if row[1]}  # Преобразуем строку в список
    cursor.close()
    conn.close()
    return subscriptions

# Функция для сохранения подписок в базу данных
def save_subscription(chat_id, streamers):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO subscriptions (chat_id, streamers)
        VALUES (?, ?)
        ON CONFLICT(chat_id) 
        DO UPDATE SET streamers=excluded.streamers;
    """, (chat_id, ','.join(streamers)))  # Сохраняем список как строку
    conn.commit()
    cursor.close()
    conn.close()

# Словарь для хранения подписок пользователей (загружаем данные при старте)
user_subscriptions = load_subscriptions()

# Функция для получения OAuth токена Twitch
def get_twitch_oauth_token():
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()['access_token']

# Проверка статуса стримов
def check_twitch_streams(bot, twitch_oauth_token):
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {twitch_oauth_token}'
    }

    for username in TWITCH_USERNAMES:
        params = {'user_login': username}
        response = requests.get(TWITCH_API_URL, headers=headers, params=params)
        data = response.json()

        # Проверяем, идет ли стрим
        stream_live = bool(data['data'])

        # Если стрим начался и ранее не было уведомления
        if stream_live and not active_streams[username]:
            stream_title = data['data'][0]['title']
            for chat_id, subscriptions in user_subscriptions.items():
                if username in subscriptions:
                    message = f'{username} начал трансляцию: {stream_title}\nСмотреть: https://twitch.tv/{username}'
                    bot.send_message(chat_id=chat_id, text=message)
            active_streams[username] = True  # Обновляем статус стрима как активный

        # Если стрим закончился, сбрасываем статус
        elif not stream_live and active_streams[username]:
            active_streams[username] = False

# Периодическая проверка стримов
def schedule_check_streams(bot):
    twitch_oauth_token = get_twitch_oauth_token()
    check_twitch_streams(bot, twitch_oauth_token)
    Timer(CHECK_INTERVAL, schedule_check_streams, [bot]).start()

# Стартовая команда
def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id not in user_subscriptions:
        user_subscriptions[chat_id] = []  # Инициализация пустого списка подписок

    # Кнопки с именами стримеров
    keyboard = [[InlineKeyboardButton(streamer, callback_data=streamer)] for streamer in TWITCH_USERNAMES]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Сообщение с картинкой и кнопками
    context.bot.send_photo(
        chat_id=chat_id,
        photo="https://axelencore.ru/wp-content/uploads/2024/09/Oreo.jpg",  # Убедитесь, что это действительная ссылка
        caption="Привет, я бот Oreo - уведомляю о стримах Encore\nОт каких стримеров вы хотите получать уведомления? Нажмите на кнопки",
        reply_markup=reply_markup
    )

# Обработка нажатий кнопок
def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    streamer = query.data
    chat_id = query.message.chat_id
    
    # Добавление стримера в подписки
    if streamer not in user_subscriptions[chat_id]:
        user_subscriptions[chat_id].append(streamer)
        save_subscription(chat_id, user_subscriptions[chat_id])  # Сохраняем подписки в базу данных
        query.answer()
        context.bot.send_message(chat_id=chat_id, text=f"Вы подписались на стримы от {streamer}")
    else:
        query.answer()
        context.bot.send_message(chat_id=chat_id, text=f"Вы уже подписаны на {streamer}")

# Запуск бота
def main():
    # Создаем таблицу, если ее еще нет
    create_table()

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Добавляем команды
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    # Запускаем проверку стримов
    bot = updater.bot
    schedule_check_streams(bot)

    # Запуск webhook сервера
    webhook_url = 'https://worker-production-1f60.up.railway.app/' + TELEGRAM_TOKEN
    updater.bot.set_webhook(url=webhook_url)
    updater.start_webhook(listen="0.0.0.0", port=8443, url_path=TELEGRAM_TOKEN, webhook_url=webhook_url)

    updater.idle()

if __name__ == '__main__':
    main()
