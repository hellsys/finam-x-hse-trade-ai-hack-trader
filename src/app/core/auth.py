"""
Модуль управления авторизацией для Finam TradeAPI

Обеспечивает получение JWT токенов, их автоматическое обновление
и управление сессиями.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

# Настройка логгера
logger = logging.getLogger(__name__)


class FinamAuthManager:
    """
    Менеджер авторизации для Finam TradeAPI
    
    Управляет JWT токенами, автоматически обновляет их при истечении.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        auto_refresh: bool = True,
    ) -> None:
        """
        Инициализация менеджера авторизации
        
        Args:
            api_key: API ключ для получения JWT токена (из env FINAM_API_KEY)
            base_url: Базовый URL API (по умолчанию из env)
            auto_refresh: Автоматически обновлять токен при истечении
        """
        self.api_key = api_key or os.getenv("FINAM_API_KEY", "")
        self.base_url = base_url or os.getenv("FINAM_API_BASE_URL", "https://api.finam.ru")
        self.auto_refresh = auto_refresh
        
        # Состояние токена
        self._jwt_token: str | None = None
        self._expires_at: datetime | None = None
        self._created_at: datetime | None = None
        self._session_details: dict[str, Any] | None = None
        
        # Запас времени до истечения (обновляем токен за 5 минут до истечения)
        self._refresh_buffer = timedelta(minutes=5)

    def get_jwt_token(self) -> str | None:
        """
        Получить текущий JWT токен
        
        Автоматически обновляет токен если он истек или близок к истечению.
        
        Returns:
            JWT токен или None если не удалось получить
        """
        # Если нет API ключа, возвращаем None
        if not self.api_key:
            logger.warning("⚠️ API ключ не настроен, авторизация недоступна")
            return None
        
        # Проверяем нужно ли обновить токен
        if self._should_refresh_token():
            logger.info("🔄 Обновление JWT токена...")
            self._refresh_token()
        
        return self._jwt_token

    def _should_refresh_token(self) -> bool:
        """
        Проверить нужно ли обновить токен
        
        Returns:
            True если токен нужно обновить
        """
        # Если токена нет - нужно получить
        if self._jwt_token is None:
            return True
        
        # Если не знаем время истечения - обновляем на всякий случай
        if self._expires_at is None:
            return True
        
        # Если автообновление выключено - не обновляем
        if not self.auto_refresh:
            return False
        
        # Проверяем истек ли токен или близок к истечению
        now = datetime.now(timezone.utc)
        return now >= (self._expires_at - self._refresh_buffer)

    def _refresh_token(self) -> None:
        """
        Обновить JWT токен
        
        Получает новый токен по API ключу и обновляет информацию о сессии.
        """
        try:
            # Маскируем API ключ для логов
            masked_key = self.api_key[:4] + "****" + self.api_key[-4:] if len(self.api_key) > 8 else "****"
            logger.debug(f"📤 Запрос JWT токена с API ключом: {masked_key}")
            
            # Получаем JWT токен
            response = requests.post(
                f"{self.base_url}/v1/sessions",
                json={"secret": self.api_key},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            
            data = response.json()
            self._jwt_token = data.get("token")
            
            if self._jwt_token:
                masked_token = self._jwt_token[:10] + "..." + self._jwt_token[-10:]
                logger.info(f"✅ JWT токен получен: {masked_token}")
                
                # Получаем детали сессии
                self._fetch_session_details()
            else:
                logger.error("❌ JWT токен не найден в ответе API")
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения JWT токена: {e}")
            self._jwt_token = None

    def _fetch_session_details(self) -> None:
        """
        Получить детали текущей сессии
        
        Обновляет информацию о времени создания и истечения токена.
        """
        try:
            logger.debug("📤 Запрос деталей сессии...")
            
            response = requests.post(
                f"{self.base_url}/v1/sessions/details",
                json={"token": self._jwt_token},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            
            self._session_details = response.json()
            
            # Парсим даты
            created_at_str = self._session_details.get("created_at")
            expires_at_str = self._session_details.get("expires_at")
            
            if created_at_str:
                self._created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            
            if expires_at_str:
                self._expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                lifetime = self.get_token_lifetime()
                logger.info(f"✅ Детали сессии получены. Токен действует: {lifetime}")
            
            # Логируем информацию о счетах
            account_ids = self._session_details.get("account_ids", [])
            if account_ids:
                logger.info(f"📊 Доступные счета: {', '.join(account_ids)}")
            
            # Предупреждаем если режим read-only
            if self._session_details.get("readonly"):
                logger.warning("⚠️ Сессия в режиме только для чтения")
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения деталей сессии: {e}")

    def get_session_details(self) -> dict[str, Any] | None:
        """
        Получить детали текущей сессии
        
        Returns:
            Словарь с информацией о сессии или None
        """
        # Убеждаемся что токен актуален
        self.get_jwt_token()
        return self._session_details

    def get_account_ids(self) -> list[str]:
        """
        Получить список ID счетов доступных в текущей сессии
        
        Returns:
            Список ID счетов
        """
        details = self.get_session_details()
        if details:
            return details.get("account_ids", [])
        return []

    def is_readonly(self) -> bool:
        """
        Проверить является ли сессия только для чтения
        
        Returns:
            True если сессия read-only
        """
        details = self.get_session_details()
        if details:
            return details.get("readonly", False)
        return True

    def get_token_lifetime(self) -> timedelta | None:
        """
        Получить время жизни токена
        
        Returns:
            Время до истечения токена или None
        """
        if self._expires_at:
            now = datetime.now(timezone.utc)
            return self._expires_at - now
        return None

    def invalidate(self) -> None:
        """
        Инвалидировать текущий токен
        
        Сбрасывает все данные авторизации. Следующий запрос get_jwt_token()
        получит новый токен.
        """
        self._jwt_token = None
        self._expires_at = None
        self._created_at = None
        self._session_details = None

    def __repr__(self) -> str:
        """Строковое представление"""
        status = "authorized" if self._jwt_token else "not authorized"
        lifetime = self.get_token_lifetime()
        lifetime_str = f", expires in {lifetime}" if lifetime else ""
        return f"<FinamAuthManager: {status}{lifetime_str}>"


# Глобальный экземпляр менеджера авторизации (singleton)
_auth_manager: FinamAuthManager | None = None


def get_auth_manager() -> FinamAuthManager:
    """
    Получить глобальный экземпляр менеджера авторизации
    
    Returns:
        Экземпляр FinamAuthManager
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = FinamAuthManager()
    return _auth_manager

