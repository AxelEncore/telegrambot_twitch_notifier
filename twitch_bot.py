import logging
import requests
import time
import schedule
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext

# Настройки
TELEGRAM_TOKEN = '7588357806:AAFZ1beGNMOTtJNX6wA5o69_uQMpW_XQa-o'
TWITCH_CLIENT_ID = 'w2y2t05i7iwk43yj6ncyvtvnqzmkze'
TWITCH_CLIENT_SECRET = 'egxo7iiha9dhv6ap4z1k4rvfpltbzg'
TWITCH_USERNAMES = ['axelencore', 'yatoencoree', 'julia_encore', 'aliseencore']
TWITCH_API_URL = 'https://api.twitch.tv/helix/streams'
CHECK_INTERVAL = 60  # интервал проверки стримов (в секундах)

# Словарь для отслеживания состояния трансляций
live_status = {username: False for username in TWITCH_USERNAMES}

# Логгирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Получаем информацию о стримах
def check_twitch_streams(bot: Bot, chat_id: int, twitch_oauth_token: str):
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {twitch_oauth_token}'
    }
    
    for username in TWITCH_USERNAMES:
        params = {'user_login': username}
        response = requests.get(TWITCH_API_URL, headers=headers, params=params)
        data = response.json()
        
        # Проверяем, идет ли трансляция
        if data['data']:
            if not live_status[username]:  # Если раньше не было стрима
                live_status[username] = True
                stream_title = data['data'][0]['title']
                message = f'{username} начал трансляцию: {stream_title}\nСмотреть: https://twitch.tv/{username}'
                bot.send_message(chat_id=chat_id, text=message)
        else:
            live_status[username] = False  # Если стрима нет

# Команда /start для подписки на уведомления
def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    context.bot.send_message(chat_id=chat_id, text="Подписка на уведомления о стримах Twitch активирована!")
    
    # Получаем токен и запускаем проверку трансляций
    twitch_oauth_token = get_twitch_oauth_token()
    
    # Планируем проверку стримов через schedule
    schedule.every(CHECK_INTERVAL).seconds.do(check_twitch_streams, bot=context.bot, chat_id=chat_id, twitch_oauth_token=twitch_oauth_token)
    
    # Цикл для выполнения задач по расписанию
    while True:
        schedule.run_pending()
        time.sleep(1)

# Запуск бота
def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    # Регистрация команд
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()