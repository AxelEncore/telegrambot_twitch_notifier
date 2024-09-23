# Используем официальный базовый образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями в контейнер
COPY requirements.txt .

# Устанавливаем зависимости напрямую в контейнер
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Копируем все файлы проекта в контейнер
COPY . .

# Открываем порт (если это необходимо для вашего приложения)
EXPOSE 8443

# Определяем команду для запуска бота
CMD ["python", "twitch_bot.py"]
