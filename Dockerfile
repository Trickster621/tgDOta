FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# лучше задавать токен в переменной окружения при запуске контейнера:
# docker run -e BOT_TOKEN=... your-image
CMD ["python", "bot.py"]
