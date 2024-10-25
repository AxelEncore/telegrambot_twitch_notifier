import os
import json
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Настройки
TELEGRAM_TOKEN = '8049016680:AAFo45bEX8HlSnKiX_bfnYY_KhaWaUJu7PE'  # Замените на токен вашего бота
TWITCH_CLIENT_ID = 'w2y2t05i7iwk43yj6ncyvtvnqzmkze'  # Замените на ваш Twitch Client ID
TWITCH_CLIENT_SECRET = 'egxo7iiha9dhv6ap4z1k4rvfpltbzg'  # Замените на ваш Twitch Client Secret
TWITCH_USERNAMES = ['axelencore', 'yatoencoree', 'julia_encore', 'aliseencore', 'hotabych4', 'waterspace17']  # Список стримеров для отслеживания
CHECK_INTERVAL = 60  # Интервал проверки стримов (в секундах)
SUBSCRIPTIONS_FILE = 'subscriptions.json'  # Файл для хранения подписок

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Словарь для хранения подписок пользователей
user_subscriptions = {}

# Функция для чтения подписок из файла
def load_subscriptions():
    global user_subscriptions
    if os.path.exists(SUBSCRIPTIONS_FILE):
        with open(SUBSCRIPTIONS_FILE, 'r') as f:
            try:
                content = f.read()
                if content.strip():
                    user_subscriptions = json.loads(content)
                    logger.info("Подписки успешно загружены.")
                else:
                    user_subscriptions = {}
                    logger.info("Файл подписок пуст. Инициализируем пустой словарь подписок.")
            except json.JSONDecodeError as e:
                user_subscriptions = {}
                logger.error(f"Ошибка при загрузке подписок: {e}. Инициализируем пустой словарь подписок.")
    else:
        user_subscriptions = {}
        logger.info("Файл подписок не найден. Инициализируем пустой словарь подписок.")

# Функция для сохранения подписок в файл
def save_subscriptions():
    try:
        with open(SUBSCRIPTIONS_FILE, 'w') as f:
            json.dump(user_subscriptions, f, indent=4)
        logger.info("Подписки успешно сохранены.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении подписок: {e}")

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

# Функция для проверки статуса стримов
def check_streams(context: CallbackContext):
    twitch_oauth_token = get_twitch_oauth_token()
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {twitch_oauth_token}'
    }
    active_streams = []

    # Получаем информацию о стримах
    for username in TWITCH_USERNAMES:
        params = {'user_login': username}
        response = requests.get('https://api.twitch.tv/helix/streams', headers=headers, params=params)
        data = response.json()
        if data['data']:
            active_streams.append(username)

    # Отправляем уведомления подписанным пользователям
    for chat_id, subscriptions in user_subscriptions.items():
        for streamer in subscriptions:
            if streamer in active_streams:
                message = f"🔴 {streamer} сейчас в эфире!\nСмотреть стрим: https://twitch.tv/{streamer}"
                context.bot.send_message(chat_id=int(chat_id), text=message)
                # Удаляем стримера из подписок, чтобы не отправлять повторные уведомления
                subscriptions.remove(streamer)
    save_subscriptions()

# Команда /start
def start(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_subscriptions:
        user_subscriptions[chat_id] = []
        save_subscriptions()

    # Создаем кнопки с именами стримеров
    keyboard = []
    for streamer in TWITCH_USERNAMES:
        keyboard.append([InlineKeyboardButton(streamer, callback_data=streamer)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Привет! Выберите стримеров, на которых хотите подписаться для получения уведомлений:",
        reply_markup=reply_markup
    )

# Обработка нажатий кнопок
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    streamer = query.data
    chat_id = str(query.message.chat.id)

    if streamer not in user_subscriptions.get(chat_id, []):
        user_subscriptions[chat_id].append(streamer)
        save_subscriptions()
        query.answer(f"Вы подписались на {streamer}")
    else:
        query.answer(f"Вы уже подписаны на {streamer}")

# Главная функция
def main():
    try:
        load_subscriptions()
    except Exception as e:
        logger.error(f"Ошибка при загрузке подписок: {e}")
        user_subscriptions = {}

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Добавляем обработчики
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CallbackQueryHandler(button))

    # Планирование задачи проверки стримов
    job_queue = updater.job_queue
    job_queue.run_repeating(check_streams, interval=CHECK_INTERVAL, first=10)

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
