import unittest
from unittest.mock import MagicMock, patch
import sys
import os

from PyQt5.QtCore import QCoreApplication, QPoint

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from context_menu_manager import ContextMenuManager
from models import Host


class TestContextMenuManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QCoreApplication.instance():
            cls.app = QCoreApplication([])

    def setUp(self):
        self.mock_parent = MagicMock()
        self.mock_table = MagicMock()
        self.mock_table_model = MagicMock()
        self.mock_repo = MagicMock()
        self.manager = ContextMenuManager(
            parent=self.mock_parent,
            table=self.mock_table,
            table_model=self.mock_table_model,
            groups=["Default"],
            theme_getter=lambda: "dark",
            repository=self.mock_repo
        )

    @patch("context_menu_manager.subprocess.Popen")
    @patch("context_menu_manager.QMessageBox.warning")
    def test_ping_cmd_rejects_malformed_ip(self, mock_warning, mock_popen):
        """Test that invalid or dangerous IP inputs are rejected without running subprocess."""
        dangerous_ips = [
            "127.0.0.1 & calc.exe",
            "192.168.1.1; echo hack",
            "8.8.8.8 | whoami",
            "999.999.999.999",
            "-t 192.168.1.1",
            ""
        ]

        for bad_ip in dangerous_ips:
            mock_popen.reset_mock()
            mock_warning.reset_mock()

            self.manager._ping_cmd(bad_ip)

            mock_popen.assert_not_called()
            mock_warning.assert_called_once()

    @patch("context_menu_manager.subprocess.Popen")
    @patch("context_menu_manager.QMessageBox.warning")
    def test_ping_cmd_valid_ip(self, mock_warning, mock_popen):
        """Test that valid IP executes subprocess and does not trigger error."""
        valid_ip = "192.168.1.1"
        self.manager._ping_cmd(valid_ip)

        mock_warning.assert_not_called()
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn(valid_ip, args)

    @patch("context_menu_manager.subprocess.Popen")
    @patch("context_menu_manager.sys")
    @patch("context_menu_manager.QMessageBox.warning")
    def test_ping_cmd_linux_safe_args(self, mock_warning, mock_sys, mock_popen):
        """Test that non-Windows uses list arguments instead of formatted shell string."""
        mock_sys.platform = "linux"
        valid_ip = "10.0.0.1"
        self.manager._ping_cmd(valid_ip)

        mock_warning.assert_not_called()
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        # Should be list: ['xterm', '-e', 'ping', '10.0.0.1']
        self.assertEqual(args, ['xterm', '-e', 'ping', valid_ip])

    @patch("context_menu_manager.QMessageBox.information")
    def test_show_context_menu_for_host_id_missing_host(self, mock_info):
        """Проверка безопасного поведения при отсутствии хоста в базе."""
        self.mock_repo.get.return_value = None
        self.manager.show_context_menu_for_host_id("non_existent_id", QPoint(100, 100))
        mock_info.assert_called_once()
        self.assertIn("не найден", mock_info.call_args[0][2])

    def test_show_context_menu_for_host_id_found(self):
        """Проверка вызова show_menu_for_host при нахождении хоста."""
        host = Host(id="h1", ip="192.168.1.10", name="TestHost")
        self.mock_repo.get.return_value = host

        with patch.object(self.manager, "show_menu_for_host") as mock_show_menu:
            pt = QPoint(50, 60)
            self.manager.show_context_menu_for_host_id("h1", pt)
            mock_show_menu.assert_called_once_with(host, pt)

    def test_event_log_panel_context_menu_signal(self):
        """Проверка эмиссии сигнала host_context_menu_requested из EventLogPanel."""
        from history_views import EventLogPanel
        mock_repo = MagicMock()
        mock_repo.get_history_events.return_value = [
            {
                "host_id": "host_42",
                "host_name": "Switch42",
                "old_status": "ONLINE",
                "new_status": "OFFLINE",
                "timestamp": "2026-09-14T10:00:00+00:00"
            }
        ]

        panel = EventLogPanel(repository=mock_repo, theme="dark")
        panel.refresh()

        received_signals = []
        panel.host_context_menu_requested.connect(lambda hid, pos: received_signals.append((hid, pos)))

        # Первый элемент списка
        item = panel._list.item(0)
        self.assertIsNotNone(item)
        self.assertEqual(item.data(1), None)  # Qt.UserRole = 32
        from PyQt5.QtCore import Qt
        self.assertEqual(item.data(Qt.UserRole), "host_42")

        # Имитируем запрос контекстного меню
        rect = panel._list.visualItemRect(item)
        panel._on_list_context_menu(rect.center())

        self.assertEqual(len(received_signals), 1)
        self.assertEqual(received_signals[0][0], "host_42")

    def test_history_dialog_table_context_menu(self):
        """Проверка вызова контекстного меню из таблицы HistoryDialog."""
        from history_views import HistoryDialog
        from PyQt5.QtWidgets import QWidget
        parent_widget = QWidget()
        parent_widget._context_menu_manager = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_history_events.return_value = [
            {
                "host_id": "host_99",
                "host_name": "Router99",
                "old_status": "ONLINE",
                "new_status": "OFFLINE",
                "timestamp": "2026-09-14T11:00:00+00:00"
            }
        ]

        dlg = HistoryDialog(parent=parent_widget, repository=mock_repo, groups=["Default"], theme="dark")
        dlg._refresh()

        self.assertEqual(dlg._table.rowCount(), 1)
        from PyQt5.QtCore import Qt
        self.assertEqual(dlg._table.item(0, 0).data(Qt.UserRole), "host_99")

        dlg._on_table_context_menu(QPoint(10, 10))
        parent_widget._context_menu_manager.show_context_menu_for_host_id.assert_called_once()
        args = parent_widget._context_menu_manager.show_context_menu_for_host_id.call_args[0]
        self.assertEqual(args[0], "host_99")

    def test_is_atm_group(self):
        """Проверка корректности определения группы АТМ / Банкоматы"""
        self.assertTrue(ContextMenuManager.is_atm_group("АТМ"))
        self.assertTrue(ContextMenuManager.is_atm_group("ATM"))
        self.assertTrue(ContextMenuManager.is_atm_group("атм"))
        self.assertTrue(ContextMenuManager.is_atm_group("АТМ_1"))
        self.assertTrue(ContextMenuManager.is_atm_group("Банкоматы"))
        self.assertTrue(ContextMenuManager.is_atm_group("Банкомат 42"))
        self.assertFalse(ContextMenuManager.is_atm_group("Серверы"))
        self.assertFalse(ContextMenuManager.is_atm_group("Платформа"))
        self.assertFalse(ContextMenuManager.is_atm_group("Без группы"))
        self.assertFalse(ContextMenuManager.is_atm_group(""))
        self.assertFalse(ContextMenuManager.is_atm_group(None))

    @patch("context_menu_manager.QMenu.exec_")
    def test_helpdesk_menu_only_for_atm_group(self, mock_exec):
        """Проверка, что пункты меню Helpdesk добавляются только для узлов из группы АТМ"""
        self.mock_parent._config = MagicMock()
        self.mock_parent._config.helpdesk_enabled = True

        # 1. Хост не из группы АТМ (например, Серверы)
        server_host = Host(id="h1", ip="192.168.1.10", name="Server1", group="Серверы")
        with patch("context_menu_manager.QMenu.addAction") as mock_add_action:
            self.manager.show_menu_for_host(server_host, QPoint(0, 0))
            labels = [call[0][1] for call in mock_add_action.call_args_list if len(call[0]) > 1]
            self.assertFalse(any("Helpdesk" in label for label in labels))

        # 2. Хост из группы АТМ
        atm_host = Host(id="h2", ip="192.168.1.20", name="ATM001", group="АТМ")
        with patch("context_menu_manager.QMenu.addAction") as mock_add_action:
            self.manager.show_menu_for_host(atm_host, QPoint(0, 0))
            labels = [call[0][1] for call in mock_add_action.call_args_list if len(call[0]) > 1]
            self.assertTrue(any("Helpdesk: открыть заявку" in label for label in labels))
            self.assertTrue(any("Helpdesk: закрыть заявку" in label for label in labels))

    @patch("context_menu_manager.HelpdeskService.process_offline")
    @patch("context_menu_manager.QInputDialog.getItem")
    @patch("context_menu_manager.QMenu.exec_")
    def test_new_helpdesk_reason_is_saved_to_config(self, mock_exec, mock_get_item, mock_process):
        """Проверка, что новая введенная причина сохраняется в config.helpdesk_reasons и на диск."""
        self.mock_parent._config = MagicMock()
        self.mock_parent._config.helpdesk_enabled = True
        self.mock_parent._config.helpdesk_reasons = ["без связи", "ошибка пинга"]
        self.mock_parent._storage = MagicMock()

        atm_host = Host(id="h1", ip="192.168.1.10", name="ATM_01", group="АТМ")

        # Настраиваем QInputDialog на ввод новой причины
        mock_get_item.return_value = ("новая причина от пользователя", True)

        # Мокаем выбор пункта Helpdesk: открыть заявку в меню
        def fake_exec(pos):
            # Возвращаем action_hd_set, который был добавлен
            return self.manager._last_action_hd_set

        with patch("context_menu_manager.QMenu.addAction") as mock_add_action:
            action_mock = MagicMock()
            def side_effect(*args, **kwargs):
                nonlocal action_mock
                act = MagicMock()
                if len(args) > 1 and "открыть заявку" in args[1]:
                    self.manager._last_action_hd_set = act
                return act
            mock_add_action.side_effect = side_effect
            mock_exec.side_effect = lambda pos: self.manager._last_action_hd_set

            self.manager.show_menu_for_host(atm_host, QPoint(0, 0))

        # Проверяем, что новая причина добавлена в список
        self.assertIn("новая причина от пользователя", self.mock_parent._config.helpdesk_reasons)
        # Проверяем, что сохранение конфигурации было вызвано
        self.mock_parent._storage.save_config.assert_called_once_with(self.mock_parent._config)
        # Проверяем, что сервис был вызван с новой причиной
        mock_process.assert_called_once_with(["ATM_01"], self.mock_parent._config, "новая причина от пользователя")


if __name__ == '__main__':
    unittest.main()


