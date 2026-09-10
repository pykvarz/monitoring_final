import unittest
from unittest.mock import MagicMock, patch
import sys
import os

from PyQt5.QtWidgets import QDialog
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtCore import QCoreApplication

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from data_manager import DataManager
from core.host_repository import HostRepository
from host_manager import HostManager
from models import Host


class TestHostManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QCoreApplication.instance():
            cls.app = QCoreApplication([])

    def setUp(self):
        if QSqlDatabase.contains("qt_sql_default_connection"):
            QSqlDatabase.removeDatabase("qt_sql_default_connection")
        self.db_manager = DatabaseManager(":memory:")
        self.data_manager = DataManager(self.db_manager)
        self.repository = HostRepository(self.data_manager)

    def tearDown(self):
        self.db_manager.close()
        del self.db_manager
        QSqlDatabase.removeDatabase("qt_sql_default_connection")

    @patch("host_manager.QMessageBox.warning")
    @patch("host_manager.HostDialog")
    def test_add_host_duplicate_ip(self, mock_dialog_cls, mock_warning):
        # Add an initial host
        initial_host = Host(id="1", ip="192.168.1.50", name="ExistingHost")
        self.repository.add(initial_host)

        # Configure mock dialog to return accepted with same IP
        mock_dialog = MagicMock()
        mock_dialog.exec_.return_value = QDialog.Accepted
        mock_dialog.get_host.return_value = Host(id="2", ip="192.168.1.50", name="DuplicateHost")
        mock_dialog_cls.return_value = mock_dialog

        # Try to add host with duplicate IP
        result = HostManager.add_host(None, ["Default"], self.repository)

        self.assertFalse(result)
        mock_warning.assert_called_once()
        self.assertIn("уже существует", mock_warning.call_args[0][2])
        self.assertEqual(len(self.repository.get_all()), 1)

    @patch("host_manager.QMessageBox.warning")
    @patch("host_manager.HostDialog")
    def test_edit_host_duplicate_ip(self, mock_dialog_cls, mock_warning):
        # Add two hosts
        h1 = Host(id="1", ip="192.168.1.50", name="Host1")
        h2 = Host(id="2", ip="192.168.1.51", name="Host2")
        self.repository.add(h1)
        self.repository.add(h2)

        # Mock table_model
        mock_table_model = MagicMock()
        mock_table_model.get_host.return_value = h2

        # Configure mock dialog to change h2's IP to h1's IP
        mock_dialog = MagicMock()
        mock_dialog.exec_.return_value = QDialog.Accepted
        mock_dialog.get_host.return_value = Host(id="2", ip="192.168.1.50", name="Host2Edited")
        mock_dialog_cls.return_value = mock_dialog

        # Try to edit h2 to have h1's IP
        HostManager.edit_host(None, 1, mock_table_model, ["Default"], self.repository)

        mock_warning.assert_called_once()
        self.assertIn("уже существует", mock_warning.call_args[0][2])
        # Verify h2 IP didn't change in repository
        fetched_h2 = self.repository.get("2")
        self.assertEqual(fetched_h2.ip, "192.168.1.51")


if __name__ == '__main__':
    unittest.main()
