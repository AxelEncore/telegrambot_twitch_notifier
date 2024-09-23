# Используем официальный базовый образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями в контейнер
COPY requirements.txt .

# Устанавливаем виртуальное окружение и необходимые зависимости
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# Обновляем PATH, чтобы использовать виртуальное окружение по умолчанию
ENV PATH="/opt/venv/bin:$PATH"

# Копируем остальные файлы в контейнер
COPY . .

# Открываем нужный порт (например, для webhook)
EXPOSE 8443

# Определяем команду по умолчанию для запуска приложения
CMD ["python", "twitch_bot.py"]
