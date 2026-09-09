#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модели данных для Network Monitor
"""

import re
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum
from constants import SVG_ONLINE, SVG_OFFLINE, SVG_WAITING, SVG_MAINTENANCE


def validate_ip_or_hostname(address: str) -> bool:
    """Валидация IP-адреса или доменного имени"""
    if not address or not isinstance(address, str):
        return False
    
    address = address.strip()
    if len(address) > 253:  # Максимальная длина hostname
        return False

    # Проверка IP адреса
    if validate_ip(address):
        return True
    
    # Проверка доменного имени (RFC 1035)
    # Базовая проверка формата hostname
    hostname_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$', re.IGNORECASE)
    
    # Разделение на части по точкам
    parts = address.split('.')
    
    if len(parts) < 2 or len(parts) > 127:
        return False
    
    # Проверка каждой части
    for part in parts:
        if not part or len(part) > 63:
            return False
        if not hostname_pattern.match(part):
            return False
        # Не может начинаться или заканчиваться дефисом
        if part.startswith('-') or part.endswith('-'):
            return False
    
    return True


def validate_ip(ip: str) -> bool:
    """Валидация IP-адреса"""
    if not ip or not isinstance(ip, str):
        return False
    
    ip = ip.strip()
    if len(ip) > 15:  # Максимальная длина IP адреса
        return False

    pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
    match = pattern.match(ip)
    if not match:
        return False

    try:
        for group in match.groups():
            num = int(group)
            if not 0 <= num <= 255:
                return False
            # Проверка на ведущие нули (кроме самого нуля)
            if len(group) > 1 and group.startswith('0'):
                return False
        return True
    except ValueError:
        return False


def format_offline_time(duration: timedelta) -> str:
    """Форматирование времени простоя"""
    total_seconds = int(duration.total_seconds())
    if total_seconds <= 0:
        return ""

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}"
    elif minutes > 0:
        return f"{minutes} м"
    else:
        return "< 1 м"



class HostStatus(Enum):
    """Статусы узлов"""
    ONLINE = ("Online", "#10b981", "🟢", SVG_ONLINE)
    WAITING = ("Ожидание", "#f59e0b", "🟠", SVG_WAITING)
    OFFLINE = ("Offline", "#ef4444", "🔴", SVG_OFFLINE)
    MAINTENANCE = ("Тех.обсл.", "#8b5cf6", "🟣", SVG_MAINTENANCE)

    def __init__(self, title, color, emoji, svg):
        self.title = title
        self.color = color
        self.emoji = emoji
        self.svg = svg
        self.icon = emoji # Для обратной совместимости


@dataclass
class Host:
    """Модель сетевого узла"""
    name: str
    ip: str
    address: str = ""
    group: str = "Без группы"
    status: str = "ONLINE"
    last_seen: Optional[str] = None
    offline_since: Optional[str] = None
    notified: bool = False
    notifications_enabled: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        """Валидация данных после инициализации"""
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Имя узла обязательно и должно быть строкой")
        if not validate_ip_or_hostname(self.ip):
            raise ValueError(f"Неверный IP адрес или доменное имя: {self.ip}")
        if self.group and not isinstance(self.group, str):
            raise ValueError("Группа должна быть строкой")
        # Ограничение длины полей
        if len(self.name) > 100:
            raise ValueError("Слишком длинное имя узла (максимум 100 символов)")
        if len(self.address) > 200:
            raise ValueError("Слишком длинный адрес (максимум 200 символов)")
        if len(self.group) > 50:
            raise ValueError("Слишком длинное название группы (максимум 50 символов)")

    def validate(self) -> bool:
        """Валидация данных узла"""
        try:
            self.__post_init__()
            return True
        except ValueError:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AppConfig:
    """Конфигурация приложения"""
    poll_interval: int = 10  # секунды
    waiting_timeout: int = 60  # секунды
    offline_timeout: int = 300  # секунды
    notifications_enabled: bool = True
    sound_enabled: bool = False
    max_workers: int = 20  # Количество потоков для ping
    column_widths: Dict[str, int] = field(default_factory=dict)
    column_order: List[int] = field(default_factory=list)
    hidden_columns: List[int] = field(default_factory=list)
    theme: str = "dark"
    custom_groups: List[str] = field(default_factory=list)
    history_retention_days: int = 90  # 0 = хранить бессрочно
    splitter_sizes: List[int] = field(default_factory=list)
    helpdesk_enabled: bool = False
    helpdesk_url: str = ""

    def __post_init__(self):
        """Валидация конфигурации"""
        if not 1 <= self.poll_interval <= 3600:
            raise ValueError("Интервал опроса должен быть от 1 до 3600 секунд")
        if not 5 <= self.waiting_timeout <= 3600:
            raise ValueError("Таймаут ожидания должен быть от 5 до 3600 секунд")
        if not 10 <= self.offline_timeout <= 7200:
            raise ValueError("Таймаут offline должен быть от 10 до 7200 секунд")
        if not 1 <= self.max_workers <= 100:
            raise ValueError("Количество потоков должно быть от 1 до 100")
        if not 0 <= self.history_retention_days <= 3650:
            raise ValueError("Срок хранения истории должен быть от 0 (бессрочно) до 3650 дней")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)