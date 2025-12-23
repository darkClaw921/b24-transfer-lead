"""Кэширование данных с TTL."""
import time
from typing import Any

logger = None


def get_logger():
    """Ленивая инициализация logger для избежания циклических импортов."""
    global logger
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)
    return logger


class TTLCache:
    """Простой in-memory кэш с TTL (Time To Live)."""

    def __init__(self, default_ttl: int = 86400):
        """Инициализация кэша.

        Args:
            default_ttl: Время жизни записей в секундах (по умолчанию 1 день = 86400)
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """Получить значение из кэша.

        Args:
            key: Ключ кэша

        Returns:
            Значение или None, если ключ не найден или истек срок действия
        """
        if key not in self._cache:
            return None

        value, expiry_time = self._cache[key]

        # Проверяем, не истек ли срок действия
        if time.time() > expiry_time:
            del self._cache[key]
            get_logger().debug(f"Cache expired for key: {key}")
            return None

        get_logger().debug(f"Cache hit for key: {key}")
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Установить значение в кэш.

        Args:
            key: Ключ кэша
            value: Значение для кэширования
            ttl: Время жизни в секундах (если None, используется default_ttl)
        """
        ttl = ttl or self.default_ttl
        expiry_time = time.time() + ttl
        self._cache[key] = (value, expiry_time)
        get_logger().debug(f"Cached value for key: {key} (TTL: {ttl}s)")

    def clear(self) -> None:
        """Очистить весь кэш."""
        self._cache.clear()
        get_logger().debug("Cache cleared")

    def remove(self, key: str) -> None:
        """Удалить конкретный ключ из кэша.

        Args:
            key: Ключ для удаления
        """
        if key in self._cache:
            del self._cache[key]
            get_logger().debug(f"Removed key from cache: {key}")


# Глобальный экземпляр кэша для статусов лидов (TTL = 1 день)
lead_statuses_cache = TTLCache(default_ttl=86400)

