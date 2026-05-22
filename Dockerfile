FROM python:3.11-slim

# Устанавливаем системные зависимости для сборки пакетов
# pkg-config и build-essential часто нужны для mysql/cryptography
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости отдельно, чтобы закэшировать этот слой
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код проекта
COPY . .

EXPOSE 8000

# Запускаем приложение
CMD ["python", "main.py"]