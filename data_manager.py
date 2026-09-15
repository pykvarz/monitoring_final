#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер данных (DataManager).
Центральный компонент архитектуры.
Отвечает за:
1. Взаимодействие с БД
2. Кеширование данных (опционально)
3. Throttling обновлений UI (для поддержки 1000+ узлов)
"""

import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
from PyQt5.QtSql import QSqlQuery, QSqlDatabase

from database import DatabaseManager
from models import Host

class DataManager(QObject):
    # Сигнал для обновления UI. 
    # Отправляет список ID измененных хостов, чтобы таблица перерисовывала только их.
    # Если список пуст/None -> полное обновление.
    hosts_updated = pyqtSignal(list)
    
    # Детальные события для подписчиков (Repository pattern)
    host_added = pyqtSignal(Host)  # Хост добавлен
    host_deleted = pyqtSignal(str, Host)  # (host_id, old_host)
    host_info_updated = pyqtSignal(str, Host, Host)  # (host_id, old_host, new_host)
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        
        # === Batch Updates Logic ===
        # Накапливаем изменения и отправляем их раз в N мс
        self._changed_host_ids = set()
        self._update_timer = QTimer()
        self._update_timer.setInterval(250)  # Обновление UI 4 раза в секунду макс.
        self._update_timer.timeout.connect(self._flush_updates)
        self._batch_mutex = QMutex()
        
    def get_all_hosts(self, connection_name: str = None) -> List[Host]:
        """Получение всех хостов из БД"""
        hosts = []
        db = QSqlDatabase.database(connection_name) if connection_name else self.db_manager.get_db()
        
        if not db.isOpen():
            return hosts

        query = QSqlQuery("SELECT * FROM hosts ORDER BY status, name", db)
        while query.next():
            host = self._record_to_host(query)
            hosts.append(host)
        query.finish()
        
        return hosts

    def get_hosts_by_group(self, group: str) -> List[Host]:
        """Получение хостов по группе (SQL-фильтрация на стороне БД)"""
        hosts = []
        db = self.db_manager.get_db()
        if not db.isOpen():
            return hosts

        query = QSqlQuery(db)
        query.prepare("SELECT * FROM hosts WHERE grp = :group ORDER BY status, name")
        query.bindValue(":group", group)
        if query.exec_():
            while query.next():
                hosts.append(self._record_to_host(query))
        else:
            logging.error(f"Ошибка фильтрации по группе '{group}': {query.lastError().text()}")
        query.finish()

        return hosts

    def exists_by_ip(self, ip: str, exclude_id: Optional[str] = None) -> bool:
        """Проверка существования хоста с данным IP/хостнеймом в БД"""
        db = self.db_manager.get_db()
        if not db.isOpen():
            return False

        query = QSqlQuery(db)
        if exclude_id:
            query.prepare("SELECT 1 FROM hosts WHERE ip = :ip AND id != :exclude_id LIMIT 1")
            query.bindValue(":exclude_id", exclude_id)
        else:
            query.prepare("SELECT 1 FROM hosts WHERE ip = :ip LIMIT 1")
        query.bindValue(":ip", ip.strip())
        
        exists = False
        if query.exec_():
            if query.next():
                exists = True
            query.finish()
        else:
            logging.error(f"Ошибка проверки существования IP {ip}: {query.lastError().text()}")
        return exists

    def add_host(self, host: Host) -> bool:
        """Добавление нового хоста"""
        db = self.db_manager.get_db()
        if not db.isOpen():
            return False

        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO hosts (id, ip, name, address, grp, status, notifications_enabled)
            VALUES (:id, :ip, :name, :address, :grp, :status, :notifications_enabled)
        """)
        query.bindValue(":id", host.id)
        query.bindValue(":ip", host.ip)
        query.bindValue(":name", host.name)
        query.bindValue(":address", host.address)
        query.bindValue(":grp", host.group)
        query.bindValue(":status", host.status)
        query.bindValue(":notifications_enabled", 1 if host.notifications_enabled else 0)
        
        success = query.exec_()
        if success:
            query.finish()
            # Эмитим детальное событие
            self.host_added.emit(host)
            # Затем общее обновление UI
            self._trigger_update()
            return True
        else:
            err = query.lastError().text()
            query.finish()
            logging.error(f"Ошибка добавления хоста: {err}")
            return False

    def add_hosts(self, hosts: List[Host]) -> Tuple[int, int]:
        """
        Пакетное добавление хостов (Transaction)
        Returns: (added_count, errors_count)
        """
        added = 0
        errors = 0
        db = self.db_manager.get_db()
        
        if not db.transaction():
            logging.error("Failed to start transaction for batch add")
            return 0, len(hosts)

        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO hosts (id, ip, name, address, grp, status, notifications_enabled)
            VALUES (:id, :ip, :name, :address, :grp, :status, :notifications_enabled)
        """)
        
        for host in hosts:
            query.bindValue(":id", host.id)
            query.bindValue(":ip", host.ip)
            query.bindValue(":name", host.name)
            query.bindValue(":address", host.address)
            query.bindValue(":grp", host.group)
            query.bindValue(":status", host.status)
            query.bindValue(":notifications_enabled", 1 if host.notifications_enabled else 0)
            
            if query.exec_():
                added += 1
            else:
                logging.warning(f"Failed to add host {host.name}: {query.lastError().text()}")
                errors += 1
                
        query.finish()
        if not db.commit():
            logging.error("Failed to commit batch add transaction")
            db.rollback()
            return 0, len(hosts)
            
        if added > 0:
            self._trigger_update() # Full update after batch import
            
        return added, errors

    def delete_host(self, host_id: str) -> bool:
        """Удаление хоста"""
        # Сначала получаем хост для события
        old_host = None
        hosts = self.get_hosts_by_ids([host_id])
        if hosts:
            old_host = hosts[0]
        
        db = self.db_manager.get_db()
        if not db.isOpen():
            return False

        query = QSqlQuery(db)
        query.prepare("DELETE FROM hosts WHERE id = :id")
        query.bindValue(":id", host_id)
        
        success = query.exec_()
        query.finish()
        if success:
            # Эмитим детальное событие
            if old_host:
                self.host_deleted.emit(host_id, old_host)
            # Затем общее обновление UI
            self._trigger_update()
            return True
        return False

    def update_host_status(self, host_id: str, status: str, offline_since: Optional[str] = None):
        """
        Обновление статуса хоста.
        Если статус реально меняется — пишем событие в журнал истории (status_history).
        """
        db = self.db_manager.get_db()
        if not db.isOpen():
            return

        # Узнаём текущий (старый) статус и имя хоста — нужно и для проверки
        # "изменился ли статус", и для журнала (имя хранится отдельно на случай
        # удаления/переименования узла в будущем — история должна остаться читаемой)
        old_status = None
        host_name = host_id
        lookup = QSqlQuery(db)
        lookup.prepare("SELECT status, name FROM hosts WHERE id = :id")
        lookup.bindValue(":id", host_id)
        if lookup.exec_() and lookup.next():
            old_status = lookup.value("status")
            host_name = lookup.value("name") or host_id
        lookup.finish()

        # Примечание: offline_since НЕ обнуляется принудительно при status=ONLINE.
        # Статус-машина (MonitorThread._calculate_status) осознанно передаёт
        # offline_since при первом неудачном пинге, даже если status ещё ONLINE
        # (порог waiting_timeout не достигнут). При реальном восстановлении
        # (ping OK) статус-машина сама передаёт offline_since=None.

        query = QSqlQuery(db)
        
        # Обновляем status, last_seen и offline_since.
        # last_seen обновляется только когда узел реально ONLINE (offline_since is None),
        # чтобы не затирать фактическое время последней доступности узла при сбоях.
        if offline_since is None:
            sql = """
                UPDATE hosts 
                SET status = :status, 
                    last_seen = :last_seen,
                    offline_since = :offline_since
                WHERE id = :id
            """
            query.prepare(sql)
            query.bindValue(":status", status)
            query.bindValue(":last_seen", datetime.now(timezone.utc).isoformat())
            query.bindValue(":offline_since", None)
            query.bindValue(":id", host_id)
        else:
            sql = """
                UPDATE hosts 
                SET status = :status, 
                    offline_since = :offline_since
                WHERE id = :id
            """
            query.prepare(sql)
            query.bindValue(":status", status)
            query.bindValue(":offline_since", offline_since)
            query.bindValue(":id", host_id)
        
        if query.exec_():
            query.finish()
            if old_status is not None and old_status != status:
                self._add_history_event(host_id, host_name, old_status, status)

            # Добавляем в batch для обновления UI
            with QMutexLocker(self._batch_mutex):
                self._changed_host_ids.add(host_id)
                if not self._update_timer.isActive():
                    self._update_timer.start()
        else:
            err = query.lastError().text()
            query.finish()
            logging.error(f"Failed to update host {host_id}: {err}")

    def _add_history_event(self, host_id: str, host_name: str, old_status: str, new_status: str) -> None:
        """Запись события смены статуса в журнал истории"""
        db = self.db_manager.get_db()
        if not db.isOpen():
            return

        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO status_history (host_id, host_name, old_status, new_status, timestamp)
            VALUES (:host_id, :host_name, :old_status, :new_status, :timestamp)
        """)
        query.bindValue(":host_id", host_id)
        query.bindValue(":host_name", host_name)
        query.bindValue(":old_status", old_status)
        query.bindValue(":new_status", new_status)
        query.bindValue(":timestamp", datetime.now(timezone.utc).isoformat())
        if not query.exec_():
            logging.warning(f"Не удалось записать событие истории для {host_id}: {query.lastError().text()}")
        query.finish()

    def get_history_events(self, limit: int = 500, host_name_filter: str = None,
                            group_filter: str = None, status_filter: str = None) -> List[Dict]:
        """
        Общий журнал событий по всем узлам (для вкладки 'История').
        group_filter фильтрует по группе через JOIN с текущими данными hosts
        (группа могла с тех пор смениться — фильтруем по актуальной).
        """
        events = []
        db = self.db_manager.get_db()
        if not db.isOpen():
            return events

        sql = """
            SELECT h.host_id, h.host_name, h.old_status, h.new_status, h.timestamp,
                   hosts.grp AS grp, hosts.ip AS ip, hosts.address AS address
            FROM status_history h
            LEFT JOIN hosts ON hosts.id = h.host_id
            WHERE 1=1
        """
        params = {}
        if host_name_filter:
            sql += " AND (h.host_name LIKE :name OR hosts.ip LIKE :name OR hosts.address LIKE :name)"
            params[":name"] = f"%{host_name_filter}%"
        if group_filter:
            sql += " AND hosts.grp = :grp"
            params[":grp"] = group_filter
        if status_filter:
            sql += " AND h.new_status = :status"
            params[":status"] = status_filter

        sql += " ORDER BY h.timestamp DESC LIMIT :limit"

        query = QSqlQuery(db)
        query.prepare(sql)
        for key, value in params.items():
            query.bindValue(key, value)
        query.bindValue(":limit", limit)

        if query.exec_():
            while query.next():
                events.append({
                    "host_id": query.value("host_id"),
                    "host_name": query.value("host_name"),
                    "old_status": query.value("old_status"),
                    "new_status": query.value("new_status"),
                    "timestamp": query.value("timestamp"),
                    "group": query.value("grp") or "",
                    "ip": query.value("ip") or "",
                    "address": query.value("address") or "",
                })
        else:
            logging.error(f"Ошибка чтения журнала истории: {query.lastError().text()}")
        query.finish()
        return events

    def purge_old_history(self, retention_days: int) -> int:
        """
        Удаление событий истории старше retention_days дней.
        retention_days == 0 означает бессрочное хранение — ничего не удаляем.
        Возвращает количество удалённых записей.
        """
        if not retention_days or retention_days <= 0:
            return 0

        db = self.db_manager.get_db()
        if not db.isOpen():
            return 0

        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        query = QSqlQuery(db)
        query.prepare("DELETE FROM status_history WHERE timestamp < :cutoff")
        query.bindValue(":cutoff", cutoff)
        if query.exec_():
            deleted = query.numRowsAffected()
            query.finish()
            if deleted > 0:
                logging.info(f"Очистка истории: удалено {deleted} событий старше {retention_days} дней")
            return deleted
        else:
            err = query.lastError().text()
            query.finish()
            logging.error(f"Ошибка очистки истории: {err}")
            return 0

    def clear_history(self) -> bool:
        """Полная очистка журнала событий"""
        db = self.db_manager.get_db()
        if not db.isOpen():
            return False

        query = QSqlQuery(db)
        if query.exec_("DELETE FROM status_history"):
            query.finish()
            logging.info("Журнал истории событий полностью очищен")
            return True
        else:
            err = query.lastError().text()
            query.finish()
            logging.error(f"Ошибка полной очистки истории: {err}")
            return False

    def update_host_info(self, host: Host) -> bool:
        """Обновление информации о хосте (имя, ip, группа и т.д.)"""
        # Сначала получаем старое состояние для события
        old_host = None
        hosts = self.get_hosts_by_ids([host.id])
        if hosts:
            old_host = hosts[0]
        
        db = self.db_manager.get_db()
        if not db.isOpen():
            return False

        query = QSqlQuery(db)
        query.prepare("""
            UPDATE hosts 
            SET ip = :ip, 
                name = :name,
                address = :address,
                grp = :grp, 
                notifications_enabled = :notifications_enabled
            WHERE id = :id
        """)
        query.bindValue(":ip", host.ip)
        query.bindValue(":name", host.name)
        query.bindValue(":address", host.address)
        query.bindValue(":grp", host.group)
        query.bindValue(":notifications_enabled", 1 if host.notifications_enabled else 0)
        query.bindValue(":id", host.id)
        
        success = query.exec_()
        if success:
            query.finish()
            # Эмитим детальное событие
            if old_host:
                self.host_info_updated.emit(host.id, old_host, host)
            # Затем общее обновление UI
            self._trigger_update()
            return True
        else:
            err = query.lastError().text()
            query.finish()
            logging.error(f"Ошибка обновления информации хоста {host.id}: {err}")
            return False

    def _trigger_update(self, host_ids: List[str] = None):
        """Принудительный вызов обновления (сразу)"""
        if host_ids is None:
            self.hosts_updated.emit([]) # Пустой список = полное обновление
        else:
            self.hosts_updated.emit(host_ids)

    def _flush_updates(self):
        """Отправка накопленных обновлений в UI"""
        with QMutexLocker(self._batch_mutex):
            if not self._changed_host_ids:
                return
            
            # Копируем и чистим
            updates = list(self._changed_host_ids)
            self._changed_host_ids.clear()
            self._update_timer.stop()
            
        # Эмитим сигнал (уже без лока)
        self.hosts_updated.emit(updates)

    def get_hosts_by_ids(self, host_ids: List[str]) -> List[Host]:
        """Получение списка хостов по ID"""
        db = self.db_manager.get_db()
        if not host_ids or not db.isOpen():
            return []
            
        hosts = []
        placeholders = ",".join(["?"] * len(host_ids))
        query = QSqlQuery(db)
        query.prepare(f"SELECT * FROM hosts WHERE id IN ({placeholders})")
        
        for host_id in host_ids:
            query.addBindValue(host_id)
            
        if query.exec_():
            while query.next():
                hosts.append(self._record_to_host(query))
        else:
            logging.error(f"Ошибка получения хостов по IDs: {query.lastError().text()}")
        query.finish()
                
        return hosts

    def _record_to_host(self, query: QSqlQuery) -> Host:
        """Helper: QSqlQuery record -> Host object"""
        st = query.value("status")
        raw_os = query.value("offline_since")
        # Читаем offline_since как есть из БД. Очистка offline_since при
        # переходе в ONLINE — ответственность статус-машины (update_host_status),
        # а не слоя чтения. Принудительный сброс здесь ломал статус-машину:
        # MonitorThread не мог отследить длительность простоя, потому что
        # каждый цикл чтения обнулял таймер для ONLINE-хостов.
        offline_since = raw_os if raw_os else None

        return Host(
            id=query.value("id"),
            ip=query.value("ip"),
            name=query.value("name"),
            address=query.value("address") or "",
            group=query.value("grp"),
            status=st,
            last_seen=query.value("last_seen") or None,
            offline_since=offline_since,
            notifications_enabled=bool(query.value("notifications_enabled"))
        )

    def get_stats(self) -> Dict[str, int]:
        """Получение статистики по статусам"""
        stats = {"ONLINE": 0, "WAITING": 0, "OFFLINE": 0, "MAINTENANCE": 0, "TOTAL": 0}
        
        db = self.db_manager.get_db()
        if not db.isOpen():
            return stats
            
        query = QSqlQuery("SELECT status, COUNT(*) FROM hosts GROUP BY status", db)
        while query.next():
            status = query.value(0)
            count = query.value(1)
            if status in stats:
                stats[status] = count
            stats["TOTAL"] += count
        query.finish()
            
        return stats

    def get_groups_with_counts(self) -> List[Tuple[str, int]]:
        """Получение списка всех групп в БД с количеством узлов в них"""
        db = self.db_manager.get_db()
        if not db.isOpen():
            return []
            
        results = []
        query = QSqlQuery("SELECT grp, COUNT(*) FROM hosts GROUP BY grp ORDER BY grp", db)
        while query.next():
            grp = query.value(0) or "Без группы"
            cnt = query.value(1) or 0
            results.append((grp, int(cnt)))
        query.finish()
        return results

    def rename_group(self, old_name: str, new_name: str) -> int:
        """
        Переименование группы узлов в БД.
        Возвращает количество обновленных узлов.
        """
        db = self.db_manager.get_db()
        if not db.isOpen() or not old_name or not new_name:
            return 0

        query = QSqlQuery(db)
        query.prepare("UPDATE hosts SET grp = :new_name WHERE grp = :old_name")
        query.bindValue(":new_name", new_name)
        query.bindValue(":old_name", old_name)

        if query.exec_():
            updated = query.numRowsAffected()
            query.finish()
            if updated > 0:
                logging.info(f"Группа '{old_name}' переименована в '{new_name}' (обновлено {updated} узлов)")
                self._trigger_update()
            return updated
        else:
            err = query.lastError().text()
            query.finish()
            logging.error(f"Ошибка переименования группы '{old_name}' -> '{new_name}': {err}")
            return 0

    def delete_group(self, group_name: str, fallback_group: str = "Без группы") -> int:
        """
        Удаление группы узлов из БД: все узлы переносятся в fallback_group.
        Возвращает количество перемещенных узлов.
        """
        db = self.db_manager.get_db()
        if not db.isOpen() or not group_name:
            return 0

        query = QSqlQuery(db)
        query.prepare("UPDATE hosts SET grp = :fallback_group WHERE grp = :group_name")
        query.bindValue(":fallback_group", fallback_group)
        query.bindValue(":group_name", group_name)

        if query.exec_():
            moved = query.numRowsAffected()
            query.finish()
            logging.info(f"Группа '{group_name}' удалена (перемещено {moved} узлов в '{fallback_group}')")
            self._trigger_update()
            return moved
        else:
            err = query.lastError().text()
            query.finish()
            logging.error(f"Ошибка при удалении группы '{group_name}': {err}")
            return 0


