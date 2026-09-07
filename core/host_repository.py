#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HostRepository - Единая точка доступа к данным (Domain Facade)
Обертка над DataManager для обеспечения совместимости и чистоты архитектуры.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from PyQt5.QtCore import QObject, pyqtSignal

from models import Host
from data_manager import DataManager

class HostRepository(QObject):
    """
    Репозиторий хостов.
    backend: DataManager (SQLite)
    """
    
    # Proxy signals (перенаправляем или адаптируем сигналы DataManager)
    hosts_updated = pyqtSignal(list)  # list[str] IDs
    
    # Детальные события для подписчиков
    host_added = pyqtSignal(Host)  # Хост добавлен
    host_deleted = pyqtSignal(str, Host)  # (host_id, old_host)
    host_info_updated = pyqtSignal(str, Host, Host)  # (host_id, old_host, new_host)
    
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self._data_manager = data_manager
        
        # Подписка на обновления от DataManager
        self._data_manager.hosts_updated.connect(self._on_data_manager_update)
        
        # Подписка на детальные события
        self._data_manager.host_added.connect(self.host_added.emit)
        self._data_manager.host_deleted.connect(self.host_deleted.emit)
        self._data_manager.host_info_updated.connect(self.host_info_updated.emit)
        
        logging.info("HostRepository initialized (wrapping DataManager)")

    def _on_data_manager_update(self, host_ids: List[str]):
        """Проброс сигнала обновления"""
        self.hosts_updated.emit(host_ids)
    
    # ==================== READ ====================
    
    def get(self, host_id: str) -> Optional[Host]:
        hosts = self._data_manager.get_hosts_by_ids([host_id])
        return hosts[0] if hosts else None
    
    def get_all(self, connection_name: str = None) -> List[Host]:
        return self._data_manager.get_all_hosts(connection_name)
    
    def find_by_group(self, group: str) -> List[Host]:
        # SQL-фильтрация на стороне БД через DataManager
        return self._data_manager.get_hosts_by_group(group)

    def get_stats(self) -> Dict[str, int]:
        return self._data_manager.get_stats()
    
    def count(self) -> int:
        stats = self.get_stats()
        return stats.get("TOTAL", 0)
    
    # ==================== WRITE ====================
    
    def add(self, host: Host) -> bool:
        return self._data_manager.add_host(host)

    def add_hosts(self, hosts: List[Host]) -> Tuple[int, int]:
        """Пакетное добавление (Transaction)"""
        return self._data_manager.add_hosts(hosts)
    
    def update(self, host: Host) -> bool:
        """Полное обновление информации хоста"""
        return self._data_manager.update_host_info(host)
    
    def delete(self, host_id: str) -> bool:
        return self._data_manager.delete_host(host_id)
        
    def update_status(self, host_id: str, new_status: str, 
                     offline_since: Optional[str] = None, 
                     offline_time: Optional[str] = None) -> bool:
        return self._data_manager.update_host_status(host_id, new_status, offline_since)

    # ==================== COMPATIBILITY / HELPERS ====================
    
    def get_hosts_by_ids(self, ids: List[str]) -> List[Host]:
        return self._data_manager.get_hosts_by_ids(ids)

    # ==================== HISTORY ====================

    def get_host_history(self, host_id: str, limit: int = 200) -> List[Dict]:
        """История смены статусов конкретного узла"""
        return self._data_manager.get_host_history(host_id, limit)

    def clear_host_history(self, host_id: str) -> bool:
        """Очистка истории конкретного узла"""
        return self._data_manager.clear_host_history(host_id)

    def get_history_events(self, limit: int = 500, host_name_filter: str = None,
                            group_filter: str = None, status_filter: str = None) -> List[Dict]:
        """Общий журнал событий по всем узлам, с опциональными фильтрами"""
        return self._data_manager.get_history_events(
            limit=limit, host_name_filter=host_name_filter,
            group_filter=group_filter, status_filter=status_filter
        )

    def purge_old_history(self, retention_days: int) -> int:
        """Очистка истории старше заданного числа дней (0 = бессрочно, ничего не чистит)"""
        return self._data_manager.purge_old_history(retention_days)

    def clear_history(self) -> bool:
        """Полная очистка журнала событий"""
        return self._data_manager.clear_history()
