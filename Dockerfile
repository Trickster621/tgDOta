FROM python:3.11-slim

# Установка зависимостей для Playwright
RUN apt-get update && apt-get install -y \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxrandr2 \
    libxfixes3 \
    libxi6 \
    libasound2 \
    libatk1.0-0 \
    libcups2 \
    libnss3 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libgbm1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы
COPY . .

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем браузеры для Playwright
RUN playwright install --with-deps

# Команда запуска
CMD ["python", "bot.py"]
