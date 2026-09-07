#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интерфейсы (абстракции) для Dependency Injection
Определяют контракты, которые должны реализовывать конкретные классы
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from models import Host, AppConfig


class IStorageRepository(ABC):
    """Интерфейс для работы с хранилищем данных"""
    
    @abstractmethod
    def load_hosts(self) -> List[Host]:
        """Загрузка всех хостов"""
        pass
    
    @abstractmethod
    def save_hosts(self, hosts: List[Host]) -> bool:
        """Сохранение списка хостов"""
        pass
    
    @abstractmethod
    def load_config(self) -> AppConfig:
        """Загрузка конфигурации"""
        pass
    
    @abstractmethod
    def save_config(self, config: AppConfig) -> bool:
        """Сохранение конфигурации"""
        pass


class IPingService(ABC):
    """Интерфейс для пинга хостов"""
    
    @abstractmethod
    def ping_host(self, ip: str, timeout: float = 2.0) -> Optional[bool]:
        """
        Пинг хоста
        
        Args:
            ip: IP адрес или hostname
            timeout: Таймаут в секундах
            
        Returns:
            True - хост доступен
            False/None - хост недоступен
        """
        pass


class INotificationService(ABC):
    """Интерфейс для отправки уведомлений"""
    
    @abstractmethod
    def notify_offline_hosts(self, offline_hosts: List[str], config: AppConfig) -> None:
        """
        Отправка уведомления о недоступных хостах
        
        Args:
            offline_hosts: Список названий недоступных хостов
            config: Конфигурация приложения
        """
        pass
    
    @abstractmethod
    def show_notification(self, title: str, message: str) -> None:
        """
        Показ системного уведомления
        
        Args:
            title: Заголовок
            message: Текст сообщения
        """
        pass
