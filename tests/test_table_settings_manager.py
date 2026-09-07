#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for table_settings_manager.py - TableSettingsManager class
"""

import unittest
import sys
import os
from unittest.mock import Mock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QTableView, QApplication

from tests.conftest import TestFixtures
from table_settings_manager import TableSettingsManager
from table_model import HostTableModel
from models import AppConfig


class TestTableSettingsManager(unittest.TestCase):
    """Tests for TableSettingsManager."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup table and config."""
        # Create table with model
        db_manager, data_manager, repository, hosts = TestFixtures.create_repository_with_data(3)
        self.db_manager = db_manager
        
        self.table_model = HostTableModel(repository)
        self.table = QTableView()
        self.table.setModel(self.table_model)
        
        # Create config and mock storage
        self.config = AppConfig()
        self.storage = Mock()
        
        # Create settings manager
        self.settings_manager = TableSettingsManager(
            self.table,
            self.config,
            self.storage
        )
    
    def tearDown(self):
        """Cleanup."""
        TestFixtures.cleanup_db(self.db_manager)
    
    @unittest.skip("Default column widths vary by Qt version/platform")
    def test_restore_column_widths(self):
        """Test restoring column widths from config."""
        # Set config with specific widths
        self.config.column_widths = {"0": 150, "1": 200, "2": 100}
        
        # Restore settings
        self.settings_manager.restore_settings()
        
        # Check widths were applied
        self.assertEqual(self.table.columnWidth(0), 150)
        self.assertEqual(self.table.columnWidth(1), 200)
        self.assertEqual(self.table.columnWidth(2), 100)
    
    def test_restore_hidden_columns(self):
        """Test restoring hidden columns from config."""
        # Set config with hidden columns
        self.config.hidden_columns = [1, 3]
        
        # Restore settings
        self.settings_manager.restore_settings()
        
        # Check columns are hidden
        self.assertTrue(self.table.isColumnHidden(1))
        self.assertTrue(self.table.isColumnHidden(3))
        self.assertFalse(self.table.isColumnHidden(0))
        self.assertFalse(self.table.isColumnHidden(2))
    
    def test_column_resize_saves_to_config(self):
        """Test that resizing column saves to config."""
        header = self.table.horizontalHeader()
        
        # Simulate column resize
        header.sectionResized.emit(0, 100, 200)
        
        # Check config was updated
        self.assertEqual(self.config.column_widths.get("0"), 200)
        
        # Check storage save was called
        self.storage.save_config.assert_called()
    
    def test_update_hidden_columns(self):
        """Test updating hidden columns list."""
        # Hide some columns
        self.table.setColumnHidden(1, True)
        self.table.setColumnHidden(2, True)
        
        # Update hidden columns
        self.settings_manager.update_hidden_columns()
        
        # Check config was updated
        self.assertIn(1, self.config.hidden_columns)
        self.assertIn(2, self.config.hidden_columns)
        
        # Check storage save was called
        self.storage.save_config.assert_called()
    
    def test_restore_empty_config(self):
        """Test restoring with empty config doesn't crash."""
        # Empty config
        self.config.column_widths = {}
        self.config.hidden_columns = []
        
        # Should not raise exception
        try:
            self.settings_manager.restore_settings()
        except Exception as e:
            self.fail(f"restore_settings() raised exception: {e}")


if __name__ == '__main__':
    unittest.main()
