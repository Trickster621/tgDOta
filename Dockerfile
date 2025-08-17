# Используем официальный образ Python как базовый
FROM python:3.10-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
# Это позволяет Docker кэшировать этот слой, если зависимости не меняются
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем системные зависимости, которые нужны для работы aiohttp и других библиотек
# Мы используем apt-get clean && apt-get update для предотвращения ошибки 100
# Затем устанавливаем пакеты без лишних рекомендаций
RUN apt-get update && \
    apt-get install -y libnss3 libxss1 libasound2 libatk1.0-0 libgtk-3-0 libcups2 libgdk-pixbuf2.0-0 libxcomposite1 libxrandr2 libxtst6 libx11-6 libxcursor1 libxfixes3 libxft2 libxi6 libxrender1 libxext6 libfontconfig1 libbz2-1.0 libglib2.0-0 libsm-dev libxau6 libxdmcp6 --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Копируем остальные файлы вашего проекта в рабочую директорию
COPY . .

# Команда, которая будет выполняться при запуске контейнера
# Убедитесь, что имя файла совпадает с вашим (например, my_bot.py)
CMD ["python", "your_bot_file_name.py"]
