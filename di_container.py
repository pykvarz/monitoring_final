#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dependency Injection Container
Управляет зависимостями и их жизненным циклом
"""

from typing import Dict, Type, Any, Callable
import logging


class DIContainer:
    """
    Контейнер для Dependency Injection
    
    Поддерживает:
    - Singleton: один экземпляр на всё приложение
    - Transient: новый экземпляр при каждом запросе
    - Factory: создание через фабричную функцию
    """
    
    def __init__(self):
        self._singletons: Dict[Type, Any] = {}
        self._transients: Dict[Type, Callable] = {}
        self._factories: Dict[Type, Callable] = {}
        
    def register_singleton(self, interface: Type, implementation: Any) -> None:
        """
        Регистрация singleton сервиса
        
        Args:
            interface: Интерфейс (абстрактный класс)
            implementation: Конкретная реализация (экземпляр)
        """
        self._singletons[interface] = implementation
        logging.debug(f"Registered singleton: {interface.__name__} -> {type(implementation).__name__}")
    
    def register_transient(self, interface: Type, factory: Callable) -> None:
        """
        Регистрация transient сервиса (новый экземпляр при каждом вызове)
        
        Args:
            interface: Интерфейс
            factory: Функция-фабрика для создания экземпляра
        """
        self._transients[interface] = factory
        logging.debug(f"Registered transient: {interface.__name__}")
    
    def register_factory(self, interface: Type, factory: Callable) -> None:
        """
        Регистрация фабрики для ленивого создания
        
        Args:
            interface: Интерфейс
            factory: Функция-фабрика
        """
        self._factories[interface] = factory
        logging.debug(f"Registered factory: {interface.__name__}")
    
    def resolve(self, interface: Type) -> Any:
        """
        Получение экземпляра сервиса
        
        Args:
            interface: Интерфейс для получения
            
        Returns:
            Экземпляр сервиса
            
        Raises:
            KeyError: Если сервис не зарегистрирован
        """
        # Сначала проверяем singletons
        if interface in self._singletons:
            return self._singletons[interface]
        
        # Затем factories (создаем singleton из фабрики)
        if interface in self._factories:
            instance = self._factories[interface]()
            self._singletons[interface] = instance
            logging.debug(f"Created singleton from factory: {interface.__name__}")
            return instance
        
        # Наконец transients (каждый раз новый экземпляр)
        if interface in self._transients:
            instance = self._transients[interface]()
            logging.debug(f"Created transient instance: {interface.__name__}")
            return instance
        
        raise KeyError(f"Service not registered: {interface.__name__}")
    
    def has(self, interface: Type) -> bool:
        """
        Проверка, зарегистрирован ли сервис
        
        Args:
            interface: Интерфейс для проверки
            
        Returns:
            True если зарегистрирован
        """
        return (interface in self._singletons or 
                interface in self._factories or 
                interface in self._transients)
    
    def clear(self) -> None:
        """Очистка всех зарегистрированных сервисов"""
        self._singletons.clear()
        self._transients.clear()
        self._factories.clear()
        logging.debug("DIContainer cleared")


# Глобальный экземпляр контейнера
_global_container: DIContainer = None


def get_container() -> DIContainer:
    """Получение глобального DI контейнера"""
    global _global_container
    if _global_container is None:
        _global_container = DIContainer()
    return _global_container


def setup_container() -> DIContainer:
    """
    Настройка и конфигурация DI контейнера
    Регистрация всех сервисов приложения
    """
    container = get_container()
    
    # Импорты здесь, чтобы избежать циклических зависимостей
    from storage import StorageManager
    from services import PingService, NotificationService
    from interfaces import IStorageRepository, IPingService, INotificationService
    from core.host_repository import HostRepository
    from database import DatabaseManager
    from data_manager import DataManager
    
    # Регистрация Core (Single Source of Truth)
    # Используем Repository как Adapter для DataManager или оставляем как есть,
    # Но для SQLite миграции нам нужен DataManager и DatabaseManager
    
    db_manager = DatabaseManager()
    container.register_singleton(DatabaseManager, db_manager)
    
    data_manager = DataManager(db_manager)
    container.register_singleton(DataManager, data_manager)

    # Repository wraps DataManager
    host_repository = HostRepository(data_manager)
    container.register_singleton(HostRepository, host_repository)
    
    # Регистрация Infrastructure сервисов
    container.register_singleton(IStorageRepository, StorageManager())
    container.register_singleton(IPingService, PingService())
    container.register_singleton(INotificationService, NotificationService())
    
    logging.info("DI Container configured successfully")
    return container
