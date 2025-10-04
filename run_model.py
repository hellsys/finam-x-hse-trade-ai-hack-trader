#!/usr/bin/env python3
"""
Скрипт для прогона модели с использованием MCP сервера

Использование:
    python run_model.py "Купи 10 акций Сбербанка по рыночной цене"
    python run_model.py --input queries.txt --output results.csv
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

# Загружаем переменные окружения (опционально)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен, используем системные переменные окружения


class MCPModelRunner:
    """Класс для прогона модели через MCP сервер"""

    def __init__(
        self,
        mcp_api_url: str = "http://localhost:8000",
        openrouter_api_key: str | None = None,
        openrouter_model: str = "openai/gpt-4o-mini",
        account_id_placeholder: str = "{account_id}",
    ):
        self.mcp_api_url = mcp_api_url
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.openrouter_base = os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
        self.openrouter_model = openrouter_model
        self.account_id_placeholder = account_id_placeholder
        self.jwt_token = None
        self.tools = []

        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY не установлен")

    def get_jwt_token(self, api_key: str) -> str:
        """
        Получить JWT токен через MCP сервер

        Args:
            api_key: Finam API ключ

        Returns:
            JWT токен
        """
        print("🔐 Получение JWT токена...")
        response = requests.post(
            f"{self.mcp_api_url}/call_tool",
            json={"tool_name": "auth", "arguments": {"secret": api_key}},
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("success"):
            raise RuntimeError(f"Ошибка получения токена: {result.get('error')}")

        token = result["result"].get("token")
        if not token:
            raise RuntimeError("Токен не найден в ответе")

        print(f"✅ JWT токен получен: {token[:20]}...")
        self.jwt_token = token
        return token

    def load_tools(self) -> list[dict]:
        """
        Загрузить список доступных MCP tools

        Returns:
            Список tools в формате OpenAI
        """
        print("📥 Загрузка MCP tools...")
        response = requests.get(f"{self.mcp_api_url}/tools", timeout=10)
        response.raise_for_status()

        tools = response.json()
        print(f"✅ Загружено {len(tools)} tools")

        # Конвертируем в OpenAI формат
        openai_tools = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
            )

        self.tools = openai_tools
        return openai_tools

    def call_llm(self, messages: list[dict], tools: list[dict]) -> dict:
        """
        Вызвать LLM с tools

        Args:
            messages: История сообщений
            tools: Список доступных tools

        Returns:
            Ответ LLM
        """
        response = requests.post(
            f"{self.openrouter_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.openrouter_model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def extract_api_call(self, tool_name: str, arguments: dict) -> str:
        """
        Извлечь метод и slug API запроса из tool call

        Args:
            tool_name: Имя вызванного tool
            arguments: Аргументы tool

        Returns:
            Строка вида "POST /v1/accounts/{account_id}/orders"
        """
        # Маппинг tool_name -> (HTTP метод, путь)
        api_mapping = {
            # AuthService
            "auth": ("POST", "/v1/sessions"),
            "get_session_details": ("POST", "/v1/sessions/details"),
            # AccountsService
            "get_account": ("GET", "/v1/accounts/{account_id}"),
            "get_transactions": ("GET", "/v1/accounts/{account_id}/transactions"),
            "get_trades": ("GET", "/v1/accounts/{account_id}/trades"),
            "get_positions": ("GET", "/v1/accounts/{account_id}"),
            # OrdersService
            "get_orders": ("GET", "/v1/accounts/{account_id}/orders"),
            "get_order": ("GET", "/v1/accounts/{account_id}/orders/{order_id}"),
            "create_order": ("POST", "/v1/accounts/{account_id}/orders"),
            "cancel_order": ("DELETE", "/v1/accounts/{account_id}/orders/{order_id}"),
            # AssetsService
            "get_asset": ("GET", "/v1/assets/{symbol}"),
            "get_asset_params": ("GET", "/v1/assets/{symbol}/params"),
            "get_options_chain": ("GET", "/v1/assets/{underlying_symbol}/options"),
            # MarketDataService
            "get_quote": ("GET", "/v1/instruments/{symbol}/quotes/latest"),
            "get_orderbook": ("GET", "/v1/instruments/{symbol}/orderbook"),
            "get_candles": ("GET", "/v1/instruments/{symbol}/bars"),
            "get_latest_trades": ("GET", "/v1/instruments/{symbol}/trades/latest"),
        }

        if tool_name not in api_mapping:
            return f"UNKNOWN {tool_name}"

        method, path = api_mapping[tool_name]

        # Заменяем параметры в пути на плейсхолдеры или значения из arguments
        if "{account_id}" in path:
            # Всегда используем плейсхолдер для account_id
            pass  # Оставляем как есть
        if "{order_id}" in path:
            order_id = arguments.get("order_id", "{order_id}")
            path = path.replace("{order_id}", order_id)
        if "{symbol}" in path:
            symbol = arguments.get("symbol", "{symbol}")
            path = path.replace("{symbol}", symbol)
        if "{underlying_symbol}" in path:
            underlying_symbol = arguments.get("underlying_symbol", "{underlying_symbol}")
            path = path.replace("{underlying_symbol}", underlying_symbol)

        return f"{method} {path}"

    def process_query(self, query: str) -> dict:
        """
        Обработать текстовый запрос через модель

        Args:
            query: Текстовый запрос пользователя

        Returns:
            Результат обработки: {
                "query": str,
                "tool_name": str,
                "arguments": dict,
                "api_call": str,
                "success": bool,
                "error": str | None
            }
        """
        print(f"\n📝 Запрос: {query}")

        # Системный промпт
        system_prompt = """Ты - AI ассистент для работы с Finam TradeAPI.
