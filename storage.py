#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер хранения данных
"""

import json
import logging
from pathlib import Path
from typing import List
from contextlib import contextmanager

from PyQt5.QtCore import QMutex

from models import Host, AppConfig
from interfaces import IStorageRepository
from database import DatabaseManager  # NEW


class StorageManager(IStorageRepository):
    """Потокобезопасное хранилище данных (JSON реализация)"""

    def __init__(self):
        self._mutex = QMutex()
        self._hosts_file = Path("hosts.json")
        self._config_file = Path("config.json")

    @contextmanager
    def _lock(self):
        """Контекстный менеджер для блокировки"""
        self._mutex.lock()
        try:
            yield
        finally:
            self._mutex.unlock()

    def load_hosts(self) -> List[Host]:
        """Загрузка списка узлов"""
        with self._lock():
            if not self._hosts_file.exists():
                return []
            
            try:
                with open(self._hosts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    hosts = []
                    for host_data in data:
                        try:
                            host = Host(**host_data)
                            hosts.append(host)
                        except (TypeError, ValueError) as e:
                            logging.warning(f"Пропуск некорректного узла: {host_data.get('ip', 'unknown')}: {e}")
                            continue
                    
                    # Валидация загруженных данных
                    valid_hosts = []
                    for host in hosts:
                        if host.validate():
                            valid_hosts.append(host)
                        else:
                            logging.warning(f"Узел {host.ip} не прошел валидацию, будет пропущен")
                    
                    if len(valid_hosts) < len(hosts):
                        logging.info(f"Загружено {len(valid_hosts)} из {len(hosts)} узлов, {len(hosts) - len(valid_hosts)} пропущено")
                    
                    return valid_hosts

            except (json.JSONDecodeError, IOError, PermissionError) as e:
                logging.error(f"Ошибка загрузки узлов: {e}", exc_info=True)
                return []

    def save_hosts(self, hosts: List[Host]) -> bool:
        """Сохранение списка узлов"""
        with self._lock():
            try:
                with open(self._hosts_file, 'w', encoding='utf-8') as f:
                    json.dump([h.to_dict() for h in hosts], f, indent=2, ensure_ascii=False)
                return True
            except (IOError, TypeError, PermissionError) as e:
                logging.error(f"Ошибка сохранения узлов: {e}", exc_info=True)
                return False

    def load_config(self) -> AppConfig:
        """Загрузка конфигурации"""
        with self._lock():
            if not self._config_file.exists():
                return AppConfig()

            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    try:
                        return AppConfig(**data)
                    except (TypeError, ValueError) as e:
                        logging.warning(f"Ошибка в конфигурации, используются значения по умолчанию: {e}")
                        return AppConfig()
            except (json.JSONDecodeError, IOError, PermissionError) as e:
                logging.error(f"Ошибка загрузки конфигурации: {e}", exc_info=True)
                return AppConfig()

    def save_config(self, config: AppConfig) -> bool:
        """Сохранение конфигурации"""
        with self._lock():
            try:
                with open(self._config_file, 'w', encoding='utf-8') as f:
                    json.dump(config.to_dict(), f, indent=2)
                return True
            except (IOError, TypeError, PermissionError) as e:
                logging.error(f"Ошибка сохранения конфигурации: {e}", exc_info=True)
                return False

    def migrate_to_db(self, db_manager: DatabaseManager) -> bool:
        """Миграция данных из JSON в SQLite"""
        hosts = self.load_hosts()
        if not hosts:
            logging.info("Нет данных для миграции из JSON")
            return False
            
        logging.info(f"Начало миграции {len(hosts)} хостов в БД...")
        query = db_manager.get_db().exec_
        
        from PyQt5.QtSql import QSqlQuery
        sql = QSqlQuery()
        sql.prepare("""
            INSERT OR IGNORE INTO hosts (id, ip, name, grp, status, notifications_enabled, offline_since, last_seen)
            VALUES (:id, :ip, :name, :grp, :status, :notif, :offline, :seen)
        """)
        
        count = 0
        db_manager.get_db().transaction()
        try:
            for host in hosts:
                sql.bindValue(":id", host.id)
                sql.bindValue(":ip", host.ip)
                sql.bindValue(":name", host.name)
                sql.bindValue(":grp", host.group)
                sql.bindValue(":status", host.status)
                sql.bindValue(":notif", 1 if host.notifications_enabled else 0)
                sql.bindValue(":offline", host.offline_since)
                sql.bindValue(":seen", host.last_seen)
                
                if sql.exec_():
                    count += 1
                else:
                    logging.warning(f"Ошибка миграции хоста {host.ip}: {sql.lastError().text()}")
            
            db_manager.get_db().commit()
            logging.info(f"Миграция завершена. Перенесено {count} записей.")
            
            # Переименовываем старый файл, чтобы не мигрировать снова
            try:
                self._hosts_file.rename(self._hosts_file.with_suffix('.json.bak'))
            except Exception as e:
                logging.warning(f"Не удалось переименовать hosts.json: {e}")
                
            return True
        except Exception as e:
            db_manager.get_db().rollback()
            logging.error(f"Критическая ошибка миграции: {e}")
            return False
