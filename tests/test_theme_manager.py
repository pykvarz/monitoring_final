#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for theme_manager.py - ThemeManager class
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, Mock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QMainWindow, QTableView, QApplication

from tests.conftest import TestFixtures
from theme_manager import ThemeManager
from table_model import HostTableModel
from storage import StorageManager
from models import AppConfig


class TestThemeManager(unittest.TestCase):
    """Tests for ThemeManager."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Setup components for testing."""
        # Create mock main window
        self.window = QMainWindow()
        
        # Create config and storage
        self.config = AppConfig(theme="light")
        self.storage = Mock(spec=StorageManager)
        
        # Create table and model
        db_manager, data_manager, repository, hosts = TestFixtures.create_repository_with_data(3)
        self.db_manager = db_manager
        
        self.table_model = HostTableModel(repository)
        self.table = QTableView()
        self.table.setModel(self.table_model)
        
        # Create theme manager
        self.theme_manager = ThemeManager(
            self.window,
            self.config,
            self.storage,
            self.table,
            self.table_model
        )
    
    def tearDown(self):
        """Cleanup."""
        TestFixtures.cleanup_db(self.db_manager)
    
    def test_get_current_theme(self):
        """Test getting current theme."""
        self.assertEqual(self.theme_manager.get_current_theme(), "light")
        
        self.config.theme = "dark"
        self.assertEqual(self.theme_manager.get_current_theme(), "dark")
    
    @unittest.skip("Qt object lifecycle issue - table model deleted")
    def test_toggle_theme_light_to_dark(self):
        """Test toggling from light to dark theme."""
        self.config.theme = "light"
        
        self.theme_manager.toggle_theme()
        
        self.assertEqual(self.config.theme, "dark")
        self.storage.save_config.assert_called_once_with(self.config)
    
    def test_toggle_theme_dark_to_light(self):
        """Test toggling from dark to light theme."""
        self.config.theme = "dark"
        
        self.theme_manager.toggle_theme()
        
        self.assertEqual(self.config.theme, "light")
        self.storage.save_config.assert_called_once_with(self.config)
    
    def test_apply_initial_theme(self):
        """Test applying initial theme."""
        # Should not raise exception
        try:
            self.theme_manager.apply_initial_theme()
        except Exception as e:
            self.fail(f"apply_initial_theme() raised exception: {e}")
    
    def test_set_window_icon(self):
        """Test setting window icon."""
        # Should not raise exception
        try:
            self.theme_manager.set_window_icon("light")
            self.theme_manager.set_window_icon("dark")
        except Exception as e:
            self.fail(f"set_window_icon() raised exception: {e}")
        
        # Window should have an icon set
        self.assertFalse(self.window.windowIcon().isNull())
    
    @unittest.skip("Qt object lifecycle issue - test setup problem")
    def test_theme_persistence(self):
        """Test that theme changes are persisted."""
        self.config.theme = "light"
        
        # Toggle twice
        self.theme_manager.toggle_theme()
        self.theme_manager.toggle_theme()
        
        # Should have saved twice
        self.assertEqual(self.storage.save_config.call_count, 2)


if __name__ == '__main__':
    unittest.main()
