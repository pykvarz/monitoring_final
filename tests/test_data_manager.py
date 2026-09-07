#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for data_manager.py - DataManager class
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import QCoreApplication

from tests.conftest import TestFixtures
from data_manager import DataManager
from models import Host


class TestDataManager(unittest.TestCase):
    """Tests for DataManager."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QCoreApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup test database and data manager."""
        self.db_manager = TestFixtures.create_in_memory_db()
        self.data_manager = DataManager(self.db_manager)
    
    def tearDown(self):
        """Cleanup database."""
        TestFixtures.cleanup_db(self.db_manager)
    
    def test_add_host_emits_signal(self):
        """Test that adding a host emits host_added signal."""
        host = TestFixtures.create_sample_host()
        
        # Connect signal to mock
        mock_handler = MagicMock()
        self.data_manager.host_added.connect(mock_handler)
        
        # Add host
        self.data_manager.add_host(host)
        
        # Verify signal was emitted
        mock_handler.assert_called_once()
        emitted_host = mock_handler.call_args[0][0]
        self.assertEqual(emitted_host.id, host.id)
    
    def test_delete_host_emits_signal(self):
        """Test that deleting a host emits host_deleted signal."""
        host = TestFixtures.create_sample_host()
        self.data_manager.add_host(host)
        
        # Connect signal to mock
        mock_handler = MagicMock()
        self.data_manager.host_deleted.connect(mock_handler)
        
        # Delete host
        self.data_manager.delete_host(host.id)
        
        # Verify signal was emitted
        mock_handler.assert_called_once()
        self.assertEqual(mock_handler.call_args[0][0], host.id)
    
    def test_update_host_info_emits_signal(self):
        """Test that updating host info emits host_info_updated signal."""
        host = TestFixtures.create_sample_host(name="OldName")
        self.data_manager.add_host(host)
        
        # Connect signal to mock
        mock_handler = MagicMock()
        self.data_manager.host_info_updated.connect(mock_handler)
        
        # Update host
        host.name = "NewName"
        self.data_manager.update_host_info(host)
        
        # Verify signal was emitted
        mock_handler.assert_called_once()
        host_id, old_host, new_host = mock_handler.call_args[0]
        self.assertEqual(host_id, host.id)
        self.assertEqual(old_host.name, "OldName")
        self.assertEqual(new_host.name, "NewName")
    
    def test_batch_add_hosts(self):
        """Test adding multiple hosts in a batch."""
        hosts = TestFixtures.create_sample_hosts(5)
        
        added, errors = self.data_manager.add_hosts(hosts)
        
        self.assertEqual(added, 5)
        self.assertEqual(errors, 0)
        
        # Verify all hosts were added
        all_hosts = self.data_manager.get_all_hosts()
        self.assertEqual(len(all_hosts), 5)
    
    def test_batch_add_with_duplicates(self):
        """Test batch add handles duplicate IDs."""
        host1 = TestFixtures.create_sample_host(id="duplicate-id")
        host2 = TestFixtures.create_sample_host(id="duplicate-id")
        
        added, errors = self.data_manager.add_hosts([host1, host2])
        
        self.assertEqual(added, 1)
        self.assertEqual(errors, 1)
    
    def test_get_all_hosts(self):
        """Test retrieving all hosts."""
        # Add some hosts
        hosts = TestFixtures.create_sample_hosts(3)
        for host in hosts:
            self.data_manager.add_host(host)
        
        # Retrieve all
        retrieved = self.data_manager.get_all_hosts()
        
        self.assertEqual(len(retrieved), 3)
        self.assertIsInstance(retrieved[0], Host)
    
    def test_get_hosts_by_ids(self):
        """Test retrieving specific hosts by ID."""
        hosts = TestFixtures.create_sample_hosts(5)
        for host in hosts:
            self.data_manager.add_host(host)
        
        # Get specific hosts
        ids = [hosts[0].id, hosts[2].id, hosts[4].id]
        retrieved = self.data_manager.get_hosts_by_ids(ids)
        
        self.assertEqual(len(retrieved), 3)
        retrieved_ids = [h.id for h in retrieved]
        for host_id in ids:
            self.assertIn(host_id, retrieved_ids)
    
    def test_update_host_status(self):
        """Test updating host status."""
        host = TestFixtures.create_sample_host(status="ONLINE")
        self.data_manager.add_host(host)
        
        # Update status to OFFLINE
        now = datetime.now(timezone.utc).isoformat()
        self.data_manager.update_host_status(host.id, "OFFLINE", offline_since=now)
        
        # Verify update
        updated = self.data_manager.get_all_hosts()[0]
        self.assertEqual(updated.status, "OFFLINE")
        self.assertIsNotNone(updated.offline_since)
    
    def test_get_stats(self):
        """Test statistics calculation."""
        # Add hosts with different statuses
        hosts = [
            TestFixtures.create_sample_host(name="H1", status="ONLINE"),
            TestFixtures.create_sample_host(name="H2", status="ONLINE"),
            TestFixtures.create_sample_host(name="H3", status="OFFLINE"),
            TestFixtures.create_sample_host(name="H4", status="WAITING"),
            TestFixtures.create_sample_host(name="H5", status="MAINTENANCE"),
        ]
        for host in hosts:
            self.data_manager.add_host(host)
        
        # Get statistics
        stats = self.data_manager.get_stats()
        
        self.assertEqual(stats.get('ONLINE', 0), 2)
        self.assertEqual(stats.get('OFFLINE', 0), 1)
        self.assertEqual(stats.get('WAITING', 0), 1)
        self.assertEqual(stats.get('MAINTENANCE', 0), 1)
    
    def test_hosts_updated_signal_batching(self):
        """Test that hosts_updated signal is batched."""
        mock_handler = MagicMock()
        self.data_manager.hosts_updated.connect(mock_handler)
        
        # Add multiple hosts
        hosts = TestFixtures.create_sample_hosts(3)
        for host in hosts:
            self.data_manager.add_host(host)
        
        # Force flush
        self.data_manager._flush_updates()
        
        # Signal should have been emitted
        self.assertTrue(mock_handler.called)


class TestDataManagerUpdateThrottling(unittest.TestCase):
    """Tests for DataManager update throttling."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QCoreApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup test database and data manager."""
        self.db_manager = TestFixtures.create_in_memory_db()
        self.data_manager = DataManager(self.db_manager)
    
    def tearDown(self):
        """Cleanup database."""
        TestFixtures.cleanup_db(self.db_manager)
    
    def test_trigger_update_immediate(self):
        """Test immediate update trigger."""
        host = TestFixtures.create_sample_host()
        self.data_manager.add_host(host)
        
        mock_handler = MagicMock()
        self.data_manager.hosts_updated.connect(mock_handler)
        
        # Trigger immediate update
        self.data_manager._trigger_update([host.id])
        
        # Should emit signal immediately
        self.assertTrue(mock_handler.called)


if __name__ == '__main__':
    unittest.main()
