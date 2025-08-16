# Используем официальный Python образ
FROM python:3.11-slim

# Рабочая директория
WORKDIR /app

# Копируем файлы
COPY bot.py requirements.txt ./

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Запуск бота
CMD ["python", "bot.py"]
