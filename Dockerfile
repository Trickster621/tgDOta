# Используем официальный образ Python как базовый
FROM python:3.10-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем системные зависимости
RUN apt-get update && \
    apt-get install -y libnss3 libxss1 libasound2 libatk1.0-0 libgtk-3-0 libcups2 libgdk-pixbuf2.0-0 libxcomposite1 libxrandr2 libxtst6 libx11-6 libxcursor1 libxfixes3 libxft2 libxi6 libxrender1 libxext6 libfontconfig1 libbz2-1.0 libglib2.0-0 libsm-dev libxau6 libxdmcp6 --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Копируем все файлы вашего проекта (включая bot.py) в рабочую директорию
COPY . .

# Команда для запуска бота, которую Railway будет использовать по умолчанию.
# Однако, мы будем использовать Procfile для более явного управления.
# CMD ["python", "bot.py"]
