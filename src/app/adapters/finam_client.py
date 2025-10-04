"""
Клиент для работы с Finam TradeAPI
https://tradeapi.finam.ru/
"""

import json
import logging
import os
from typing import Any

import requests

# Настройка логгера
logger = logging.getLogger(__name__)


# Все mcp методы будут через этот класс
class FinamAPIClient:
    """
    Клиент для взаимодействия с Finam TradeAPI

    Документация: https://tradeapi.finam.ru/
    """

    def __init__(
        self,
        access_token: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        use_auth_manager: bool = True,
    ) -> None:
        """
        Инициализация клиента

        Args:
            access_token: JWT токен доступа (из переменной окружения FINAM_ACCESS_TOKEN)
            api_key: API ключ для получения JWT токена (из переменной окружения FINAM_API_KEY)
            base_url: Базовый URL API (по умолчанию из документации)
            use_auth_manager: Использовать менеджер авторизации для автоматического обновления токенов
        """
        self.base_url = base_url or os.getenv("FINAM_API_BASE_URL", "https://api.finam.ru")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        # Режим авторизации
        self.use_auth_manager = use_auth_manager
        self._auth_manager = None
        self._static_token = access_token or os.getenv("FINAM_ACCESS_TOKEN", "")

        # Если есть API ключ и включен auth manager - используем его
        if use_auth_manager:
            api_key_to_use = api_key or os.getenv("FINAM_API_KEY", "")
            if api_key_to_use:
                # Используем относительный импорт для совместимости с Docker
                try:
                    from ..core.auth import FinamAuthManager
                except ImportError:
                    # Fallback на абсолютный импорт (для локального запуска)
                    from src.app.core.auth import FinamAuthManager

                self._auth_manager = FinamAuthManager(
                    api_key=api_key_to_use,
                    base_url=self.base_url,
                )

        # Если есть статический токен - используем его
        if self._static_token and not self._auth_manager:
            self.session.headers.update({
                "Authorization": f"Bearer {self._static_token}",
            })

    def _get_current_token(self) -> str | None:
        """
        Получить текущий токен для авторизации

        Returns:
            JWT токен или None
        """
        # Если используется auth manager - получаем токен через него
        if self._auth_manager:
            return self._auth_manager.get_jwt_token()

        # Иначе используем статический токен
        return self._static_token

    def _update_auth_header(self) -> None:
        """Обновить Authorization заголовок с текущим токеном"""
        token = self._get_current_token()
        if token:
            self.session.headers.update({
                "Authorization": f"{token}",
            })

    def execute_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """
        Выполнить HTTP запрос к Finam TradeAPI

        Args:
            method: HTTP метод (GET, POST, DELETE и т.д.)
            path: Путь API (например, /v1/instruments/SBER@MISX/quotes/latest)
            **kwargs: Дополнительные параметры для requests

        Returns:
            Ответ API в виде словаря

        Raises:
            requests.HTTPError: Если запрос завершился с ошибкой
        """
        # Обновляем токен перед запросом (если используется auth manager)
        if self._auth_manager:
            self._update_auth_header()

        url = f"{self.base_url}{path}"

        # Логируем запрос
        log_data = {
            "method": method,
            "url": url,
            "params": kwargs.get("params"),
            "json": self._mask_sensitive_data(kwargs.get("json")),
        }
        logger.info(f"📤 Finam API Request: {method} {path}")
        logger.debug(f"Request details: {json.dumps(log_data, ensure_ascii=False, indent=2)}")

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()

            # Если ответ пустой (например, для DELETE)
            if not response.content:
                result = {"status": "success", "message": "Operation completed"}
                logger.info(f"✅ Finam API Response: {method} {path} - {response.status_code} (empty body)")
                return result

            result = response.json()

            # Логируем успешный ответ
            logger.info(f"✅ Finam API Response: {method} {path} - {response.status_code}")
            logger.debug(f"Response body: {json.dumps(result, ensure_ascii=False, indent=2)[:1000]}...")

            return result

        except requests.exceptions.HTTPError as e:
            # Пытаемся извлечь детали ошибки из ответа
            error_detail = {"error": str(e), "status_code": e.response.status_code if e.response else None}

            try:
                if e.response and e.response.content:
                    error_detail["details"] = e.response.json()
            except Exception:
                error_detail["details"] = e.response.text if e.response else None

            # Логируем ошибку HTTP
            logger.error(
                f"❌ Finam API Error: {method} {path} - {error_detail['status_code']}\n"
                f"Error: {error_detail.get('details', str(e))}"
            )

            return error_detail

        except Exception as e:
            # Логируем общую ошибку
            logger.error(f"💥 Finam API Exception: {method} {path} - {type(e).__name__}: {str(e)}")
            return {"error": str(e), "type": type(e).__name__}

    def _mask_sensitive_data(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Маскировать чувствительные данные в логах (токены, секреты)

        Args:
            data: Словарь с данными

        Returns:
            Словарь с замаскированными чувствительными данными
        """
        if not data:
            return data

        masked = data.copy()
        sensitive_keys = ["secret", "token", "password", "api_key", "apikey"]

        for key in masked:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if isinstance(masked[key], str) and len(masked[key]) > 8:
                    masked[key] = masked[key][:4] + "****" + masked[key][-4:]
                else:
                    masked[key] = "****"

        return masked

    def get_auth_info(self) -> dict[str, Any]:
        """
        Получить информацию о текущей авторизации

        Returns:
            Словарь с информацией об авторизации
        """
        info: dict[str, Any] = {
            "mode": "auth_manager" if self._auth_manager else "static_token",
            "has_token": bool(self._get_current_token()),
        }

        if self._auth_manager:
            lifetime = self._auth_manager.get_token_lifetime()
            info["token_lifetime"] = str(lifetime) if lifetime else None
            info["account_ids"] = self._auth_manager.get_account_ids()
            info["readonly"] = self._auth_manager.is_readonly()

        return info

    # Методы авторизации (AuthService)

    def auth(self, secret: str) -> dict[str, Any]:
        """
        Получить JWT-токен по API-ключу (Auth)

        Args:
            secret: Секретный API-ключ

        Returns:
            Объект JSON со свойством 'token' (строка)
        """
        return self.execute_request("POST", "/v1/sessions", json={"secret": secret})

    # Методы для работы со счетами (AccountsService)

    def get_account(self, account_id: str) -> dict[str, Any]:
        """
        Получить подробную информацию о счёте (GetAccount)

        Возвращает: тип счёта, статус, общий капитал (equity), нереализованную прибыль,
        денежные балансы по валютам (cash), открытые позиции (positions),
        портфель по секциям: МосБиржа, АмерБиржа, FORTS (portfolio)
        """
        return self.execute_request("GET", f"/v1/accounts/{account_id}")

    def get_transactions(
        self, account_id: str, start: str | None = None, end: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """
        Получить операции по счёту (Transactions)

        Возвращает операции: ввод/вывод средств, комиссии, начисления дивидендов.
        Каждая операция содержит: id, category (funding/fee), timestamp, symbol,
        сумму изменения (change), флаг trade, transaction_category, transaction_name

        Args:
            account_id: Идентификатор счёта
            start: Начало периода в ISO 8601 (опционально)
            end: Конец периода в ISO 8601 (опционально)
            limit: Максимальное число записей (опционально)
        """
        params = {}
        if start:
            params["interval.start"] = start
        if end:
            params["interval.end"] = end
        if limit:
            params["limit"] = limit
        return self.execute_request("GET", f"/v1/accounts/{account_id}/transactions", params=params)

    def get_trades(
        self, account_id: str, start: str | None = None, end: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """
        Получить историю сделок (Trades)

        Возвращает список исполненных ордеров за период.
        Каждая сделка содержит: trade_id, symbol, price, size, side (buy/sell),
        timestamp, order_id, account_id

        Args:
            account_id: Идентификатор счёта
            start: Начало периода в ISO 8601 (опционально)
            end: Конец периода в ISO 8601 (опционально)
            limit: Максимальное число записей (опционально)
        """
        params = {}
        if start:
            params["interval.start"] = start
        if end:
            params["interval.end"] = end
        if limit:
            params["limit"] = limit
        return self.execute_request("GET", f"/v1/accounts/{account_id}/trades", params=params)

    def get_positions(self, account_id: str) -> dict[str, Any]:
        """
        Получить открытые позиции по счёту

        Примечание: позиции включены в ответ get_account в поле 'positions'.
        Каждая позиция содержит: symbol, quantity, average_price, current_price,
        market_value, unrealized_profit
        """
        return self.execute_request("GET", f"/v1/accounts/{account_id}")

    # Методы для работы с ордерами (OrdersService)

    def get_orders(self, account_id: str) -> dict[str, Any]:
        """
        Получить список ордеров (GetOrders)

        Возвращает активные и исторические ордеры для счёта.
        Каждый ордер содержит: order_id, status (New/Accepted/Rejected/PartiallyFilled/Filled/Withdrawn),
        исходные параметры ордера, временные метки (transact_at, accept_at, withdraw_at)
        """
        return self.execute_request("GET", f"/v1/accounts/{account_id}/orders")

    def get_order(self, account_id: str, order_id: str) -> dict[str, Any]:
        """
        Получить информацию о конкретном ордере (GetOrder)

        Возвращает OrderState с подробными параметрами ордера и временными метками
        принятия и исполнения
        """
        return self.execute_request("GET", f"/v1/accounts/{account_id}/orders/{order_id}")

    def create_order(self, account_id: str, order_data: dict[str, Any]) -> dict[str, Any]:
        """
        Создать новый биржевой ордер (PlaceOrder)

        Объект order_data должен включать:
        - symbol: инструмент
        - quantity: количество лотов
        - side: buy или sell
        - type: market, limit, stop, stop_limit, take_profit
        - time_in_force: day, gtc, ioc, fok
        - limit_price: цена (для лимитных ордеров)
        - stop_price: стоп-цена (для стоп-ордеров)
        - stop_condition: bid, ask, last
        - client_order_id: пользовательский ID (опционально)
        - valid_before: время истечения ISO 8601 (опционально)
        - comment: комментарий (опционально)

        Returns:
            OrderState с order_id, exec_id, status и временными метками
        """
        return self.execute_request("POST", f"/v1/accounts/{account_id}/orders", json=order_data)

    def cancel_order(self, account_id: str, order_id: str) -> dict[str, Any]:
        """
        Отменить существующий ордер (CancelOrder)

        Returns:
            OrderState в момент отмены с причиной и временной меткой withdraw_at
        """
        return self.execute_request("DELETE", f"/v1/accounts/{account_id}/orders/{order_id}")

    # Методы для работы с инструментами (AssetsService)

    def get_asset(self, symbol: str, account_id: str) -> dict[str, Any]:
        """
        Получить подробную информацию об инструменте (GetAsset)

        Возвращает данные о конкретном инструменте: symbol, board, id, ticker, mic,
        isin, type (акция/облигация/фьючерс/опцион), name, decimals, min_step,
        lot_size, expiration_date (для производных), quote_currency

        Args:
            symbol: Уникальный идентификатор инструмента (например, SBER@MISX)
            account_id: ID счёта (обязательно)
        """
        return self.execute_request("GET", f"/v1/assets/{symbol}", params={"account_id": account_id})

    def get_asset_params(self, symbol: str, account_id: str) -> dict[str, Any]:
        """
        Получить параметры торговли инструмента (GetAssetParams)

        Возвращает параметры торговли на конкретном счёте:
        - tradeable: можно ли торговать (true/false)
        - longable/shortable: объекты с value (разрешён ли длинный/короткий) и halted_days
        - риск-параметры: initial_margin, maintain_margin, risk_rate

        Args:
            symbol: Идентификатор инструмента
            account_id: Счёт для оценки параметров
        """
        return self.execute_request("GET", f"/v1/assets/{symbol}/params", params={"account_id": account_id})

    def get_options_chain(self, underlying_symbol: str) -> dict[str, Any]:
        """
        Получить опционный ряд (OptionsChain)

        Возвращает список опционов на выбранный базовый актив.
        Каждый опцион содержит: symbol, type (call/put), contract_size, strike,
        multiplier, период торгов (trade_first_day, trade_last_day),
        период экспирации (expiration_first_day, expiration_last_day)

        Args:
            underlying_symbol: Базовый актив (например, SBER)
        """
        return self.execute_request("GET", f"/v1/assets/{underlying_symbol}/options")

    # Методы для получения рыночных данных (MarketDataService)

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """
        Получить последнюю котировку инструмента (LastQuote)

        Возвращает: symbol и объект quote с полями:
        timestamp, ask, ask_size, bid, bid_size, last, last_size, volume,
        turnover, open, high, low, close, change.
        Для опционов дополнительно: объект option с греками (delta, gamma и др.)

        Args:
            symbol: Идентификатор инструмента (например, SBER@MISX)
        """
        return self.execute_request("GET", f"/v1/instruments/{symbol}/quotes/latest")

    def get_orderbook(self, symbol: str, depth: int = 10) -> dict[str, Any]:
        """
        Получить биржевой стакан (OrderBook)

        Возвращает текущий стакан (best bid/ask).
        Ответ содержит orderbook с массивом rows (уровни).
        Каждый уровень: price, sell_size, buy_size, action, mpid (код участника), timestamp

        Args:
            symbol: Идентификатор инструмента
            depth: Глубина стакана (количество уровней)
        """
        return self.execute_request("GET", f"/v1/instruments/{symbol}/orderbook", params={"depth": depth})

    def get_candles(
        self, symbol: str, timeframe: str = "day", start: str | None = None, end: str | None = None
    ) -> dict[str, Any]:
        """
        Получить исторические свечи (Bars)

        Возвращает OHLCV свечи для указанного инструмента.
        Ответ содержит: symbol и массив bars.
        Каждый бар: timestamp, open, high, low, close, volume

        Args:
            symbol: Идентификатор инструмента
            timeframe: Временной интервал (1min, 5min, 15min, hour, day и др.)
            start: Начало периода в ISO 8601 (опционально)
            end: Конец периода в ISO 8601 (опционально)
        """
        params = {"timeframe": timeframe}
        if start:
            params["interval.start"] = start
        if end:
            params["interval.end"] = end
        return self.execute_request("GET", f"/v1/instruments/{symbol}/bars", params=params)

    def get_latest_trades(self, symbol: str) -> dict[str, Any]:
        """
        Получить последние сделки по инструменту (LatestTrades)

        Возвращает: symbol и массив trades.
        Каждая сделка: trade_id, mpid, timestamp, price, size, side (buy/sell)

        Args:
            symbol: Идентификатор инструмента
        """
        return self.execute_request("GET", f"/v1/instruments/{symbol}/trades/latest")

    def get_session_details(self, token: str | None = None) -> dict[str, Any]:
        """
        Получить информацию о текущей торговой сессии (TokenDetails)

        Возвращает: created_at, expires_at, md_permissions, account_ids, readonly

        Args:
            token: JWT токен для проверки (если не указан - использует текущий)
        """
        token_to_check = token or self._get_current_token()
        if not token_to_check:
            return {"error": "No token available"}
        return self.execute_request("POST", "/v1/sessions/details", json={"token": token_to_check})
