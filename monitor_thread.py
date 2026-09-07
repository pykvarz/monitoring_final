#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Поток мониторинга (Optimized & Clean Architecture).
Работает в связке с HostRepository.
"""

from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import time
import logging

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtSql import QSqlDatabase

from models import Host, AppConfig
from services import PingService
from core.host_repository import HostRepository

class MonitorThread(QThread):
    """
    Поток для мониторинга узлов.
    
    Ver 3.0:
    - Использует HostRepository как Single Source of Truth.
    - Агрегирует изменения статусов и обновляет их через репозиторий.
    """

    # Сигналы
    hosts_offline = pyqtSignal(list)  # Для уведомлений
    hosts_recovered = pyqtSignal(list)  # Для уведомлений о восстановлении
    scan_started = pyqtSignal()
    scan_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    # Новый сигнал для обновления статуса в главном потоке (Thread Safety)
    host_status_changed = pyqtSignal(str, str, object) # id, status, offline_since

    def __init__(self, repository: HostRepository, config: AppConfig):
        super().__init__()
        self._repository = repository
        self._config = config
        self._running = True
        self._executor: ThreadPoolExecutor = None
        self._force_scan_flag = False
        self._interrupt_flag = False  # Флаг для прерывания текущего цикла
        self._known_statuses: Dict[str, str] = {}  # Кеш статусов: {host_id: status}
        # Время последнего восстановления узла (OFFLINE/WAITING → ONLINE).
        # Используется для определения устаревшего offline_since из БД.
        self._recovery_times: Dict[str, datetime] = {}
        self._update_executor()

    def _update_executor(self) -> None:
        """Обновление пула потоков"""
        if self._executor:
            try:
                import sys
                if sys.version_info >= (3, 9):
                    self._executor.shutdown(wait=False, cancel_futures=True)
                else:
                    self._executor.shutdown(wait=False)
            except (RuntimeError, TypeError):
                pass
        self._executor = ThreadPoolExecutor(max_workers=self._config.max_workers)

    def update_config(self, config: AppConfig) -> None:
        """Обновление конфигурации"""
        old_max_workers = self._config.max_workers
        self._config = config
        if config.max_workers != old_max_workers:
            self._update_executor()

    def force_scan(self) -> None:
        """Принудительное сканирование"""
        self._force_scan_flag = True
    
    def interrupt_cycle(self) -> None:
        """
        Прервать текущий цикл мониторинга и запустить новый.
        Используется при критичных изменениях хостов (добавление, удаление, смена IP).
        """
        logging.info("MonitorThread: Cycle interrupt requested")
        self._interrupt_flag = True

    def remove_from_cache(self, host_id: str) -> None:
        """Удалить хост из кеша статусов (при удалении хоста)"""
        self._known_statuses.pop(host_id, None)

    def stop(self) -> None:
        self._running = False
        if self._executor:
            try:
                self._executor.shutdown(wait=True)
            except RuntimeError:
                pass
        self.wait()

    def _check_host(self, host: Host) -> Tuple[str, str, Optional[str]]:
        """Проверка одного узла"""
        try:
            if host.status == "MAINTENANCE":
                return (host.id, "MAINTENANCE", None)

            result = PingService.ping_host(host.ip, timeout=2.0)
            status = "ONLINE" if result else "OFFLINE"
            return (host.id, status, None)
        except Exception as e:
            return (host.id, "OFFLINE", str(e))

    def run(self) -> None:
        """Основной цикл"""
        # Создаем подключение к БД специально для этого потока
        connection_name = f"monitor_thread_{int(QThread.currentThreadId())}"
        
        try:
            if QSqlDatabase.contains(connection_name):
                db = QSqlDatabase.database(connection_name)
            else:
                db = QSqlDatabase.addDatabase("QSQLITE", connection_name)
                db.setDatabaseName("hosts.db")
            
            if not db.open():
                self.error_occurred.emit(f"Failed to open DB in thread: {db.lastError().text()}")
                return

            while self._running:
                try:
                    # 1. Получаем актуальный список хостов из Репозитория
                    # Используем наше потокобезопасное соединение
                    hosts = self._repository.get_all(connection_name=connection_name)

                    if not hosts:
                        self.msleep(1000)
                        continue
                    
                    self.scan_started.emit()

                    # 2. Запускаем параллельный пинг
                    futures: Dict[Future, Host] = {}
                    for host in hosts:
                        if not self._running:
                            break
                        future = self._executor.submit(self._check_host, host)
                        futures[future] = host

                    newly_offline = []
                    newly_recovered = []
                    current_time = datetime.now(timezone.utc)

                    # 3. Обрабатываем результаты
                    for future in as_completed(futures):
                        if not self._running or self._interrupt_flag:
                            break

                        host = futures[future]
                        try:
                            host_id, ping_status, error = future.result()
                            
                            # Логика смены статуса (Domain Logic)
                            # Логика смены статуса (Domain Logic)
                            new_status, offline_since, should_update = self._calculate_status(host, ping_status, current_time)

                            if should_update:
                                # Use signal to update in Main Thread (Thread Safety)
                                self.host_status_changed.emit(host_id, new_status, offline_since)
                                
                                # Notification Logic — используем кеш статусов потока
                                prev_status = self._known_statuses.get(host_id, host.status)
                                if new_status == "OFFLINE" and prev_status != "OFFLINE" and host.notifications_enabled:
                                    newly_offline.append(host.name)
                                elif new_status == "ONLINE" and prev_status == "OFFLINE" and host.notifications_enabled:
                                    newly_recovered.append(host.name)
                                
                                # Обновляем кеш
                                self._known_statuses[host_id] = new_status
                                # Фиксируем момент восстановления для сброса
                                # устаревшего offline_since при следующем падении
                                if new_status == "ONLINE":
                                    self._recovery_times[host_id] = current_time

                        except Exception as e:
                            logging.error(f"Error processing host result: {e}")
                    
                    # Проверяем флаг прерывания
                    if self._interrupt_flag:
                        logging.info("MonitorThread: Cycle interrupted, restarting immediately")
                        self._interrupt_flag = False
                        continue  # Немедленно начать новый цикл

                    if newly_offline:
                        self.hosts_offline.emit(newly_offline)

                    if newly_recovered:
                        self.hosts_recovered.emit(newly_recovered)

                    self.scan_finished.emit()

                    # Пауза
                    elapsed_wait = 0
                    while elapsed_wait < self._config.poll_interval * 1000 and self._running:
                        self.msleep(100)
                        elapsed_wait += 100
                        
                        # Проверка флагов для прерывания паузы
                        if self._force_scan_flag:
                            self._force_scan_flag = False
                            break
                        if self._interrupt_flag:
                            self._interrupt_flag = False
                            logging.info("MonitorThread: Wait interrupted, starting new cycle")
                            break

                except Exception as e:
                    logging.error(f"Global monitor loop error inside loop: {e}")
                    self.error_occurred.emit(f"Global monitor loop error: {e}")
                    self.msleep(5000)

        except Exception as e:
             logging.error(f"Critical MonitorThread error (setup): {e}")
             self.error_occurred.emit(f"Critical MonitorThread error: {e}")

    def _calculate_status(self, host: Host, ping_status: str, current_time: datetime) -> Tuple[str, Optional[str], bool]:
        """
        Pure function to calculate next status.
        Returns: (new_status, offline_since, should_update)
        """
        new_status = host.status
        offline_since = host.offline_since
        should_update = False
        
        if ping_status == "ONLINE":
            if host.status != "ONLINE":
                new_status = "ONLINE"
                offline_since = None
                should_update = True
            
            # Optimization: Heartbeat Throttling (Reduce DB I/O)
            # Only update last_seen if it's been more than 60 seconds (or never set)
            # This prevents writing to DB on every single ping (e.g. every 2s)
            elif not should_update:
                if not host.last_seen:
                    should_update = True
                else:
                    try:
                        last_seen_dt = datetime.fromisoformat(host.last_seen)
                        if last_seen_dt.tzinfo is None:
                            last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                        
                        # Throttle threshold: 60 seconds
                        if (current_time - last_seen_dt).total_seconds() > 60:
                             should_update = True
                             
                    except ValueError:
                        should_update = True

        else: # ping_status == "OFFLINE"
            if host.status == "MAINTENANCE":
                return host.status, host.offline_since, False

            # Если узел уже OFFLINE — он остаётся OFFLINE, никакого отката в WAITING
            if host.status == "OFFLINE":
                if not host.offline_since:
                    offline_since = current_time.isoformat()
                    should_update = True
                return "OFFLINE", offline_since, should_update

            # Проверяем, не является ли offline_since устаревшим от прошлого падения.
            # Ситуация: узел упал → восстановился → снова упал. Batch-запись
            # восстановления (offline_since=NULL) могла не успеть дойти до потока
            # мониторинга, поэтому host.offline_since может содержать старый timestamp.
            # Сравниваем offline_since с временем последнего зафиксированного
            # восстановления: если offline_since < recovery_time — он устаревший.
            # Важно: после сброса (offline_since=now) он станет свежее recovery_time
            # и на следующем пинге сбрасываться уже не будет — таймер накапливается.
            recovery_time = self._recovery_times.get(host.id)
            if offline_since and recovery_time:
                try:
                    os_dt = datetime.fromisoformat(offline_since)
                    if os_dt.tzinfo is None:
                        os_dt = os_dt.replace(tzinfo=timezone.utc)
                    if os_dt < recovery_time:
                        offline_since = None  # Устаревший — сбрасываем
                except ValueError:
                    offline_since = None

            if not offline_since:
                offline_since = current_time.isoformat()
                should_update = True
            
            if offline_since:
                try:
                    start_dt = datetime.fromisoformat(offline_since)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    duration = (current_time - start_dt).total_seconds()
                    
                    if duration >= self._config.offline_timeout:
                        if host.status != "OFFLINE":
                            new_status = "OFFLINE"
                            should_update = True
                    elif duration >= self._config.waiting_timeout:
                        if host.status != "WAITING":
                            new_status = "WAITING"
                            should_update = True
                except ValueError:
                    offline_since = current_time.isoformat()
                    should_update = True
                    
        return new_status, offline_since, should_update
