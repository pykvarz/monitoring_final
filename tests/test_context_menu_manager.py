import unittest
from unittest.mock import MagicMock, patch
import sys
import os

from PyQt5.QtCore import QCoreApplication

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from context_menu_manager import ContextMenuManager


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


if __name__ == '__main__':
    unittest.main()
