#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MonitorSubscriber - Подписчик для синхронизации с MonitorThread

Оптимизации (v2.0):
- Использует детальные события Repository (host_added, host_deleted, host_info_updated)
- Прерывает цикл MonitorThread при критических изменениях (смена IP)
- НЕ обновляет MonitorThread при изменении статусов (MonitorThread сам их обновляет)
"""

import logging
from typing import List
from PyQt5.QtCore import QObject

from core.host_repository import HostRepository
from models import Host


class MonitorSubscriber(QObject):
    """
    Подписчик для синхронизации HostRepository с MonitorThread
    
    Стратегии (v2.0):
    - host_added: Прервать цикл и обновить список хостов
    - host_deleted: Прервать цикл и обновить список хостов
    - host_info_updated: Проверить критичные изменения (IP), если есть - прервать цикл
    - НЕ подписываемся на status_changed (MonitorThread сам обновляет статусы)
    """
    
    def __init__(self, repository: HostRepository, monitor_thread):
        super().__init__()
        self._repository = repository
        self._monitor_thread = monitor_thread
        
        # Подписка на детальные события Repository
        repository.host_added.connect(self._on_host_added)
        repository.host_deleted.connect(self._on_host_deleted)
        repository.host_info_updated.connect(self._on_host_info_updated)
        
        logging.debug("MonitorSubscriber initialized (using detailed events)")
    
    def _on_host_added(self, host: Host):
        """
        Хост добавлен
        
        Стратегия: Прервать текущий цикл и немедленно обновить список хостов
        """
        logging.info(f"MonitorSubscriber: Host added {host.name} ({host.ip})")
        
        # Прерываем текущий цикл для немедленного включения нового хоста в мониторинг
        self._monitor_thread.interrupt_cycle()
    
    def _on_host_deleted(self, host_id: str, old_host: Host):
        """
        Хост удалён
        
        Стратегия: Прервать текущий цикл и обновить список хостов
        """
        logging.info(f"MonitorSubscriber: Host deleted {old_host.name} ({old_host.ip})")
        
        # Чистим кеш статусов
        self._monitor_thread.remove_from_cache(host_id)
        
        # Прерываем текущий цикл для немедленного исключения хоста из мониторинга
        self._monitor_thread.interrupt_cycle()
    
    def _on_host_info_updated(self, host_id: str, old_host: Host, new_host: Host):
        """
        Хост обновлён
        
        Стратегия: Проверить критичные изменения (IP, notifications_enabled).
        Если они есть - прервать цикл для немедленного применения изменений.
        """
        # Проверяем критичные изменения
        ip_changed = old_host.ip != new_host.ip
        notifications_changed = old_host.notifications_enabled != new_host.notifications_enabled
        
        if ip_changed:
            logging.warning(
                f"MonitorSubscriber: IP changed for {new_host.name}: "
                f"{old_host.ip} -> {new_host.ip}. Interrupting monitor cycle."
            )
            self._monitor_thread.interrupt_cycle()
        elif notifications_changed:
            logging.info(
                f"MonitorSubscriber: Notifications changed for {new_host.name}: "
                f"{old_host.notifications_enabled} -> {new_host.notifications_enabled}"
            )
            # Для изменения notifications можно не прерывать цикл,
            # но для консистентности делаем это
            self._monitor_thread.interrupt_cycle()
        else:
            # Изменились только название, группа или другие некритичные поля
            # Не прерываем цикл - изменения применятся при следующей загрузке
            logging.debug(f"MonitorSubscriber: Non-critical update for host {host_id}")
