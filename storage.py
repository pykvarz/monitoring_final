#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер хранения данных
"""

import json
import dataclasses
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Union
from contextlib import contextmanager

from PyQt5.QtCore import QMutex

from models import Host, AppConfig
from interfaces import IStorageRepository
from database import DatabaseManager  # NEW


class StorageManager(IStorageRepository):
    """Потокобезопасное хранилище данных (JSON реализация)"""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        self._mutex = QMutex()
        if base_dir is not None:
            self._base_dir = Path(base_dir)
        elif getattr(sys, 'frozen', False):
            self._base_dir = Path(sys.executable).resolve().parent
        else:
            self._base_dir = Path(".")

        self._hosts_file = self._base_dir / "hosts.json"
        self._config_file = self._base_dir / "config.json"

    @property
    def base_dir(self) -> Path:
        """Базовая директория хранения данных"""
        return self._base_dir

    @property
    def hosts_file(self) -> Path:
        """Путь к файлу hosts.json"""
        return self._hosts_file

    @property
    def config_file(self) -> Path:
        """Путь к файлу config.json"""
        return self._config_file

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
                    if not isinstance(data, list):
                        logging.warning("Список узлов должен быть JSON-массивом")
                        return []
                    hosts = []
                    for host_data in data:
                        if not isinstance(host_data, dict):
                            logging.warning("Пропуск узла: запись не является JSON-объектом")
                            continue
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
                self._atomic_json_write(
                    self._hosts_file,
                    [h.to_dict() for h in hosts],
                    ensure_ascii=False,
                )
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
                    if not isinstance(data, dict):
                        logging.warning("Конфигурация должна быть JSON-объектом; используются значения по умолчанию")
                        return AppConfig()
                    valid_keys = {f.name for f in dataclasses.fields(AppConfig)}
                    unknown_keys = set(data.keys()) - valid_keys
                    if unknown_keys:
                        logging.warning(f"Неизвестные поля в конфигурации (пропущены): {unknown_keys}")
                    filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                    defaults = AppConfig()
                    for key, value in list(filtered_data.items()):
                        default = getattr(defaults, key)
                        invalid_collection = isinstance(default, (dict, list)) and not isinstance(value, type(default))
                        if key == "column_widths" and isinstance(value, dict):
                            invalid_collection = any(
                                not isinstance(k, str) or type(v) is not int
                                for k, v in value.items()
                            )
                        if isinstance(default, list) and isinstance(value, list):
                            item_type = str if key in ("custom_groups", "helpdesk_reasons", "helpdesk_reasons_recovered") else int
                            invalid_collection = any(type(item) is not item_type for item in value)
                        if invalid_collection:
                            logging.warning(f"Некорректный тип настройки {key}; используется значение по умолчанию")
                            filtered_data[key] = default
                    try:
                        return AppConfig(**filtered_data)
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
                self._atomic_json_write(self._config_file, config.to_dict())
                return True
            except (IOError, TypeError, PermissionError) as e:
                logging.error(f"Ошибка сохранения конфигурации: {e}", exc_info=True)
                return False

    @staticmethod
    def _atomic_json_write(path: Path, data, ensure_ascii: bool = True) -> None:
        """Записать JSON через временный файл без риска усечь старые данные."""
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                json.dump(data, stream, indent=2, ensure_ascii=ensure_ascii)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        except Exception:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    def migrate_to_db(self, db_manager: DatabaseManager) -> bool:
        """Миграция данных из JSON в SQLite"""
        hosts = self.load_hosts()
        if not hosts:
            logging.info("Нет данных для миграции из JSON")
            return False
            
        logging.info(f"Начало миграции {len(hosts)} хостов в БД...")
        db = db_manager.get_db()
        
        from PyQt5.QtSql import QSqlQuery
        sql = QSqlQuery(db)
        sql.prepare("""
            INSERT OR IGNORE INTO hosts (id, ip, name, address, grp, status, notifications_enabled, offline_since, last_seen)
            VALUES (:id, :ip, :name, :address, :grp, :status, :notif, :offline, :seen)
        """)
        
        count = 0
        if not db.transaction():
            logging.error(f"Не удалось начать транзакцию миграции: {db.lastError().text()}")
            sql.finish()
            return False
        try:
            for host in hosts:
                sql.bindValue(":id", host.id)
                sql.bindValue(":ip", host.ip)
                sql.bindValue(":name", host.name)
                sql.bindValue(":address", host.address or "")
                sql.bindValue(":grp", host.group)
                sql.bindValue(":status", host.status)
                sql.bindValue(":notif", 1 if host.notifications_enabled else 0)
                sql.bindValue(":offline", host.offline_since)
                sql.bindValue(":seen", host.last_seen)
                
                if not sql.exec_():
                    raise RuntimeError(
                        f"Ошибка миграции хоста {host.ip}: {sql.lastError().text()}"
                    )
                count += max(0, sql.numRowsAffected())
            
            if not db.commit():
                raise RuntimeError(f"Не удалось зафиксировать миграцию: {db.lastError().text()}")
            logging.info(f"Миграция завершена. Перенесено {count} записей.")
            
            # Переименовываем старый файл, чтобы не мигрировать снова
            try:
                os.replace(self._hosts_file, self._hosts_file.with_suffix('.json.bak'))
            except Exception as e:
                logging.warning(f"Не удалось переименовать hosts.json: {e}")
                
            return True
        except Exception as e:
            db.rollback()
            logging.error(f"Критическая ошибка миграции: {e}")
            return False
        finally:
            sql.finish()
