# Упрощенный Dockerfile без Poetry (более надежная сборка)
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY requirements.txt ./

# Устанавливаем зависимости через pip
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY README.md .

# Создаем непривилегированного пользователя
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Установка PYTHONPATH для корректных импортов
ENV PYTHONPATH=/app

# Открываем порт для Streamlit
EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# По умолчанию запускаем HTTP-версию Streamlit приложения
CMD ["python", "-m", "streamlit", "run", "src/app/interfaces/chat_app_http.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--server.fileWatcherType=none"]

