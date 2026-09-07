
import unittest
from datetime import datetime
import sys
import os

from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtCore import QCoreApplication

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from data_manager import DataManager
from core.host_repository import HostRepository
from models import Host

class TestHostRepository(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We need QCoreApplication for Database handling occasionally 
        if not QCoreApplication.instance():
            cls.app = QCoreApplication([])

    def setUp(self):
        # Use in-memory DB
        
        # Remove default if exists (cleanup from other tests?)
        if QSqlDatabase.contains("qt_sql_default_connection"):
             QSqlDatabase.removeDatabase("qt_sql_default_connection")
             
        self.db_manager = DatabaseManager(":memory:")
        self.data_manager = DataManager(self.db_manager)
        self.repository = HostRepository(self.data_manager)

    def tearDown(self):
        self.db_manager.close()
        del self.db_manager
        # removeDatabase must be called when db object is garbage collected or after invalidating it
        QSqlDatabase.removeDatabase("qt_sql_default_connection")

    def test_add_and_get_host(self):
        host = Host(id="1", ip="192.168.1.1", name="TestHost")
        
        self.repository.add(host)
        
        hosts = self.repository.get_all()
        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0].name, "TestHost")
        self.assertEqual(hosts[0].ip, "192.168.1.1")

    def test_update_status(self):
        host = Host(id="1", ip="192.168.1.1", name="TestHost", status="UNKNOWN")
        self.repository.add(host)
        
        now = datetime.now()
        self.repository.update_status("1", "ONLINE", offline_since=None)
        
        updated_hosts = self.repository.get_all()
        self.assertEqual(updated_hosts[0].status, "ONLINE")
        val = updated_hosts[0].offline_since
        self.assertTrue(val is None or val == "")
        
        # Update to OFFLINE
        iso_now = now.isoformat()
        self.repository.update_status("1", "OFFLINE", offline_since=iso_now)
        
        updated_hosts_2 = self.repository.get_all()
        self.assertEqual(updated_hosts_2[0].status, "OFFLINE")
        self.assertEqual(updated_hosts_2[0].offline_since, iso_now)

    def test_batch_add_and_duplicates(self):
        # Schema constraints? Primary key is ID.
        hosts = [
            Host(id="1", ip="1.1.1.1", name="H1"),
            Host(id="2", ip="2.2.2.2", name="H2"),
            Host(id="3", ip="3.3.3.3", name="H3")
        ]
        
        added, errors = self.repository.add_hosts(hosts)
        
        self.assertEqual(added, 3)
        self.assertEqual(errors, 0)
        
        all_hosts = self.repository.get_all()
        self.assertEqual(len(all_hosts), 3)
        
        # Test Duplicate ID
        duplicate_host = Host(id="1", ip="1.1.1.1", name="Duplicate")
        # add_hosts handles errors per row
        added, errors = self.repository.add_hosts([duplicate_host])
        
        self.assertEqual(added, 0)
        self.assertEqual(errors, 1)

    def test_delete_host(self):
        host = Host(id="1", ip="192.168.1.1", name="TestHost")
        self.repository.add(host)
        
        self.repository.delete("1")
        
        hosts = self.repository.get_all()
        self.assertEqual(len(hosts), 0)

if __name__ == '__main__':
    unittest.main()
