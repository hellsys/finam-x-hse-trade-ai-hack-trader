"""
HTTP клиент для взаимодействия с MCP REST API

Этот модуль предоставляет простой интерфейс для вызова MCP инструментов
через HTTP REST API вместо прямого subprocess.
"""

import json
import os
from typing import Any

import requests


class MCPHttpClient:
    """HTTP клиент для взаимодействия с MCP REST API"""

    def __init__(self, base_url: str | None = None) -> None:
        """
        Инициализация HTTP клиента

        Args:
            base_url: URL MCP REST API сервера (по умолчанию из env)
        """
        self.base_url = base_url or os.getenv("MCP_API_URL", "http://localhost:8000")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def get_tools(self) -> list[dict[str, Any]]:
        """
        Получить список всех доступных MCP инструментов

        Returns:
            Список инструментов в формате OpenAI function calling
        """
        response = self.session.get(f"{self.base_url}/tools", timeout=10)
        response.raise_for_status()

        tools_data = response.json()

        # Конвертируем в формат OpenAI
        openai_tools = []
        for tool in tools_data:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            })

        return openai_tools

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        Вызвать MCP инструмент

        Args:
            tool_name: Название инструмента
            arguments: Аргументы для инструмента

        Returns:
            Результат выполнения инструмента в виде JSON строки
        """
        payload = {
            "tool_name": tool_name,
            "arguments": arguments,
        }

        response = self.session.post(
            f"{self.base_url}/call_tool",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()

        if not result["success"]:
            error_msg = result.get("error", "Unknown error")
            return json.dumps({"error": error_msg})

        # Возвращаем результат как JSON строку
        return json.dumps(result["result"], ensure_ascii=False)

    def health_check(self) -> bool:
        """
        Проверить доступность MCP API сервера

        Returns:
            True если сервер доступен, False иначе
        """
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


# Глобальный клиент (singleton)
_http_client: MCPHttpClient | None = None


def get_http_client() -> MCPHttpClient:
    """Получить глобальный экземпляр HTTP клиента"""
    global _http_client
    if _http_client is None:
        _http_client = MCPHttpClient()
    return _http_client


def get_tools_for_llm() -> list[dict[str, Any]]:
    """
    Получить список инструментов для использования с LLM

    Returns:
        Список tools в формате OpenAI function calling
    """
    client = get_http_client()
    return client.get_tools()


def execute_tool_call(tool_name: str, arguments: dict[str, Any]) -> str:
    """
    Выполнить вызов инструмента MCP

    Args:
        tool_name: Название инструмента
        arguments: Аргументы в виде словаря

    Returns:
        Результат выполнения инструмента
    """
    client = get_http_client()
    return client.call_tool(tool_name, arguments)
