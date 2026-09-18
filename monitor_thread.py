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
import threading

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
    paused_state_changed = pyqtSignal(bool)
    
    # Новый сигнал для обновления статуса в главном потоке (Thread Safety)
    host_status_changed = pyqtSignal(str, str, object) # id, status, offline_since

    def __init__(self, repository: HostRepository, config: AppConfig, db_name: str = "hosts.db"):
        super().__init__()
        self._repository = repository
        self._config = config
        self._db_name = db_name
        self._running = True
        self._paused = False
        self._executor: ThreadPoolExecutor = None
        self._force_scan_flag = False
        self._interrupt_flag = False  # Флаг для прерывания текущего цикла
        self._known_statuses: Dict[str, str] = {}  # Кеш статусов: {host_id: status}
        # Время последнего восстановления узла (OFFLINE/WAITING → ONLINE).
        # Используется для определения устаревшего offline_since из БД.
        self._recovery_times: Dict[str, datetime] = {}
        self._offline_since_cache: Dict[str, str] = {}
        self._executor_lock = threading.Lock()
        self._update_executor()

    def _update_executor(self) -> None:
        """Обновление пула потоков с защитой блокировкой"""
        with self._executor_lock:
            old_executor = self._executor
            self._executor = ThreadPoolExecutor(max_workers=self._config.max_workers)

        if old_executor:
            try:
                import sys
                if sys.version_info >= (3, 9):
                    old_executor.shutdown(wait=False, cancel_futures=True)
                else:
                    old_executor.shutdown(wait=False)
            except (RuntimeError, TypeError):
                pass

    def update_config(self, config: AppConfig) -> None:
        """Обновление конфигурации"""
        current_workers = self._executor._max_workers if self._executor else 0
        self._config = config
        if config.max_workers != current_workers:
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
        self._recovery_times.pop(host_id, None)
        self._offline_since_cache.pop(host_id, None)

    def pause(self) -> None:
        """Приостановить мониторинг"""
        self._paused = True
        self.paused_state_changed.emit(True)

    def resume(self) -> None:
        """Возобновить мониторинг"""
        self._paused = False
        self.paused_state_changed.emit(False)

    def is_paused(self) -> bool:
        """Проверка статуса паузы"""
        return self._paused

    def toggle_pause(self) -> bool:
        """Переключить паузу (возвращает True если теперь на паузе)"""
        if self._paused:
            self.resume()
        else:
            self.pause()
        return self._paused

    def stop(self) -> None:
        self._running = False
        self._paused = False
        with self._executor_lock:
            if self._executor:
                try:
                    self._executor.shutdown(wait=False, cancel_futures=True)
                except (RuntimeError, TypeError):
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
                db.setDatabaseName(self._db_name)
            
            if not db.open():
                self.error_occurred.emit(f"Failed to open DB in thread: {db.lastError().text()}")
                return

            while self._running:
                try:
                    if self._paused:
                        self.msleep(150)
                        continue

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
                        try:
                            with self._executor_lock:
                                if not self._running:
                                    break
                                future = self._executor.submit(self._check_host, host)
                            futures[future] = host
                        except RuntimeError as e:
                            logging.warning(f"MonitorThread submit failed: {e}")

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
                            
                            # Защита от гонки: если за время пинга оператор перевел узел
                            # в MAINTENANCE — отбрасываем устаревший результат пинга
                            current_db_host = self._repository.get(host_id, connection_name=connection_name)
                            if current_db_host and current_db_host.status == "MAINTENANCE":
                                self._known_statuses[host_id] = "MAINTENANCE"
                                continue

                            # Логика смены статуса (Domain Logic)
                            new_status, offline_since, should_update = self._calculate_status(host, ping_status, current_time)

                            prev_status = self._known_statuses.get(host_id, host.status)

                            if should_update:
                                # Use signal to update in Main Thread (Thread Safety)
                                self.host_status_changed.emit(host_id, new_status, offline_since)
                                
                                # Notification Logic — используем кеш статусов потока
                                if new_status == "OFFLINE" and prev_status != "OFFLINE" and host.notifications_enabled:
                                    newly_offline.append(host.name)
                                elif new_status == "ONLINE" and prev_status in ("OFFLINE", "WAITING") and host.notifications_enabled:
                                    newly_recovered.append(host.name)
                                
                                # Обновляем кеш статусов
                                self._known_statuses[host_id] = new_status

                            # ВАЖНО: Фиксируем момент реального восстановления для сброса
                            # устаревшего offline_since при последующих падениях.
                            # Восстановление происходит ТОЛЬКО когда ping успешен (ONLINE)
                            # и узел до этого был в сбое (prev_status != ONLINE или имел offline_since).
                            if ping_status == "ONLINE":
                                if prev_status in ("WAITING", "OFFLINE") or host.offline_since is not None or host_id in self._offline_since_cache:
                                    self._recovery_times[host_id] = current_time
                                self._offline_since_cache.pop(host_id, None)
                            elif ping_status == "OFFLINE" and offline_since:
                                self._offline_since_cache[host_id] = offline_since

                        except Exception as e:
                            logging.error(f"Error processing host result: {e}")
                    
                    # Проверяем флаг прерывания
                    if self._interrupt_flag:
                        if newly_offline:
                            self.hosts_offline.emit(newly_offline)
                        if newly_recovered:
                            self.hosts_recovered.emit(newly_recovered)
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
                        if self._paused:
                            break
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
        finally:
            if QSqlDatabase.contains(connection_name):
                try:
                    thread_db = QSqlDatabase.database(connection_name)
                    if thread_db.isOpen():
                        thread_db.close()
                    del thread_db
                except Exception:
                    pass
                QSqlDatabase.removeDatabase(connection_name)

    def _calculate_status(self, host: Host, ping_status: str, current_time: datetime) -> Tuple[str, Optional[str], bool]:
        """
        Pure function to calculate next status.
        Returns: (new_status, offline_since, should_update)
        """
        # Если узел на тех.обслуживании — любой результат пинга игнорируется
        if host.status == "MAINTENANCE":
            return "MAINTENANCE", host.offline_since, False

        new_status = host.status
        offline_since = host.offline_since
        should_update = False
        
        if ping_status == "ONLINE":
            new_status = "ONLINE"
            if host.status != "ONLINE" or host.offline_since:
                offline_since = None
                should_update = True
            else:
                offline_since = None
            
            # Optimization: Heartbeat Throttling (Reduce DB I/O)
            # Only update last_seen if it's been more than 60 seconds (or never set)
            # This prevents writing to DB on every single ping (e.g. every 2s)
            if not should_update:
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

            # Восстанавливаем offline_since из локального кеша потока, если в объекте host он еще пуст
            if not offline_since and host.id in self._offline_since_cache:
                offline_since = self._offline_since_cache[host.id]

            # 1. Проверяем, не является ли offline_since устаревшим от прошлого падения
            recovery_time = self._recovery_times.get(host.id)
            if offline_since and recovery_time:
                try:
                    os_dt = datetime.fromisoformat(offline_since)
                    if os_dt.tzinfo is None:
                        os_dt = os_dt.replace(tzinfo=timezone.utc)
                    if os_dt < recovery_time:
                        offline_since = None  # Устаревший от прошлого падения — сбрасываем!
                except ValueError:
                    offline_since = None

            # 2. Если узел был ONLINE — это НОВОЕ падение, отсчёт простоя начинается сейчас!
            known_st = self._known_statuses.get(host.id, host.status)
            if host.status == "ONLINE" or known_st == "ONLINE":
                if not offline_since:
                    offline_since = current_time.isoformat()
                    should_update = True

            # 3. Если узел уже подтверждённо OFFLINE и offline_since актуален — остаётся OFFLINE
            if host.status == "OFFLINE" and offline_since:
                return "OFFLINE", offline_since, should_update

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
                    else:
                        # Еще не прошло время для статуса 'Ожидание'. 
                        # Остаемся в текущем статусе (обычно ONLINE).
                        pass
                except ValueError:
                    offline_since = current_time.isoformat()
                    should_update = True
                    
        return new_status, offline_since, should_update
