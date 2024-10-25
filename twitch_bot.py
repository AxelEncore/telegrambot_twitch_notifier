import os
import logging
import requests
import redis  # Новая библиотека для работы с Redis
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Настройки
TELEGRAM_TOKEN = '8049016680:AAFo45bEX8HlSnKiX_bfnYY_KhaWaUJu7PE'  # Замените на токен вашего бота
TWITCH_CLIENT_ID = 'w2y2t05i7iwk43yj6ncyvtvnqzmkze'  # Замените на ваш Twitch Client ID
TWITCH_CLIENT_SECRET = 'egxo7iiha9dhv6ap4z1k4rvfpltbzg'  # Замените на ваш Twitch Client Secret
TWITCH_USERNAMES = ['axelencore', 'yatoencoree', 'julia_encore', 'aliseencore', 'hotabych4', 'waterspace17']  # Список стримеров для отслеживания
CHECK_INTERVAL = 60  # Интервал проверки стримов (в секундах)

# Настройка Redis
REDIS_URL = os.getenv('REDIS_URL')  # URL подключения к Redis из переменной окружения
redis_client = redis.Redis.from_url(REDIS_URL)

# Настройка логирования
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

# Функция для проверки статуса стримов
def check_streams(context: CallbackContext):
    twitch_oauth_token = get_twitch_oauth_token()
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {twitch_oauth_token}'
    }
    active_streams = []

    # Получаем информацию о стримах
    params = [('user_login', username) for username in TWITCH_USERNAMES]
    response = requests.get('https://api.twitch.tv/helix/streams', headers=headers, params=params)
    data = response.json()
    if 'data' in data:
        active_streams = [stream['user_login'] for stream in data['data']]

    # Отправляем уведомления подписанным пользователям
    for chat_id in redis_client.smembers('subscribers'):
        chat_id = chat_id.decode()
        subscriptions = redis_client.smembers(f'subscriptions:{chat_id}')
        subscriptions = {s.decode() for s in subscriptions}
        for streamer in subscriptions:
            if streamer in active_streams:
                # Проверяем, отправляли ли уже уведомление
                if not redis_client.get(f'notified:{chat_id}:{streamer}'):
                    message = f"🔴 {streamer} сейчас в эфире!\nСмотреть стрим: https://twitch.tv/{streamer}"
                    context.bot.send_message(chat_id=int(chat_id), text=message)
                    # Отмечаем, что уведомление отправлено
                    redis_client.set(f'notified:{chat_id}:{streamer}', '1')
            else:
                # Сбрасываем отметку об отправленном уведомлении
                redis_client.delete(f'notified:{chat_id}:{streamer}')

# Команда /start
def start(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)
    # Добавляем пользователя в список подписчиков
    redis_client.sadd('subscribers', chat_id)

    # Создаем кнопки с именами стримеров
    keyboard = []
    for streamer in TWITCH_USERNAMES:
        keyboard.append([InlineKeyboardButton(streamer, callback_data=streamer)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с изображением и кнопками
    context.bot.send_photo(
        chat_id=chat_id,
        photo="https://axelencore.ru/wp-content/uploads/2024/09/Oreo.jpg",  # Замените на действительный URL изображения
        caption="Привет! Я бот Oreo - уведомляю о стримах Encore.\nВыберите стримеров, на которых хотите подписаться для получения уведомлений:",
        reply_markup=reply_markup
    )

# Обработка нажатий кнопок
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    streamer = query.data
    chat_id = str(query.message.chat.id)

    if not redis_client.sismember(f'subscriptions:{chat_id}', streamer):
        redis_client.sadd(f'subscriptions:{chat_id}', streamer)
        query.answer(f"Вы подписались на {streamer}")
    else:
        query.answer(f"Вы уже подписаны на {streamer}")

# Главная функция
def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Регистрация обработчиков
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
