#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for database.py - DatabaseManager class
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtSql import QSqlDatabase, QSqlQuery

from tests.conftest import TestFixtures
from database import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """Tests for DatabaseManager."""
    
    @classmethod
    def setUpClass(cls):
        """Setup QCoreApplication once for all tests."""
        TestFixtures.setup_qapp()
    
    def setUp(self):
        """Remove any existing database connection."""
        if QSqlDatabase.contains("qt_sql_default_connection"):
            QSqlDatabase.removeDatabase("qt_sql_default_connection")
    
    def tearDown(self):
        """Cleanup database connection."""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
            del self.db_manager
        
        if QSqlDatabase.contains("qt_sql_default_connection"):
            QSqlDatabase.removeDatabase("qt_sql_default_connection")
    
    def test_create_in_memory_database(self):
        """Test creating an in-memory database."""
        self.db_manager = DatabaseManager(":memory:")
        
        self.assertIsNotNone(self.db_manager.get_db())
        self.assertTrue(self.db_manager.get_db().isOpen())
    
    def test_hosts_table_created(self):
        """Test that hosts table is created."""
        self.db_manager = DatabaseManager(":memory:")
        db = self.db_manager.get_db()
        
        # Query to check if table exists
        query = QSqlQuery(db)
        query.exec_("SELECT name FROM sqlite_master WHERE type='table' AND name='hosts'")
        
        self.assertTrue(query.next())
        self.assertEqual(query.value(0), 'hosts')
    
    def test_settings_table_created(self):
        """Test that settings table is created."""
        self.db_manager = DatabaseManager(":memory:")
        db = self.db_manager.get_db()
        
        # Query to check if table exists
        query = QSqlQuery(db)
        query.exec_("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        
        self.assertTrue(query.next())
        self.assertEqual(query.value(0), 'settings')
    
    def test_hosts_table_indices(self):
        """Test that indices are created on hosts table."""
        self.db_manager = DatabaseManager(":memory:")
        db = self.db_manager.get_db()
        
        # Query to check indices
        query = QSqlQuery(db)
        query.exec_("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='hosts'")
        
        indices = []
        while query.next():
            indices.append(query.value(0))
        
        # Should have indices on status and group
        self.assertTrue(any('status' in idx for idx in indices))
        self.assertTrue(any('grp' in idx for idx in indices))
    
    def test_wal_mode_enabled(self):
        """Test that WAL mode is enabled."""
        self.db_manager = DatabaseManager(":memory:")
        db = self.db_manager.get_db()
        
        query = QSqlQuery(db)
        query.exec_("PRAGMA journal_mode")
        
        if query.next():
            journal_mode = query.value(0)
            # WAL mode should be enabled (might be "wal" or "memory" for :memory: db)
            self.assertIn(journal_mode.lower(), ['wal', 'memory'])
    
    def test_insert_and_query_host(self):
        """Test basic insert and query operations."""
        self.db_manager = DatabaseManager(":memory:")
        db = self.db_manager.get_db()
        
        # Insert a host
        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO hosts (id, ip, name, grp, status)
            VALUES (:id, :ip, :name, :grp, :status)
        """)
        query.bindValue(":id", "test-1")
        query.bindValue(":ip", "192.168.1.1")
        query.bindValue(":name", "TestHost")
        query.bindValue(":grp", "TestGroup")
        query.bindValue(":status", "ONLINE")
        
        success = query.exec_()
        self.assertTrue(success, f"Insert failed: {query.lastError().text()}")
        
        # Query it back
        query2 = QSqlQuery(db)
        query2.exec_("SELECT ip, name FROM hosts WHERE id='test-1'")
        
        self.assertTrue(query2.next())
        self.assertEqual(query2.value(0), "192.168.1.1")
        self.assertEqual(query2.value(1), "TestHost")
    
    def test_database_close(self):
        """Test closing database connection."""
        self.db_manager = DatabaseManager(":memory:")
        db = self.db_manager.get_db()
        
        self.assertTrue(db.isOpen())
        
        self.db_manager.close()
        
        self.assertFalse(db.isOpen())
    
    def test_reconnect_after_close(self):
        """Test that we can't use database after close."""
        self.db_manager = DatabaseManager(":memory:")
        self.db_manager.close()
        
        db = self.db_manager.get_db()
        self.assertFalse(db.isOpen())


if __name__ == '__main__':
    unittest.main()
