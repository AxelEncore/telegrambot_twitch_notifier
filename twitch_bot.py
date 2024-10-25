import json
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
# Удаляем Timer
# from threading import Timer

# Настройки
TELEGRAM_TOKEN = '8049016680:AAFo45bEX8HlSnKiX_bfnYY_KhaWaUJu7PE'
TWITCH_CLIENT_ID = 'w2y2t05i7iwk43yj6ncyvtvnqzmkze'
TWITCH_CLIENT_SECRET = 'egxo7iiha9dhv6ap4z1k4rvfpltbzg'
TWITCH_USERNAMES = ['axelencore', 'yatoencoree', 'julia_encore', 'aliseencore', 'hotabych4', 'waterspace17']
TWITCH_API_URL = 'https://api.twitch.tv/helix/streams'
CHECK_INTERVAL = 60  # Интервал проверки стримов (в секундах)
SUBSCRIPTIONS_FILE = 'subscriptions.json'  # Файл для хранения подписок

# Словарь для отслеживания активных стримов
active_streams = {username: False for username in TWITCH_USERNAMES}

# Логгирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Словарь для хранения подписок пользователей (загружаем при старте)
user_subscriptions = {}

# Функции load_subscriptions и save_subscriptions остаются без изменений

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
                    bot.send_message(chat_id=int(chat_id), text=message)
            active_streams[username] = True  # Обновляем статус стрима как активный

        # Если стрим закончился, сбрасываем статус
        elif not stream_live and active_streams[username]:
            active_streams[username] = False

# Функция для задания в JobQueue
def check_twitch_streams_job(context: CallbackContext):
    try:
        twitch_oauth_token = get_twitch_oauth_token()
        check_twitch_streams(context.bot, twitch_oauth_token)
    except Exception as e:
        logger.error(f"Ошибка при проверке стримов: {e}")

# Остальной код (функции start, button_callback и main) с изменениями для использования JobQueue

def start(update: Update, context: CallbackContext) -> None:
    # Ваш код функции start

def button_callback(update: Update, context: CallbackContext) -> None:
    # Ваш код функции button_callback

def main():
    load_subscriptions()
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Добавляем команды
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    # Планируем периодическую задачу
    job_queue = updater.job_queue
    job_queue.run_repeating(check_twitch_streams_job, interval=CHECK_INTERVAL, first=0)

    # Запуск вебхука
    port = int(os.environ.get('PORT', '8443'))
    webhook_url = 'https://worker-production-1f60.up.railway.app/' + TELEGRAM_TOKEN
    updater.start_webhook(listen="0.0.0.0",
                          port=port,
                          url_path=TELEGRAM_TOKEN,
                          webhook_url=webhook_url)

    updater.idle()

if __name__ == '__main__':
    main()