Твоя задача - определить какой API метод нужно вызвать на основе запроса пользователя.

Важные правила:
1. Для account_id всегда используй плейсхолдер {account_id}
2. Для создания ордеров используй create_order
3. Для получения информации используй get_* методы
4. Для отмены ордеров используй cancel_order
5. Всегда указывай symbol в формате TICKER@EXCHANGE (например, SBER@MISX)
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        try:
            # Вызываем LLM
            print("🤖 Отправка запроса к LLM...")
            response = self.call_llm(messages, self.tools)

            choice = response["choices"][0]
            message = choice["message"]

            # Проверяем что LLM вызвал tool
            if not message.get("tool_calls"):
                return {
                    "query": query,
                    "tool_name": None,
                    "arguments": {},
                    "api_call": None,
                    "success": False,
                    "error": "LLM не вызвал ни один tool",
                    "response": message.get("content"),
                }

            # Берем первый tool call
            tool_call = message["tool_calls"][0]
            function = tool_call["function"]
            tool_name = function["name"]
            arguments = json.loads(function["arguments"])

            print(f"✅ LLM выбрал tool: {tool_name}")
            print(f"📋 Аргументы: {json.dumps(arguments, ensure_ascii=False, indent=2)}")

            # Извлекаем API call
            api_call = self.extract_api_call(tool_name, arguments)
            print(f"🎯 API вызов: {api_call}")

            return {
                "query": query,
                "tool_name": tool_name,
                "arguments": arguments,
                "api_call": api_call,
                "success": True,
                "error": None,
            }

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return {
                "query": query,
                "tool_name": None,
                "arguments": {},
                "api_call": None,
                "success": False,
                "error": str(e),
            }

    def run_batch(self, queries: list[str]) -> list[dict]:
        """
        Обработать несколько запросов

        Args:
            queries: Список текстовых запросов

        Returns:
            Список результатов
        """
        results = []
        for i, query in enumerate(queries, 1):
            print(f"\n{'=' * 60}")
            print(f"Запрос {i}/{len(queries)}")
            print(f"{'=' * 60}")

            result = self.process_query(query)
            results.append(result)

        return results


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="Прогон модели через MCP сервер")
    parser.add_argument("query", nargs="?", help="Текстовый запрос")
    parser.add_argument("--input", "-i", help="Файл с запросами (по одному на строку)")
    parser.add_argument("--output", "-o", help="Файл для сохранения результатов (CSV)")
    parser.add_argument("--api-key", help="Finam API ключ (или используйте FINAM_API_KEY в .env)")
    parser.add_argument("--mcp-url", default="http://localhost:8000", help="URL MCP API")
    parser.add_argument(
        "--model", default="openai/gpt-4o-mini", help="Модель OpenRouter"
    )

    args = parser.parse_args()

    # Проверяем входные данные
    if not args.query and not args.input:
        parser.error("Укажите либо query, либо --input")

    # Инициализируем runner
    runner = MCPModelRunner(
        mcp_api_url=args.mcp_url,
        openrouter_model=args.model,
    )

    # Получаем JWT токен если нужно
    api_key = args.api_key or os.getenv("FINAM_API_KEY")
    if api_key:
        try:
            runner.get_jwt_token(api_key)
        except Exception as e:
            print(f"⚠️ Не удалось получить JWT токен: {e}")
            print("Продолжаем без токена...")

    # Загружаем tools
    runner.load_tools()

    # Читаем запросы
    if args.input:
        input_file = Path(args.input)
        if not input_file.exists():
            print(f"❌ Файл не найден: {args.input}")
            sys.exit(1)

        with open(input_file, encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
    else:
        queries = [args.query]

    # Обрабатываем запросы
    results = runner.run_batch(queries)

    # Выводим сводку
    print(f"\n{'=' * 60}")
    print("📊 СВОДКА")
    print(f"{'=' * 60}")
    print(f"Всего запросов: {len(results)}")
    print(f"Успешно: {sum(1 for r in results if r['success'])}")
    print(f"Ошибок: {sum(1 for r in results if not r['success'])}")

    # Сохраняем результаты
    if args.output:
        import csv

        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["query", "api_call", "tool_name", "success", "error"],
            )
            writer.writeheader()

            for result in results:
                writer.writerow(
                    {
                        "query": result["query"],
                        "api_call": result["api_call"] or "",
                        "tool_name": result["tool_name"] or "",
                        "success": result["success"],
                        "error": result["error"] or "",
                    }
                )

        print(f"\n💾 Результаты сохранены в: {output_file}")
    else:
        # Выводим результаты в консоль
        print("\n📋 РЕЗУЛЬТАТЫ:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['query']}")
            if result["success"]:
                print(f"   ✅ {result['api_call']}")
            else:
                print(f"   ❌ {result['error']}")


if __name__ == "__main__":
    main()

