"""
REST API wrapper для MCP сервера

Этот модуль предоставляет HTTP интерфейс для взаимодействия с MCP инструментами,
избегая проблем с импортами и subprocess в Docker.
"""

import logging
import os
import sys
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.adapters.finam_client import FinamAPIClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Логгер для этого модуля
logger = logging.getLogger(__name__)

# Настраиваем уровень для библиотек
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("fastapi").setLevel(logging.INFO)

# Создаем FastAPI приложение
app = FastAPI(
    title="Finam MCP REST API",
    description="REST API для взаимодействия с Finam TradeAPI через MCP протокол",
    version="1.0.0",
)

# Глобальный клиент API
logger.info("🚀 Инициализация Finam API Client...")
finam_client = FinamAPIClient()
logger.info("✅ Finam API Client инициализирован")


# Pydantic модели для запросов
class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any]


class ToolCallResponse(BaseModel):
    success: bool
    result: Any
    error: str | None = None


class Tool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


# Эндпоинты API


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "service": "finam-mcp-api"}


@app.get("/tools", response_model=list[Tool])
async def list_tools():
    """
    Получить список всех доступных MCP инструментов

    Returns:
        Список инструментов в формате OpenAI function calling
    """
    tools = [
        # AuthService
        Tool(
            name="auth",
            description="Получить JWT-токен по API-ключу для авторизации в системе",
            input_schema={
                "type": "object",
                "properties": {"secret": {"type": "string", "description": "Секретный API-ключ"}},
                "required": ["secret"],
            },
        ),
        Tool(
            name="get_auth_info",
            description="Получить информацию о текущей авторизации",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_session_details",
            description="Получить информацию о текущей торговой сессии (TokenDetails). Возвращает: created_at, expires_at, md_permissions, account_ids, readonly",
            input_schema={
                "type": "object",
                "properties": {
                    "token": {
                        "type": "string",
                        "description": "JWT токен для проверки (опционально, по умолчанию текущий)",
                    }
                },
                "required": [],
            },
        ),
        # MarketDataService
        Tool(
            name="get_quote",
            description="Получить последнюю котировку инструмента. Возвращает: timestamp, ask, ask_size, bid, bid_size, last, last_size, volume, turnover, open, high, low, close, change. Для опционов: греки (delta, gamma)",
            input_schema={
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "Символ инструмента (например, SBER@MISX)"}},
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_orderbook",
            description="Получить биржевой стакан (best bid/ask). Каждый уровень: price, sell_size, buy_size, action, mpid (код участника), timestamp",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Символ инструмента"},
                    "depth": {"type": "integer", "description": "Глубина стакана (кол-во уровней)", "default": 10},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_candles",
            description="Получить исторические OHLCV свечи. Каждый бар: timestamp, open, high, low, close, volume",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Символ инструмента"},
                    "timeframe": {
                        "type": "string",
                        "description": "Интервал (1min/5min/15min/hour/day)",
                        "default": "day",
                    },
                    "start": {"type": "string", "description": "Начало периода (ISO 8601)"},
                    "end": {"type": "string", "description": "Конец периода (ISO 8601)"},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_latest_trades",
            description="Получить последние сделки по инструменту. Каждая сделка: trade_id, mpid, timestamp, price, size, side (buy/sell)",
            input_schema={
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "Символ инструмента"}},
                "required": ["symbol"],
            },
        ),
        # AccountsService
        Tool(
            name="get_account",
            description="Получить подробную информацию о счёте: тип, статус, капитал (equity), нереализованную прибыль, денежные балансы (cash), открытые позиции (positions), портфель по секциям (portfolio)",
            input_schema={
                "type": "object",
                "properties": {"account_id": {"type": "string", "description": "ID торгового счета"}},
                "required": ["account_id"],
            },
        ),
        Tool(
            name="get_transactions",
            description="Получить операции по счёту: ввод/вывод средств, комиссии, начисления дивидендов. Каждая операция: id, category (funding/fee), timestamp, symbol, change, trade, transaction_category",
            input_schema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "ID счёта"},
                    "start": {"type": "string", "description": "Начало периода (ISO 8601)"},
                    "end": {"type": "string", "description": "Конец периода (ISO 8601)"},
                    "limit": {"type": "integer", "description": "Макс. число записей"},
                },
                "required": ["account_id"],
            },
        ),
        Tool(
            name="get_trades",
            description="Получить историю исполненных ордеров. Каждая сделка: trade_id, symbol, price, size, side (buy/sell), timestamp, order_id, account_id",
            input_schema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "ID счёта"},
                    "start": {"type": "string", "description": "Начало периода (ISO 8601)"},
                    "end": {"type": "string", "description": "Конец периода (ISO 8601)"},
                    "limit": {"type": "integer", "description": "Макс. число записей"},
                },
                "required": ["account_id"],
            },
        ),
        Tool(
            name="get_positions",
            description="Получить открытые позиции. Каждая позиция: symbol, quantity, average_price, current_price, market_value, unrealized_profit",
            input_schema={
                "type": "object",
                "properties": {"account_id": {"type": "string", "description": "ID счёта"}},
                "required": ["account_id"],
            },
        ),
        # OrdersService
        Tool(
            name="get_orders",
            description="Получить активные и исторические ордеры. Каждый ордер: order_id, status (New/Accepted/Rejected/PartiallyFilled/Filled/Withdrawn), параметры, временные метки",
            input_schema={
                "type": "object",
                "properties": {"account_id": {"type": "string", "description": "ID счёта"}},
                "required": ["account_id"],
            },
        ),
        Tool(
            name="get_order",
            description="Получить информацию об ордере",
            input_schema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "order_id": {"type": "string"},
                },
                "required": ["account_id", "order_id"],
            },
        ),
        Tool(
            name="create_order",
            description="Создать новый биржевой ордер. order_data должен содержать: symbol, quantity (лоты), side (buy/sell), type (market/limit/stop/stop_limit/take_profit), time_in_force (day/gtc/ioc/fok), limit_price, stop_price, stop_condition (bid/ask/last)",
            input_schema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "ID счёта"},
                    "order_data": {"type": "object", "description": "Параметры ордера"},
                },
                "required": ["account_id", "order_data"],
            },
        ),
        Tool(
            name="cancel_order",
            description="Отменить ордер",
            input_schema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "order_id": {"type": "string"},
                },
                "required": ["account_id", "order_id"],
            },
        ),
        # AssetsService
        Tool(
            name="get_asset",
            description="Получить подробную информацию об инструменте: symbol, board, ticker, mic, isin, type (акция/облигация/фьючерс/опцион), name, decimals, min_step, lot_size, expiration_date, quote_currency",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Идентификатор инструмента (например, SBER@MISX)"},
                    "account_id": {"type": "string", "description": "ID счёта (обязательно)"},
                },
                "required": ["symbol", "account_id"],
            },
        ),
        Tool(
            name="get_asset_params",
            description="Получить параметры торговли инструмента на счёте: tradeable (можно ли торговать), longable/shortable, риски (initial_margin, maintain_margin, risk_rate)",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Идентификатор инструмента"},
                    "account_id": {"type": "string", "description": "ID счёта"},
                },
                "required": ["symbol", "account_id"],
            },
        ),
        Tool(
            name="get_options_chain",
            description="Получить список опционов на базовый актив. Каждый опцион: symbol, type (call/put), contract_size, strike, multiplier, периоды торгов и экспирации",
            input_schema={
                "type": "object",
                "properties": {
                    "underlying_symbol": {"type": "string", "description": "Базовый актив (например, SBER)"}
                },
                "required": ["underlying_symbol"],
            },
        ),
    ]

    return tools


