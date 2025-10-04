import json
from typing import Any

import requests

from .config import get_settings


def call_llm(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = None) -> dict[str, Any]:
    """Простой вызов LLM без tools (legacy метод для обратной совместимости)"""
    s = get_settings()
    payload: dict[str, Any] = {
        "model": s.openrouter_model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    r = requests.post(
        f"{s.openrouter_base}/chat/completions",
        headers={
            "Authorization": f"{s.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def call_llm_with_tools(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]],
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """
    Вызов LLM с поддержкой function calling (tools)

    Args:
        messages: История сообщений
        tools: Список доступных инструментов в формате OpenAI
        temperature: Температура генерации (0.0-1.0)
        max_tokens: Максимальное количество токенов в ответе

    Returns:
        Ответ от LLM с возможными tool_calls
    """
    s = get_settings()
    payload: dict[str, Any] = {
        "model": s.openrouter_model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",  # LLM сам решает, когда использовать tools
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    r = requests.post(
        f"{s.openrouter_base}/chat/completions",
        headers={
            "Authorization": f"Bearer {s.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,  # Увеличенный timeout для tool calls
    )
    r.raise_for_status()
    return r.json()


def run_conversation_with_tools(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]],
    max_iterations: int = 5,
    temperature: float = 0.2,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Запустить conversation loop с поддержкой MCP tools (синхронная версия)

    Args:
        messages: История сообщений
        tools: Список доступных MCP инструментов
        max_iterations: Максимальное количество итераций (защита от бесконечных циклов)
        temperature: Температура генерации

    Returns:
        Tuple из (финальный ответ, история tool_calls)
    """
    from .mcp_http_client import execute_tool_call

    tool_calls_history = []
    conversation_messages = messages.copy()

    for _ in range(max_iterations):
        # Вызываем LLM с tools
        response = call_llm_with_tools(conversation_messages, tools, temperature)

        message = response["choices"][0]["message"]

        # Если нет tool_calls, возвращаем финальный ответ
        if not message.get("tool_calls"):
            return message.get("content", ""), tool_calls_history

        # Добавляем сообщение ассистента в историю
        conversation_messages.append(message)

        # Выполняем все tool calls
        for tool_call in message["tool_calls"]:
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])

            # Выполняем MCP tool call (теперь синхронно через HTTP)
            tool_result = execute_tool_call(function_name, function_args)

            # Сохраняем в историю
            tool_calls_history.append({
                "name": function_name,
                "arguments": function_args,
                "result": tool_result,
            })

            # Добавляем результат в контекст для LLM
            conversation_messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": tool_result,
            })

    # Если достигли максимума итераций, возвращаем последнее сообщение
    return "Достигнуто максимальное количество итераций инструментов.", tool_calls_history
