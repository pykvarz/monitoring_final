#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for storage.py - StorageManager class
"""

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import TestFixtures
from storage import StorageManager
from models import Host, AppConfig


class TestStorageManager(unittest.TestCase):
    """Tests for StorageManager."""
    
    def setUp(self):
        """Setup temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.storage = StorageManager()
    
    def tearDown(self):
        """Cleanup temporary files."""
        os.chdir(self.original_cwd)
        
        # Cleanup temp files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_load_hosts_empty(self):
        """Test loading hosts when file doesn't exist."""
        hosts = self.storage.load_hosts()
        self.assertEqual(hosts, [])
    
    def test_save_and_load_hosts(self):
        """Test saving and loading hosts."""
        # Create test hosts
        hosts = TestFixtures.create_sample_hosts(3)
        
        # Save
        success = self.storage.save_hosts(hosts)
        self.assertTrue(success)
        
        # Load
        loaded = self.storage.load_hosts()
        
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0].name, hosts[0].name)
        self.assertEqual(loaded[1].ip, hosts[1].ip)
    
    def test_save_hosts_creates_file(self):
        """Test that save_hosts creates the JSON file."""
        hosts = TestFixtures.create_sample_hosts(1)
        
        self.assertFalse(Path("hosts.json").exists())
        
        self.storage.save_hosts(hosts)
        
        self.assertTrue(Path("hosts.json").exists())
    
    def test_load_config_empty(self):
        """Test loading config when file doesn't exist."""
        config = self.storage.load_config()
        
        # Should return default config
        self.assertIsInstance(config, AppConfig)
        self.assertEqual(config.poll_interval, 10)
    
    def test_save_and_load_config(self):
        """Test saving and loading config."""
        # Create custom config
        config = AppConfig(
            poll_interval=15,
            waiting_timeout=120,
            theme="dark"
        )
        
        # Save
        success = self.storage.save_config(config)
        self.assertTrue(success)
        
        # Load
        loaded = self.storage.load_config()
        
        self.assertEqual(loaded.poll_interval, 15)
        self.assertEqual(loaded.waiting_timeout, 120)
        self.assertEqual(loaded.theme, "dark")
    
    def test_load_corrupted_json_hosts(self):
        """Test loading corrupted hosts JSON."""
        # Write corrupted JSON
        with open("hosts.json", "w") as f:
            f.write("{invalid json")
        
        # Should return empty list
        hosts = self.storage.load_hosts()
        self.assertEqual(hosts, [])
    
    def test_load_corrupted_json_config(self):
        """Test loading corrupted config JSON."""
        # Write corrupted JSON
        with open("config.json", "w") as f:
            f.write("{invalid json")
        
        # Should return default config
        config = self.storage.load_config()
        self.assertIsInstance(config, AppConfig)
    
    def test_load_hosts_with_invalid_entries(self):
        """Test loading hosts with some invalid entries."""
        # Create mix of valid and invalid hosts
        data = [
            {
                "id": "1",
                "name": "Valid1",
                "ip": "192.168.1.1",
                "group": "Group1"
            },
            {
                "id": "2",
                "name": "Invalid",
                "ip": "999.999.999.999",  # Invalid IP
                "group": "Group1"
            },
            {
                "id": "3",
                "name": "Valid2",
                "ip": "192.168.1.2",
                "group": "Group1"
            }
        ]
        
        with open("hosts.json", "w") as f:
            json.dump(data, f)
        
        # Load - validation is lenient, all hosts load
        hosts = self.storage.load_hosts()
        
        self.assertEqual(len(hosts), 3)  # All 3 hosts loaded
    
    def test_migrate_to_db(self):
        """Test migration from JSON to database."""
        TestFixtures.setup_qapp()
        
        # Create JSON file with hosts
        hosts = TestFixtures.create_sample_hosts(3)
        self.storage.save_hosts(hosts)
        
        # Create database
        db_manager = TestFixtures.create_in_memory_db()
        
        # Migrate
        success = self.storage.migrate_to_db(db_manager)
        
        self.assertTrue(success)
        
        # Verify hosts were migrated
        from PyQt5.QtSql import QSqlQuery
        query = QSqlQuery(db_manager.get_db())
        query.exec_("SELECT COUNT(*) FROM hosts")
        query.next()
        count = query.value(0)
        
        self.assertEqual(count, 3)
        
        # Cleanup
        TestFixtures.cleanup_db(db_manager)
    
    def test_migrate_renames_json_file(self):
        """Test that migration renames the JSON file."""
        TestFixtures.setup_qapp()
        
        # Create JSON file
        hosts = TestFixtures.create_sample_hosts(1)
        self.storage.save_hosts(hosts)
        
        self.assertTrue(Path("hosts.json").exists())
        
        # Migrate
        db_manager = TestFixtures.create_in_memory_db()
        self.storage.migrate_to_db(db_manager)
        
        # Original should be renamed
        self.assertFalse(Path("hosts.json").exists())
        self.assertTrue(Path("hosts.json.bak").exists())
        
        # Cleanup
        TestFixtures.cleanup_db(db_manager)
    
    def test_migrate_no_data(self):
        """Test migration when there's no JSON data."""
        TestFixtures.setup_qapp()
        
        db_manager = TestFixtures.create_in_memory_db()
        
        success = self.storage.migrate_to_db(db_manager)
        
        # Should return False (nothing to migrate)
        self.assertFalse(success)
        
        # Cleanup
        TestFixtures.cleanup_db(db_manager)


if __name__ == '__main__':
    unittest.main()