@app.post("/call_tool", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """
    Вызвать MCP инструмент

    Args:
        request: Запрос с именем инструмента и аргументами

    Returns:
        Результат выполнения инструмента
    """
    tool_name = request.tool_name
    arguments = request.arguments

    logger.info(f"🔧 Вызов tool: {tool_name} с аргументами: {list(arguments.keys())}")

    try:
        # Маршрутизация на соответствующий метод
        if tool_name == "auth":
            result = finam_client.auth(arguments["secret"])
        elif tool_name == "get_auth_info":
            result = finam_client.get_auth_info()
        elif tool_name == "get_session_details":
            token = arguments.get("token")
            result = finam_client.get_session_details(token)
        elif tool_name == "get_quote":
            result = finam_client.get_quote(arguments["symbol"])
        elif tool_name == "get_orderbook":
            depth = arguments.get("depth", 10)
            result = finam_client.get_orderbook(arguments["symbol"], depth)
        elif tool_name == "get_candles":
            result = finam_client.get_candles(
                arguments["symbol"],
                arguments.get("timeframe", "day"),
                arguments.get("start"),
                arguments.get("end"),
            )
        elif tool_name == "get_latest_trades":
            result = finam_client.get_latest_trades(arguments["symbol"])
        elif tool_name == "get_account":
            result = finam_client.get_account(arguments["account_id"])
        elif tool_name == "get_transactions":
            result = finam_client.get_transactions(
                arguments["account_id"],
                arguments.get("start"),
                arguments.get("end"),
                arguments.get("limit"),
            )
        elif tool_name == "get_trades":
            result = finam_client.get_trades(
                arguments["account_id"],
                arguments.get("start"),
                arguments.get("end"),
                arguments.get("limit"),
            )
        elif tool_name == "get_positions":
            result = finam_client.get_positions(arguments["account_id"])
        elif tool_name == "get_orders":
            result = finam_client.get_orders(arguments["account_id"])
        elif tool_name == "get_order":
            result = finam_client.get_order(arguments["account_id"], arguments["order_id"])
        elif tool_name == "create_order":
            result = finam_client.create_order(arguments["account_id"], arguments["order_data"])
        elif tool_name == "cancel_order":
            result = finam_client.cancel_order(arguments["account_id"], arguments["order_id"])
        elif tool_name == "get_asset":
            result = finam_client.get_asset(arguments["symbol"], arguments["account_id"])
        elif tool_name == "get_asset_params":
            result = finam_client.get_asset_params(arguments["symbol"], arguments["account_id"])
        elif tool_name == "get_options_chain":
            result = finam_client.get_options_chain(arguments["underlying_symbol"])
        else:
            logger.error(f"❌ Неизвестный tool: {tool_name}")
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

        logger.info(f"✅ Tool {tool_name} выполнен успешно")
        return ToolCallResponse(success=True, result=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Ошибка при выполнении tool {tool_name}: {type(e).__name__}: {str(e)}")
        return ToolCallResponse(
            success=False,
            result=None,
            error=str(e),
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("MCP_API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
