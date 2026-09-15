#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for group management (rename, delete, counts, and UI dialog).
"""

import unittest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from tests.conftest import TestFixtures
from models import Host, AppConfig
from data_manager import DataManager
from core.host_repository import HostRepository
from dialogs import GroupManagerDialog


class TestGroupManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def setUp(self):
        self.db_manager = TestFixtures.create_in_memory_db()
        self.data_manager = DataManager(self.db_manager)
        self.repository = HostRepository(self.data_manager)

        # Добавляем хосты в разные группы
        self.h1 = Host(id="h1", ip="192.168.1.1", name="Host 1", group="Серверы")
        self.h2 = Host(id="h2", ip="192.168.1.2", name="Host 2", group="Серверы")
        self.h3 = Host(id="h3", ip="192.168.1.3", name="Host 3", group="АТМ")
        self.repository.add(self.h1)
        self.repository.add(self.h2)
        self.repository.add(self.h3)

    def tearDown(self):
        TestFixtures.cleanup_db(self.db_manager)

    def test_get_groups_with_counts(self):
        """Проверка получения списка групп с количеством узлов."""
        counts = dict(self.repository.get_groups_with_counts())
        self.assertEqual(counts.get("Серверы"), 2)
        self.assertEqual(counts.get("АТМ"), 1)

    def test_rename_group(self):
        """Проверка переименования группы и обновления всех узлов в БД."""
        updated = self.repository.rename_group("Серверы", "Инфраструктура")
        self.assertEqual(updated, 2)

        # Проверяем, что хосты теперь в новой группе
        h1_updated = self.repository.get("h1")
        h2_updated = self.repository.get("h2")
        self.assertEqual(h1_updated.group, "Инфраструктура")
        self.assertEqual(h2_updated.group, "Инфраструктура")

        # АТМ не изменились
        h3 = self.repository.get("h3")
        self.assertEqual(h3.group, "АТМ")

    def test_delete_group_moves_hosts_to_fallback(self):
        """Проверка удаления группы с переносом хостов в 'Без группы'."""
        moved = self.repository.delete_group("Серверы", fallback_group="Без группы")
        self.assertEqual(moved, 2)

        h1_updated = self.repository.get("h1")
        h2_updated = self.repository.get("h2")
        self.assertEqual(h1_updated.group, "Без группы")
        self.assertEqual(h2_updated.group, "Без группы")

    def test_group_manager_dialog_add_group(self):
        """Проверка добавления группы через диалог."""
        config = AppConfig(custom_groups=["Кастомная 1"])
        mock_storage = MagicMock()

        dialog = GroupManagerDialog(
            parent=None,
            repository=self.repository,
            config=config,
            storage=mock_storage
        )

        with patch("dialogs.QInputDialog.getText", return_value=("Новая группа", True)):
            dialog._on_add_group()

        self.assertIn("Новая группа", config.custom_groups)
        mock_storage.save_config.assert_called_with(config)

    def test_group_manager_dialog_rename_group(self):
        """Проверка переименования группы через диалог."""
        config = AppConfig(custom_groups=["АТМ", "Пустая"])
        mock_storage = MagicMock()

        dialog = GroupManagerDialog(
            parent=None,
            repository=self.repository,
            config=config,
            storage=mock_storage
        )

        # Имитируем выбор группы 'АТМ'
        dialog._select_group("АТМ")

        with patch("dialogs.QInputDialog.getText", return_value=("АТМ Банка", True)):
            dialog._on_edit_group()

        self.assertIn("АТМ Банка", config.custom_groups)
        self.assertNotIn("АТМ", config.custom_groups)
        mock_storage.save_config.assert_called_with(config)

        # В БД хост также обновился
        h3 = self.repository.get("h3")
        self.assertEqual(h3.group, "АТМ Банка")

    def test_group_manager_dialog_delete_group_with_confirmation(self):
        """Проверка удаления группы с подтверждением переноса хостов."""
        config = AppConfig(custom_groups=["Серверы"])
        mock_storage = MagicMock()

        dialog = GroupManagerDialog(
            parent=None,
            repository=self.repository,
            config=config,
            storage=mock_storage
        )

        dialog._select_group("Серверы")

        # Мокаем подтверждение пользователя (Yes)
        with patch("dialogs.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog._on_delete_group()

        self.assertNotIn("Серверы", config.custom_groups)
        mock_storage.save_config.assert_called_with(config)

        # Хосты перенесены в 'Без группы'
        self.assertEqual(self.repository.get("h1").group, "Без группы")
        self.assertEqual(self.repository.get("h2").group, "Без группы")

    def test_group_manager_dialog_cannot_delete_default_group(self):
        """Проверка защиты от удаления системной группы 'Без группы'."""
        config = AppConfig(custom_groups=[])
        mock_storage = MagicMock()

        dialog = GroupManagerDialog(
            parent=None,
            repository=self.repository,
            config=config,
            storage=mock_storage
        )

        dialog._select_group("Без группы")

        with patch("dialogs.QMessageBox.warning") as mock_warning:
            dialog._on_delete_group()
            mock_warning.assert_called_once()


if __name__ == '__main__':
    unittest.main()
