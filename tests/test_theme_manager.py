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
        self.repository = repository
        
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
    

    
    @patch('theme_manager.set_dark_titlebar')
    def test_apply_initial_theme(self, mock_titlebar):
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
    
    @patch('theme_manager.set_dark_titlebar')
    def test_theme_change(self, mock_titlebar):
        """Test that theme can be changed via _apply_theme."""
        self.config.theme = "light"
        
        # Apply dark theme
        self.theme_manager._apply_theme("dark")
        
        # Apply light theme
        self.theme_manager._apply_theme("light")
        
        # set_dark_titlebar should have been called for each apply
        self.assertEqual(mock_titlebar.call_count, 2)


if __name__ == '__main__':
    unittest.main()
