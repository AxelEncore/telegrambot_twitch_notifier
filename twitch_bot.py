import os
import logging
import requests
import redis
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    MessageHandler,
    Filters
)


# Настройки
TELEGRAM_TOKEN = '8049016680:AAFo45bEX8HlSnKiX_bfnYY_KhaWaUJu7PE'  # Замените на токен вашего бота
TWITCH_CLIENT_ID = 'w2y2t05i7iwk43yj6ncyvtvnqzmkze'  # Замените на ваш Twitch Client ID
TWITCH_CLIENT_SECRET = 'egxo7iiha9dhv6ap4z1k4rvfpltbzg'  # Замените на ваш Twitch Client Secret
TWITCH_USERNAMES = ['axelencore', 'yatoencoree', 'julia_encore', 'aliseencore', 'hotabych4', 'waterspace17']  # Список стримеров для отслеживания
CHECK_INTERVAL = 60  # Интервал проверки стримов (в секундах)

# Настройка Redis
REDIS_URL = os.getenv('REDIS_URL')
redis_client = redis.Redis.from_url(REDIS_URL)

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Основная клавиатура с кнопками "Подписаться" и "Отписаться"
reply_keyboard = [
    [KeyboardButton("Подписаться"), KeyboardButton("Отписаться")]
]
main_reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

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

# Функция для проверки стримов
def check_streams(context: CallbackContext):
    twitch_oauth_token = get_twitch_oauth_token()
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {twitch_oauth_token}'
    }
    params = [('user_login', username) for username in TWITCH_USERNAMES]
    response = requests.get('https://api.twitch.tv/helix/streams', headers=headers, params=params)
    data = response.json()
    active_streams = [stream['user_login'] for stream in data.get('data', [])]

    subscribers = redis_client.smembers('subscribers')
    for chat_id_bytes in subscribers:
        chat_id = chat_id_bytes.decode()
        subscriptions = redis_client.smembers(f'subscriptions:{chat_id}')
        subscriptions = {s.decode() for s in subscriptions}
        for streamer in subscriptions:
            if streamer in active_streams:
                notified_key = f'notified:{chat_id}:{streamer}'
                if not redis_client.exists(notified_key):
                    message = f"🔴 {streamer} сейчас в эфире!\nЗаглядывай на стрим: https://twitch.tv/{streamer}"
                    context.bot.send_message(chat_id=int(chat_id), text=message, reply_markup=main_reply_markup)
                    redis_client.set(notified_key, '1')
            else:
                redis_client.delete(f'notified:{chat_id}:{streamer}')

# Обработчик команды /start
def start(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)
    redis_client.sadd('subscribers', chat_id)

    # Отправляем приветственное сообщение с кнопками
    message = context.bot.send_photo(
        chat_id=chat_id,
        photo="https://axelencore.ru/wp-content/uploads/2024/09/Oreo.jpg",  # Убедитесь, что URL корректен
        text="Привет! Я бот Oreo - уведомляю о стримах семьи Encore.",
        reply_markup=main_reply_markup
    )

    # Отправляем варианты подписки
    send_subscribe_options(update, context)

    # Удаляем команду /start
    try:
        context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения /start: {e}")

# Обработчик текстовых сообщений
def text_message_handler(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)
    text = update.message.text

    if text == "Подписаться":
        delete_previous_bot_message(chat_id, context)
        send_subscribe_options(update, context)
    elif text == "Отписаться":
        delete_previous_bot_message(chat_id, context)
        send_unsubscribe_options(update, context)
    else:
        context.bot.send_message(chat_id=chat_id, text="Пожалуйста, выберите действие с помощью кнопок ниже.", reply_markup=main_reply_markup)

    # Удаляем сообщение пользователя с текстом кнопки "Подписаться" или "Отписаться"
    if text in ["Подписаться", "Отписаться"]:
        try:
            context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения пользователя: {e}")

# Функция для отправки вариантов подписки
def send_subscribe_options(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)

    # Создаем кнопки с именами стримеров для подписки
    keyboard = []
    for streamer in TWITCH_USERNAMES:
        keyboard.append([InlineKeyboardButton(streamer, callback_data=f'subscribe:{streamer}')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с изображением и кнопками
    message = context.bot.send_message(
        chat_id=chat_id,
        caption="Выберите стримеров, на которых хотите подписаться для получения уведомлений:",
        reply_markup=reply_markup
    )

    # Сохраняем ID сообщения
    redis_client.set(f'last_message:{chat_id}', message.message_id)

# Функция для отправки вариантов отписки
def send_unsubscribe_options(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)

    # Получаем подписки пользователя
    subscriptions = redis_client.smembers(f'subscriptions:{chat_id}')
    subscriptions = [s.decode() for s in subscriptions]

    if not subscriptions:
        context.bot.send_message(chat_id=chat_id, text="Вы не подписаны ни на одного стримера.", reply_markup=main_reply_markup)
        return

    # Создаем кнопки с именами стримеров для отписки
    keyboard = []
    for streamer in subscriptions:
        keyboard.append([InlineKeyboardButton(streamer, callback_data=f'unsubscribe:{streamer}')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с вариантами отписки
    message = context.bot.send_message(
        chat_id=chat_id,
        text="Выберите стримеров, от которых вы хотите отписаться:",
        reply_markup=reply_markup
    )

    # Сохраняем ID сообщения
    redis_client.set(f'last_message:{chat_id}', message.message_id)

# Функция для удаления предыдущего сообщения бота
def delete_previous_bot_message(chat_id, context):
    message_id = redis_client.get(f'last_message:{chat_id}')
    if message_id:
        try:
            context.bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение: {e}")
        finally:
            redis_client.delete(f'last_message:{chat_id}')

# Обработчик нажатий на кнопки
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    chat_id = str(query.message.chat.id)

    if data.startswith('subscribe:'):
        streamer = data.split(':', 1)[1]
        if not redis_client.sismember(f'subscriptions:{chat_id}', streamer):
            redis_client.sadd(f'subscriptions:{chat_id}', streamer)
            query.answer(f"Вы успешно подписались на {streamer}")
        else:
            query.answer(f"Вы уже подписаны на {streamer}")
    elif data.startswith('unsubscribe:'):
        streamer = data.split(':', 1)[1]
        if redis_client.sismember(f'subscriptions:{chat_id}', streamer):
            redis_client.srem(f'subscriptions:{chat_id}', streamer)
            query.answer(f"Вы успешно отписались от {streamer}")
            # Обновляем список подписок
            subscriptions = redis_client.smembers(f'subscriptions:{chat_id}')
            subscriptions = [s.decode() for s in subscriptions]
            if subscriptions:
                # Обновляем клавиатуру
                keyboard = []
                for s in subscriptions:
                    keyboard.append([InlineKeyboardButton(s, callback_data=f'unsubscribe:{s}')])
                reply_markup = InlineKeyboardMarkup(keyboard)
                query.edit_message_text(text="Выберите стримеров, от которых вы хотите отписаться:", reply_markup=reply_markup)
            else:
                query.edit_message_text(text="Вы не подписаны ни на одного стримера.")
        else:
            query.answer(f"Вы не были подписаны на {streamer}")
    else:
        query.answer("Неизвестная команда.")

# Главная функция
def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Регистрация обработчиков
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text_message_handler))

    # Планирование задачи проверки стримов
    job_queue = updater.job_queue
    job_queue.run_repeating(check_streams, interval=CHECK_INTERVAL, first=10)

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
