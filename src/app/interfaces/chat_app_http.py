#!/usr/bin/env python3
"""
Streamlit веб-интерфейс для AI ассистента трейдера (с MCP через HTTP)

Использование:
    poetry run streamlit run src/app/interfaces/chat_app_http.py
    streamlit run src/app/interfaces/chat_app_http.py
"""

import json

import streamlit as st

from src.app.core import (
    get_http_client,
    get_settings,
    get_tools_for_llm,
    get_trading_system_prompt,
    run_conversation_with_tools,
)


def main() -> None:  # noqa: C901
    """Главная функция Streamlit приложения"""
    st.set_page_config(page_title="AI Трейдер (Finam + MCP)", page_icon="🤖", layout="wide")

    # Заголовок
    st.title("🤖 AI Ассистент Трейдера (MCP REST)")
    st.caption("Интеллектуальный помощник для работы с Finam TradeAPI через MCP REST API")

    # Sidebar с настройками
    with st.sidebar:
        st.header("⚙️ Настройки")
        settings = get_settings()
        st.info(f"**Модель:** {settings.openrouter_model}")

        account_id = st.text_input("ID счета", value="", help="Оставьте пустым если не требуется")

        use_simple_prompt = st.checkbox("Простой промпт", value=False, help="Использовать упрощенный системный промпт")

        if st.button("🔄 Очистить историю"):
            st.session_state.messages = []
            st.session_state.mcp_tools = None
            st.rerun()

        st.markdown("---")

        # Статус MCP API и авторизация
        with st.expander("🔐 Статус подключения", expanded=True):
            try:
                mcp_client = get_http_client()
                response = mcp_client.session.get(f"{mcp_client.base_url}/health", timeout=5)
                if response.status_code == 200:
                    st.success("✅ MCP API: подключен")

                    # Проверяем статус авторизации через специальный tool
                    try:
                        auth_result = mcp_client.call_tool("get_auth_info", {})
                        auth_info = json.loads(auth_result)

                        if auth_info.get("has_token"):
                            st.success("✅ Finam API: авторизован")
                            mode = auth_info.get("mode", "unknown")
                            if mode == "auth_manager":
                                st.info("🔄 Режим: API ключ (автообновление)")
                                lifetime = auth_info.get("token_lifetime")
                                if lifetime:
                                    st.caption(f"⏱️ Токен действует: {lifetime}")
                            else:
                                st.info("🔑 Режим: JWT токен напрямую")

                            account_ids = auth_info.get("account_ids", [])
                            if account_ids:
                                st.caption(f"📊 Счета: {', '.join(account_ids)}")

                            if auth_info.get("readonly"):
                                st.warning("⚠️ Режим только для чтения")
                        else:
                            st.warning("⚠️ Finam API: не авторизован")
                            st.caption("Установите FINAM_API_KEY в .env")
                    except Exception:
                        st.info("ℹ️ Finam API: статус недоступен")
                else:
                    st.error(f"❌ MCP API: ошибка ({response.status_code})")
            except Exception as e:
                st.error(f"❌ MCP API: недоступен")
                st.caption(f"Ошибка: {str(e)}")

        # Информация о MCP инструментах
        if "mcp_tools" in st.session_state and st.session_state.mcp_tools:
            with st.expander("🔧 MCP Инструменты", expanded=False):
                st.write(f"Загружено: **{len(st.session_state.mcp_tools)}** инструментов")
                for tool in st.session_state.mcp_tools:
                    st.markdown(f"- `{tool['function']['name']}`")

        st.markdown("---")
        st.markdown("### 💡 Примеры вопросов:")
        st.markdown("""
        - Какая цена Сбербанка?
        - Покажи мой портфель
        - Что в стакане по Газпрому?
        - Покажи свечи YNDX за последние дни
        - Какие у меня активные ордера?
        - Расскажи про акцию SBER@MISX
        - Какие есть опционы на Газпром?
        """)

    # Инициализация состояния
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Загрузка MCP инструментов (один раз)
    if "mcp_tools" not in st.session_state:
        with st.spinner("🔧 Загрузка MCP инструментов..."):
            try:
                # Проверяем доступность MCP API
                http_client = get_http_client()
                if not http_client.health_check():
                    st.error("❌ MCP API сервер недоступен. Убедитесь что он запущен.")
                    st.stop()

                tools = get_tools_for_llm()
                st.session_state.mcp_tools = tools
                st.success(f"✅ Загружено {len(tools)} MCP инструментов")
            except Exception as e:
                st.error(f"❌ Ошибка загрузки MCP инструментов: {e}")
                st.stop()

    tools = st.session_state.mcp_tools

    # Отображение истории сообщений
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Показываем использованные tool calls
            if "tool_calls" in message and message["tool_calls"]:
                with st.expander(f"🔧 Использовано инструментов: {len(message['tool_calls'])}"):
                    for i, call in enumerate(message["tool_calls"], 1):
                        st.markdown(f"**{i}. {call['name']}**")
                        st.json(call["arguments"])
                        with st.expander("Результат"):
                            try:
                                result_json = json.loads(call["result"])
                                st.json(result_json)
                            except Exception:
                                st.code(call["result"])

    # Поле ввода
    if prompt := st.chat_input("Напишите ваш вопрос..."):
        # Добавляем сообщение пользователя
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Формируем историю для LLM
        from src.app.core import get_simple_system_prompt

        system_prompt = get_simple_system_prompt() if use_simple_prompt else get_trading_system_prompt()
        conversation_history = [{"role": "system", "content": system_prompt}]

        # Добавляем account_id если есть
        if account_id:
            conversation_history.append({
                "role": "system",
                "content": f"ID счета пользователя: {account_id}. Используй его автоматически где требуется.",
            })

        # Добавляем историю сообщений
        for msg in st.session_state.messages:
            conversation_history.append({"role": msg["role"], "content": msg["content"]})

        # Получаем ответ от ассистента
        with st.chat_message("assistant"), st.spinner("Думаю и использую инструменты..."):
            try:
                # Запускаем conversation с MCP tools (теперь синхронно!)
                final_answer, tool_calls = run_conversation_with_tools(
                    messages=conversation_history,
                    tools=tools,
                    temperature=0.3,
                    max_iterations=5,
                )

                # Показываем использованные инструменты
                if tool_calls:
                    st.info(f"🔧 Использовано инструментов: {len(tool_calls)}")
                    with st.expander("Детали вызовов инструментов"):
                        for i, call in enumerate(tool_calls, 1):
                            st.markdown(f"**{i}. {call['name']}**")
                            st.json(call["arguments"])
                            st.code(call["result"][:500] + "..." if len(call["result"]) > 500 else call["result"])

                # Выводим финальный ответ
                st.markdown(final_answer)

                # Сохраняем сообщение ассистента
                message_data = {"role": "assistant", "content": final_answer}
                if tool_calls:
                    message_data["tool_calls"] = tool_calls
                st.session_state.messages.append(message_data)

            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
                import traceback

                with st.expander("Stack trace"):
                    st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
