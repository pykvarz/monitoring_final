#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for subscribers/monitor_subscriber.py - MonitorSubscriber class
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import TestFixtures
from subscribers.monitor_subscriber import MonitorSubscriber
from models import Host


class TestMonitorSubscriber(unittest.TestCase):
    """Tests for MonitorSubscriber."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QCoreApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup repository and monitor thread mock."""
        db_manager, data_manager, repository, hosts = TestFixtures.create_repository_with_data(3)
        self.db_manager = db_manager
        self.repository = repository
        
        # Mock monitor thread
        self.monitor_thread = MagicMock()
        
        # Create subscriber
        self.subscriber = MonitorSubscriber(self.repository, self.monitor_thread)
    
    def tearDown(self):
        """Cleanup."""
        TestFixtures.cleanup_db(self.db_manager)
    
    def test_host_added_interrupts_cycle(self):
        """Test that adding a host interrupts the monitor cycle."""
        new_host = TestFixtures.create_sample_host(name="NewHost")
        
        # Add host (should trigger signal)
        self.repository.add(new_host)
        
        # Should have called interrupt_cycle
        self.monitor_thread.interrupt_cycle.assert_called()
    
    def test_host_deleted_interrupts_cycle(self):
        """Test that deleting a host interrupts the monitor cycle."""
        all_hosts = self.repository.get_all()
        if all_hosts:
            host_to_delete = all_hosts[0]
            
            # Delete host (should trigger signal)
            self.repository.delete(host_to_delete.id)
            
            # Should have called interrupt_cycle
            self.monitor_thread.interrupt_cycle.assert_called()


if __name__ == '__main__':
    unittest.main()
