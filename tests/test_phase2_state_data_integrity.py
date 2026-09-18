#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для Этапа 2: Состояние UI, целостность данных, синхронизация потоков и настроек
"""

import sys
import os
import time
import unittest
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtCore import QPersistentModelIndex

from models import Host, AppConfig
from table_model import HostTableModel
from monitor_thread import MonitorThread
from host_manager import HostManager
from dialogs import GroupManagerDialog
from database import DatabaseManager
from data_manager import DataManager
from core.host_repository import HostRepository
from services import PingService


class TestPhase2StateDataIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_persistent_indexes_mapped_on_sort_and_status_update(self):
        """
        Проверка: при сортировке и обновлении статуса persistent indexes
        должны сохранять привязку к исходному Host ID, а не застревать на старых номерах строк.
        """
        model = HostTableModel()
        host_a = Host(id="id-a", name="Beta", ip="10.0.0.2", status="ONLINE")
        host_b = Host(id="id-b", name="Alpha", ip="10.0.0.1", status="ONLINE")
        model.set_hosts([host_a, host_b])

        # Строка 0 = host_a ("Beta"), Строка 1 = host_b ("Alpha")
        self.assertEqual(model.get_host(0).id, "id-a")
        self.assertEqual(model.get_host(1).id, "id-b")

        # Создаем persistent index для host_a (строка 0)
        p_index_a = QPersistentModelIndex(model.index(0, 0))
        # Создаем persistent index для host_b (строка 1)
        p_index_b = QPersistentModelIndex(model.index(1, 0))

        # Сортируем по имени (колонка 1, Ascending): "Alpha" станет строкой 0, "Beta" строкой 1
        from PyQt5.QtCore import Qt
        model.sort(1, Qt.AscendingOrder)

        # Проверяем, что persistent index для host_a теперь указывает на строку 1
        self.assertEqual(p_index_a.row(), 1)
        self.assertEqual(model.get_host(p_index_a.row()).id, "id-a")

        # Проверяем, что persistent index для host_b теперь указывает на строку 0
        self.assertEqual(p_index_b.row(), 0)
        self.assertEqual(model.get_host(p_index_b.row()).id, "id-b")

    def test_persistent_indexes_mapped_on_status_change_reorder(self):
        """
        Проверка: когда при активной сортировке по статусу узел меняет статус
        в update_hosts, persistent indexes должны оставаться на своих хостах.
        """
        model = HostTableModel()
        host_1 = Host(id="id-1", name="Host 1", ip="10.0.0.1", status="ONLINE")
        host_2 = Host(id="id-2", name="Host 2", ip="10.0.0.2", status="ONLINE")
        model.set_hosts([host_1, host_2])

        from PyQt5.QtCore import Qt
        model.sort(0, Qt.AscendingOrder) # Сортировка по статусу

        p_index_1 = QPersistentModelIndex(model.index(0, 0))
        p_index_2 = QPersistentModelIndex(model.index(1, 0))

        # host_1 падает в OFFLINE -> при сортировке по статусу он должен сместиться
        updated_host_1 = Host(id="id-1", name="Host 1", ip="10.0.0.1", status="OFFLINE")
        model.update_hosts([updated_host_1])

        # persistent index 1 должен следовать за host-1
        self.assertEqual(model.get_host(p_index_1.row()).id, "id-1")
        self.assertEqual(model.get_host(p_index_2.row()).id, "id-2")

    def test_maintenance_status_not_overwritten_by_online_ping(self):
        """
        Проверка: если узел переведен в MAINTENANCE, успешный ping (ONLINE)
        НЕ должен менять статус узла на ONLINE.
        """
        thread = MonitorThread(MagicMock(), AppConfig())
        host = Host(id="id-m", name="Server", ip="10.0.0.1", status="MAINTENANCE")
        now = datetime.now(timezone.utc)

        new_status, offline_since, should_update = thread._calculate_status(host, "ONLINE", now)
        self.assertEqual(new_status, "MAINTENANCE")
        self.assertFalse(should_update)

    def test_group_name_length_validation_in_dialog(self):
        """Проверка отклонения группы длиннее 50 символов в GroupManagerDialog"""
        storage = MagicMock()
        repo = MagicMock()
        repo.get_groups_with_counts.return_value = []
        config = AppConfig()
        config.custom_groups = []

        dialog = GroupManagerDialog(None, repository=repo, config=config, storage=storage)
        with patch("PyQt5.QtWidgets.QInputDialog.getText", return_value=("A" * 51, True)):
            with patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn:
                dialog._on_add_group()
                mock_warn.assert_called_once()
                self.assertNotIn("A" * 51, config.custom_groups)

    def test_group_rename_length_validation_in_repo(self):
        """Проверка: репозиторий отклоняет переименование группы в имя > 50 символов"""
        from core.host_repository import HostRepository
        repo = HostRepository(MagicMock())
        with pytest.raises(ValueError):
            repo.rename_group("Старая", "X" * 51)

    def test_monitor_thread_update_config_updates_workers_when_mutated(self):
        """
        Проверка: MonitorThread пересоздает пул потоков при смене max_workers,
        даже если объект AppConfig был мутирован до вызова update_config.
        """
        config = AppConfig(max_workers=5)
        thread = MonitorThread(MagicMock(), config)
        self.assertEqual(thread._executor._max_workers, 5)

        # Симулируем мутацию в UI до вызова update_config
        config.max_workers = 12
        thread.update_config(config)

        self.assertEqual(thread._executor._max_workers, 12)
        thread.stop()


def test_monitor_cycle_updates_host_through_thread_connection(tmp_path):
    """Полный цикл мониторинга применяет результат пинга через реальный репозиторий."""
    from PyQt5.QtSql import QSqlDatabase

    app = QApplication.instance() or QApplication([])
    if QSqlDatabase.contains("qt_sql_default_connection"):
        existing = QSqlDatabase.database("qt_sql_default_connection", open=False)
        existing.close()
        del existing
        QSqlDatabase.removeDatabase("qt_sql_default_connection")

    db_manager = DatabaseManager(str(tmp_path / "monitor-cycle.db"))
    repository = HostRepository(DataManager(db_manager))
    host = Host(id="runtime-host", name="Runtime", ip="127.0.0.1", status="OFFLINE")
    assert repository.add(host)

    monitor = MonitorThread(repository, AppConfig(poll_interval=1), db_manager.db_name)
    monitor.host_status_changed.connect(repository.update_status)
    try:
        with patch.object(PingService, "ping_host", return_value=True):
            monitor.start()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                app.processEvents()
                current = repository.get(host.id)
                if current and current.status == "ONLINE" and current.last_seen:
                    break
                time.sleep(0.01)

        current = repository.get(host.id)
        assert current.status == "ONLINE"
        assert current.last_seen is not None
    finally:
        monitor.stop()
        db_manager.close()
