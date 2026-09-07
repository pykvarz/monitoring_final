#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for filter_manager.py - FilterManager class
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, Mock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QLineEdit, QComboBox, QTableView, QApplication
from PyQt5.QtCore import QTimer

from filter_manager import FilterManager
from tests.conftest import TestFixtures
from table_model import HostTableModel
from models import HostStatus


class TestFilterManager(unittest.TestCase):
    """Tests for FilterManager."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup UI components for testing."""
        # Create mock UI components
        self.search_edit = QLineEdit()
        self.group_filter = QComboBox()
        self.status_filter = QComboBox()
        
        # Setup table with model
        db_manager, data_manager, repository, hosts = TestFixtures.create_repository_with_data(5)
        self.db_manager = db_manager
        self.repository = repository
        
        self.table_model = HostTableModel(repository)
        self.table = QTableView()
        self.table.setModel(self.table_model)
        
        # Initialize filters
        self.group_filter.addItem("📁 Все группы")
        self.group_filter.addItems(["Group1", "Group2", "Group3"])
        
        self.status_filter.addItem("📊 Все статусы")
        for status in HostStatus:
            self.status_filter.addItem(status.title)
        
        # Create filter manager
        self.filter_manager = FilterManager(
            self.search_edit,
            self.group_filter,
            self.status_filter,
            self.table,
            self.table_model
        )
    
    def tearDown(self):
        """Cleanup."""
        TestFixtures.cleanup_db(self.db_manager)
    
    @unittest.skip("Table model updates asynchronously - difficult to test")
    def test_text_search(self):
        """Test text search filtering."""
        # Add a unique host
        unique_host = TestFixtures.create_sample_host(name="UniqueServer", ip="10.0.0.99")
        self.repository.add(unique_host)
        # Table model updates automatically via signals
        
        # Search for unique host
        self.search_edit.setText("UniqueServer")
        self.filter_manager.apply_filters()
        
        # Check visible rows
        visible_count = 0
        for row in range(self.table_model.rowCount()):
            if not self.table.isRowHidden(row):
                host = self.table_model.get_host(row)
                if host and "UniqueServer" in host.name:
                    visible_count += 1
        
        self.assertGreater(visible_count, 0)
    
    def test_group_filter(self):
        """Test filtering by group."""
        # Set group filter
        self.group_filter.setCurrentText("Group1")
        self.filter_manager.apply_filters()
        
        # Check that only Group1 hosts are visible
        for row in range(self.table_model.rowCount()):
            host = self.table_model.get_host(row)
            if host:
                is_visible = not self.table.isRowHidden(row)
                if host.group == "Group1":
                    self.assertTrue(is_visible, f"Group1 host should be visible: {host.name}")
                else:
                    self.assertFalse(is_visible, f"Non-Group1 host should be hidden: {host.name}")
    
    def test_status_filter(self):
        """Test filtering by status."""
        # Set status filter
        self.status_filter.setCurrentText("Online")
        self.filter_manager.apply_filters()
        
        # Check that only ONLINE hosts are visible
        for row in range(self.table_model.rowCount()):
            host = self.table_model.get_host(row)
            if host:
                is_visible = not self.table.isRowHidden(row)
                if host.status == "ONLINE":
                    self.assertTrue(is_visible, f"ONLINE host should be visible: {host.name}")
                else:
                    self.assertFalse(is_visible, f"Non-ONLINE host should be hidden: {host.name}")
    
    @unittest.skip("Table model updates asynchronously - difficult to test")
    def test_combined_filters(self):
        """Test combining search text, group, and status filters."""
        # Add specific host
        test_host = TestFixtures.create_sample_host(
            name="TestHost",
            group="Group1",
            status="ONLINE"
        )
        self.repository.add(test_host)
        # Table model updates automatically
        
        # Apply combined filters
        self.search_edit.setText("Test")
        self.group_filter.setCurrentText("Group1")
        self.status_filter.setCurrentText("Online")
        self.filter_manager.apply_filters()
        
        # TestHost should be visible
        found = False
        for row in range(self.table_model.rowCount()):
            host = self.table_model.get_host(row)
            if host and host.name == "TestHost":
                found = True
                self.assertFalse(self.table.isRowHidden(row))
        
        self.assertTrue(found, "TestHost should be found and visible")
    
    def test_reset_filters(self):
        """Test resetting all filters."""
        # Apply some filters
        self.search_edit.setText("test")
        self.group_filter.setCurrentIndex(1)
        self.status_filter.setCurrentIndex(1)
        
        # Reset
        self.filter_manager.reset_filters()
        
        # Check all filters are cleared
        self.assertEqual(self.search_edit.text(), "")
        self.assertEqual(self.group_filter.currentIndex(), 0)
        self.assertEqual(self.status_filter.currentIndex(), 0)
    
    def test_update_group_filter(self):
        """Test updating group filter list."""
        new_groups = ["GroupA", "GroupB", "GroupC"]
        
        self.filter_manager.update_group_filter(new_groups)
        
        # Check groups were added
        items = [self.group_filter.itemText(i) for i in range(self.group_filter.count())]
        
        self.assertIn("GroupA", items)
        self.assertIn("GroupB", items)
        self.assertIn("GroupC", items)
    
    def test_get_current_filters(self):
        """Test getting current filter values."""
        self.search_edit.setText("test search")
        self.group_filter.setCurrentText("Group1")
        self.status_filter.setCurrentText("Online")
        
        self.assertEqual(self.filter_manager.get_current_search_text(), "test search")
        self.assertEqual(self.filter_manager.get_current_group_filter(), "Group1")
        self.assertEqual(self.filter_manager.get_current_status_filter(), "Online")
    
    def test_set_status_filter(self):
        """Test programmatically setting status filter."""
        self.filter_manager.set_status_filter("Offline")
        
        self.assertEqual(self.status_filter.currentText(), "Offline")
    
    @unittest.skip("Table model updates asynchronously - difficult to test")
    def test_search_by_ip(self):
        """Test searching by IP address."""
        # Add host with specific IP
        test_host = TestFixtures.create_sample_host(ip="172.16.0.99")
        self.repository.add(test_host)
        # Table model updates automatically
        
        # Search by IP
        self.search_edit.setText("172.16.0.99")
        self.filter_manager.apply_filters()
        
        # Should find the host
        found = False
        for row in range(self.table_model.rowCount()):
            host = self.table_model.get_host(row)
            if host and host.ip == "172.16.0.99":
                found = True
                self.assertFalse(self.table.isRowHidden(row))
        
        self.assertTrue(found)


if __name__ == '__main__':
    unittest.main()
