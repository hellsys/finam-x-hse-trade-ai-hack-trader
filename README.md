# 🤖 Finam AI Trader — AI Ассистент для Фондовой Биржи

> Интеллектуальный помощник для работы с Finam TradeAPI с поддержкой 17 инструментов через REST API

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.118+-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red.svg)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

## 🌟 Возможности

### 17 MCP Инструментов для работы с биржей

#### 📊 Рыночные данные (4)
- **Котировки** — текущие цены и объемы
- **Биржевой стакан** — заявки на покупку/продажу
- **Исторические свечи** — OHLCV данные
- **Последние сделки** — лента сделок

#### 💼 Управление счётом (4)
- **Информация о счёте** — баланс, капитал, позиции
- **Транзакции** — ввод/вывод средств, комиссии
- **История сделок** — исполненные ордера
- **Открытые позиции** — текущий портфель

#### 📝 Торговые операции (4)
- **Список ордеров** — активные и исторические
- **Детали ордера** — полная информация
- **Создание ордера** — покупка/продажа
- **Отмена ордера** — отмена заявки

#### 🔍 Информация об инструментах (3)
- **Детали инструмента** — тикер, лот, валюта
- **Параметры торговли** — маржа, риски
- **Опционный ряд** — опционы на актив

#### 🔐 Авторизация (2)
- **Получение токена** — JWT авторизация
- **Детали сессии** — информация о сессии

## 🏗️ Архитектура

Микросервисная архитектура с двумя контейнерами:

```
┌──────────────────────────────────────────┐
│         Docker Network                    │
│                                           │
│  ┌─────────────────┐  ┌────────────────┐ │
│  │  Web UI         │  │  MCP REST API  │ │
│  │  (Streamlit)    │◄─┤  (FastAPI)     │ │
│  │  Port: 8501     │  │  Port: 8000    │ │
│  └─────────────────┘  └────────────────┘ │
│         │                      │          │
└─────────┼──────────────────────┼──────────┘
          │                      │
          ▼                      ▼
   OpenRouter API          Finam TradeAPI
```

**Компоненты:**
- **MCP REST API** — FastAPI сервер с 17 инструментами
- **Web UI** — Streamlit интерфейс с LLM интеграцией
- **HTTP Client** — синхронный клиент для MCP API

## 🚀 Быстрый старт

### Через Docker Compose (рекомендуется)

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd finam-x-hse-trade-ai-hack-trader

# 2. Настройте переменные окружения
cp .env.example .env
nano .env  # Добавьте OPENROUTER_API_KEY и FINAM_ACCESS_TOKEN

# 3. Запустите
docker-compose up -d

# 4. Откройте в браузере
# http://localhost:8501
```

**Готово!** 🎉

### Локальный запуск

#### Терминал 1: MCP REST API
```bash
export PYTHONPATH=$(pwd)/src
python -m uvicorn app.mcp_rest_api:app --reload
```

#### Терминал 2: Streamlit UI
```bash
export MCP_API_URL=http://localhost:8000
streamlit run src/app/interfaces/chat_app_http.py
```

## 📋 Требования

- Python 3.11+
- Docker и Docker Compose (для контейнеризации)
- OpenRouter API Key (для LLM)
- Finam Access Token (для торговли)

## 🔧 Конфигурация

### Переменные окружения (.env)

```env
# OpenRouter API (обязательно)
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=openai/gpt-4o-mini

# Finam TradeAPI (обязательно)
FINAM_ACCESS_TOKEN=your-token-here
FINAM_API_BASE_URL=https://api.finam.ru

# MCP API (автоматически в Docker)
MCP_API_URL=http://mcp-api:8000

