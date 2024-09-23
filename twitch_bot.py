import json
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from threading import Timer

# Логгирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Словарь для хранения подписок пользователей (загружаем при старте)
user_subscriptions = {}

# Словарь для отслеживания активных стримов
active_streams = {username: False for username in TWITCH_USERNAMES}

# Функция для чтения подписок из файла
def load_subscriptions():
    global user_subscriptions
    if os.path.exists(SUBSCRIPTIONS_FILE):
        try:
            with open(SUBSCRIPTIONS_FILE, 'r') as f:
                # Проверяем, если файл пустой
                if os.stat(SUBSCRIPTIONS_FILE).st_size == 0:
                    user_subscriptions = {}
                else:
                    user_subscriptions = json.load(f)
                logger.info(f"Подписки успешно загружены: {user_subscriptions}")
        except (json.JSONDecodeError, FileNotFoundError):
            # Если файл поврежден или его нет, инициализируем пустой словарь
            logger.error("Ошибка загрузки файла подписок. Инициализация пустого словаря.")
            user_subscriptions = {}
            save_subscriptions()
    else:
        user_subscriptions = {}

# Функция для сохранения подписок в файл
def save_subscriptions():
    try:
        with open(SUBSCRIPTIONS_FILE, 'w') as f:
            json.dump(user_subscriptions, f, indent=4)  # Добавим форматирование для читаемости
        logger.info(f"Подписки успешно сохранены: {user_subscriptions}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении подписок: {e}")

# Остальной код (проверка стримов и логика работы бота) остается без изменений

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
    # Инициализация подписок для нового пользователя
    if chat_id not in user_subscriptions:
        user_subscriptions[chat_id] = []  # Инициализация пустого списка подписок
        save_subscriptions()  # Сохраняем файл после инициализации

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
    
    # Убедимся, что у пользователя есть ключ в словаре, если он уже не был инициализирован
    if chat_id not in user_subscriptions:
        user_subscriptions[chat_id] = []  # Инициализация подписок для нового пользователя
    
    # Добавление стримера в подписки
    if streamer not in user_subscriptions[chat_id]:
        user_subscriptions[chat_id].append(streamer)
        save_subscriptions()  # Сохранение подписок после изменений
        query.answer()  # Отправляем подтверждение нажатия
        context.bot.send_message(chat_id=chat_id, text=f"Вы подписались на стримы от {streamer}")
    else:
        query.answer()  # Если уже подписан, не добавляем повторно
        context.bot.send_message(chat_id=chat_id, text=f"Вы уже подписаны на {streamer}")

# Запуск бота
def main():
    load_subscriptions()  # Загружаем подписки из файла при старте
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
