# Используем стандартный образ Python, который уже содержит все необходимые инструменты
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости для Chromium
RUN apt-get update && apt-get install -y \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libgtk-3-0 \
    libcups2 \
    libgdk-pixbuf2.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libxtst6 \
    libx11-6 \
    libxcursor1 \
    libxfixes3 \
    libxft2 \
    libxi6 \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libbz2-1.0 \
    libglib2.0-0 \
    libsm-dev \
    libxau6 \
    libxdmcp6 \
    --no-install-recommends

# Копируем файлы проекта
COPY . .

# Устанавливаем зависимости из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Указываем команду для запуска бота
CMD ["python", "bot.py"]
