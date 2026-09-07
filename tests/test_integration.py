#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for the monitoring application.
Tests end-to-end workflows and component interactions.
"""

import unittest
import sys
import os
import tempfile
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import TestFixtures
from models import Host, AppConfig
from database import DatabaseManager
from data_manager import DataManager
from core.host_repository import HostRepository
from storage import StorageManager
from monitor_thread import MonitorThread


class TestHostLifecycle(unittest.TestCase):
    """Test complete host lifecycle from add to delete."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QCoreApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup database and repository."""
        self.db_manager = TestFixtures.create_in_memory_db()
        self.data_manager = DataManager(self.db_manager)
        self.repository = HostRepository(self.data_manager)
    
    def tearDown(self):
        """Cleanup."""
        TestFixtures.cleanup_db(self.db_manager)
    
    def test_complete_host_lifecycle(self):
        """Test: add → retrieve → update → delete."""
        # 1. Add host
        host = TestFixtures.create_sample_host(
            name="LifecycleTest",
            ip="192.168.100.1",
            status="ONLINE"
        )
        self.repository.add(host)
        
        # 2. Retrieve and verify
        all_hosts = self.repository.get_all()
        self.assertEqual(len(all_hosts), 1)
        self.assertEqual(all_hosts[0].name, "LifecycleTest")
        
        # 3. Update status
        now = datetime.now(timezone.utc).isoformat()
        self.repository.update_status(host.id, "OFFLINE", offline_since=now)
        
        # Verify update
        updated = self.repository.get_all()[0]
        self.assertEqual(updated.status, "OFFLINE")
        self.assertIsNotNone(updated.offline_since)
        
        # 4. Delete
        self.repository.delete(host.id)
        
        # Verify deletion
        final_hosts = self.repository.get_all()
        self.assertEqual(len(final_hosts), 0)


class TestExcelIntegration(unittest.TestCase):
    """Test Excel import/export integration with database."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QCoreApplication once for all tests."""
        TestFixtures.setup_qapp()
        
        # Check if openpyxl is available
        try:
            import openpyxl
            cls.has_openpyxl = True
        except ImportError:
            cls.has_openpyxl = False
    
    def setUp(self):
        """Setup database and temp directory."""
        if not self.has_openpyxl:
            self.skipTest("openpyxl not available")
        
        self.db_manager = TestFixtures.create_in_memory_db()
        self.data_manager = DataManager(self.db_manager)
        self.repository = HostRepository(self.data_manager)
        
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Cleanup."""
        TestFixtures.cleanup_db(self.db_manager)
        
        # Cleanup temp files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_export_and_import_cycle(self):
        """Test exporting hosts to Excel and importing them back."""
        from excel_service import ExcelService
        
        # 1. Add hosts to database
        hosts = TestFixtures.create_sample_hosts(5)
        for host in hosts:
            self.repository.add(host)
        
        # 2. Export to Excel
        excel_path = os.path.join(self.temp_dir, "export.xlsx")
        all_hosts = self.repository.get_all()
        ExcelService.export_hosts(excel_path, all_hosts)
        
        # 3. Clear database
        for host in all_hosts:
            self.repository.delete(host.id)
        
        self.assertEqual(len(self.repository.get_all()), 0)
        
        # 4. Import from Excel
        existing_ips = set()
        imported_hosts, skipped, errors = ExcelService.import_hosts(excel_path, existing_ips)
        
        # 5. Add imported hosts to database
        for host in imported_hosts:
            self.repository.add(host)
        
        # 6. Verify
        final_hosts = self.repository.get_all()
        self.assertEqual(len(final_hosts), 5)


class TestMonitoringIntegration(unittest.TestCase):
    """Test integration between monitoring thread and repository."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QCoreApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup database, repository, and monitor."""
        self.db_manager = TestFixtures.create_in_memory_db()
        self.data_manager = DataManager(self.db_manager)
        self.repository = HostRepository(self.data_manager)
        
        # Create config
        self.config = AppConfig(
            poll_interval=1,
            waiting_timeout=5,
            offline_timeout=10,
            max_workers=5
        )
        
        # Create monitor thread
        self.monitor = MonitorThread(self.repository, self.config)
    
    def tearDown(self):
        """Cleanup."""
        # Stop monitor if running
        if self.monitor.isRunning():
            self.monitor.stop()
            self.monitor.wait(1000)
        
        TestFixtures.cleanup_db(self.db_manager)
    
    def test_monitor_thread_initialization(self):
        """Test that monitor thread initializes correctly."""
        self.assertFalse(self.monitor.isRunning())
    
    def test_monitor_start_stop(self):
        """Test starting and stopping monitor thread."""
        # Add a host
        host = TestFixtures.create_sample_host()
        self.repository.add(host)
        
        # Start monitor
        self.monitor.start()
        
        # Give it a moment
        import time
        time.sleep(0.1)
        
        self.assertTrue(self.monitor.isRunning())
        
        # Stop monitor
        self.monitor.stop()
        self.monitor.wait(2000)  # Wait max 2 seconds
        
        self.assertFalse(self.monitor.isRunning())


class TestStorageMigration(unittest.TestCase):
    """Test migration from JSON storage to database."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QCoreApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Cleanup."""
        os.chdir(self.original_cwd)
        
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_json_to_database_migration(self):
        """Test complete migration workflow."""
        # 1. Create JSON storage with hosts
        storage = StorageManager()
        hosts = TestFixtures.create_sample_hosts(3)
        storage.save_hosts(hosts)
        
        # 2. Create database
        db_manager = TestFixtures.create_in_memory_db()
        
        # 3. Migrate
        success = storage.migrate_to_db(db_manager)
        self.assertTrue(success)
        
        # 4. Verify data in database
        data_manager = DataManager(db_manager)
        db_hosts = data_manager.get_all_hosts()
        
        self.assertEqual(len(db_hosts), 3)
        
        # 5. Verify JSON file was backed up
        import pathlib
        self.assertFalse(pathlib.Path("hosts.json").exists())
        self.assertTrue(pathlib.Path("hosts.json.bak").exists())
        
        # Cleanup
        TestFixtures.cleanup_db(db_manager)


if __name__ == '__main__':
    unittest.main()