# Отладка (опционально)
APP_DEBUG=false
```

### Поддерживаемые LLM модели

Через OpenRouter можно использовать:
- `anthropic/claude-3.5-sonnet` — лучшее качество
- `openai/gpt-4o-mini` — бюджетный вариант
- `openai/gpt-4-turbo` — баланс цены и качества
- `google/gemini-pro-1.5` — альтернатива

## 💡 Примеры использования

### Простые запросы

```
👤 Какая сейчас цена Сбербанка?
🤖 [вызывает get_quote("SBER@MISX")]
   📊 Сбербанк: 285.50 ₽ (+1.2%)

👤 Покажи мой портфель
🤖 [вызывает get_account + get_positions]
   💼 Баланс: 100,000 ₽
   📈 Открытые позиции: 3

👤 Последние сделки по Газпрому
🤖 [вызывает get_latest_trades("GAZP@MISX")]
   📊 Последние 10 сделок по Газпрому
```

### Сложные запросы

```
👤 Проанализируй акцию YNDX@MISX
🤖 [вызывает get_asset + get_quote + get_latest_trades]
   🔍 Полный анализ Яндекса с текущими данными

👤 Какие есть опционы на Сбербанк?
🤖 [вызывает get_options_chain("SBER@MISX")]
   📋 Список опционов с страйками и датами
```

## 📚 Документация

- **[QUICKSTART_HTTP.md](QUICKSTART_HTTP.md)** — Быстрый старт за 5 минут
- **[ARCHITECTURE_HTTP.md](ARCHITECTURE_HTTP.md)** — Подробная архитектура
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Развертывание в production
- **[BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md)** — Решение проблем со сборкой
- **[FIX_NOTES.md](FIX_NOTES.md)** — История исправлений

## 🔍 API Документация

После запуска MCP API доступна интерактивная документация:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI Schema:** http://localhost:8000/openapi.json

### Основные эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Проверка здоровья сервиса |
| GET | `/tools` | Список всех инструментов |
| POST | `/call_tool` | Вызов инструмента |

## 🐳 Docker

### Структура

```
docker-compose.yml
├── mcp-api (Dockerfile.mcp)
│   └── FastAPI сервер с инструментами
└── web (Dockerfile)
    └── Streamlit UI с LLM
```

### Команды

```bash
# Запуск
docker-compose up -d

# Логи
docker-compose logs -f

# Остановка
docker-compose down

# Пересборка
docker-compose build --no-cache
```

## 🧪 Тестирование

### Проверка MCP API

```bash
# Health check
curl http://localhost:8000/health

# Список инструментов
curl http://localhost:8000/tools | jq

# Вызов инструмента
curl -X POST http://localhost:8000/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_quote",
    "arguments": {"symbol": "SBER@MISX"}
  }' | jq
```

### Проверка Web UI

1. Откройте http://localhost:8501
2. Должно появиться: "✅ Загружено 17 MCP инструментов"
3. Задайте вопрос: "Какая цена Сбербанка?"

## ⚠️ Безопасность

**Важно:**
- Токены дают полный доступ к торговому счёту
- Используйте тестовые счета для разработки
- Настройте лимиты у брокера
- Не коммитьте `.env` в Git
- В production используйте Docker secrets

## 🤝 Вклад в проект

Этот проект создан для хакатона Finam x HSE Trade AI Hack.

## 📄 Лицензия

См. LICENSE файл в корне проекта.

## 🔗 Полезные ссылки

- **Finam TradeAPI Docs:** https://tradeapi.finam.ru/
- **OpenRouter:** https://openrouter.ai/
- **FastAPI:** https://fastapi.tiangolo.com/
- **Streamlit:** https://streamlit.io/

## 💬 Поддержка

Если возникли проблемы:
1. Проверьте документацию в папке проекта
2. Проверьте логи: `docker-compose logs`
3. Посмотрите [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md)
4. Проверьте [FIX_NOTES.md](FIX_NOTES.md)

---

**Версия:** 2.1.0  
**Дата:** 2025-10-04  
**Статус:** ✅ Готово к использованию

🚀 **Удачных торгов!**
