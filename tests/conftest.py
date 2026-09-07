#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared test fixtures and utilities for the test suite.
"""

import sys
import os
from datetime import datetime, timezone
from typing import List
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtCore import QCoreApplication

from database import DatabaseManager
from data_manager import DataManager
from core.host_repository import HostRepository
from models import Host, AppConfig
from storage import StorageManager


class TestFixtures:
    """Shared test fixtures and helper methods."""
    
    _app = None
    
    @classmethod
    def setup_qapp(cls):
        """Setup QApplication for tests that need Qt."""
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QCoreApplication
        
        # Check if any QApplication exists
        existing = QCoreApplication.instance()
        if existing is None:
            cls._app = QApplication([])
        return cls._app or existing
    
    @classmethod
    def create_in_memory_db(cls) -> DatabaseManager:
        """Create an in-memory database for testing."""
        # Remove default connection if exists
        if QSqlDatabase.contains("qt_sql_default_connection"):
            QSqlDatabase.removeDatabase("qt_sql_default_connection")
        
        db_manager = DatabaseManager(":memory:")
        return db_manager
    
    @classmethod
    def cleanup_db(cls, db_manager: DatabaseManager):
        """Clean up database connection."""
        if db_manager:
            # Close the database first
            db = db_manager.get_db()
            if db.isOpen():
                db.close()
            
            # Small delay to ensure all queries are finished
            from PyQt5.QtCore import QCoreApplication
            if QCoreApplication.instance():
                QCoreApplication.processEvents()
            
            del db_manager
        
        # Now safe to remove
        if QSqlDatabase.contains("qt_sql_default_connection"):
            db_conn = QSqlDatabase.database("qt_sql_default_connection", open=False)
            if db_conn.isValid():
                db_conn.close()
            QSqlDatabase.removeDatabase("qt_sql_default_connection")
    
    @staticmethod
    def create_sample_host(
        name: str = "TestHost",
        ip: str = "192.168.1.1",
        group: str = "TestGroup",
        status: str = "ONLINE",
        **kwargs
    ) -> Host:
        """Create a sample host for testing."""
        return Host(
            id=kwargs.get('id', str(uuid.uuid4())),
            name=name,
            ip=ip,
            group=group,
            status=status,
            address=kwargs.get('address', ''),
            last_seen=kwargs.get('last_seen', None),
            offline_since=kwargs.get('offline_since', None),
            notifications_enabled=kwargs.get('notifications_enabled', True),
            notified=kwargs.get('notified', False)
        )
    
    @staticmethod
    def create_sample_hosts(count: int = 5) -> List[Host]:
        """Create multiple sample hosts for testing."""
        hosts = []
        for i in range(count):
            host = TestFixtures.create_sample_host(
                name=f"Host{i+1}",
                ip=f"192.168.1.{i+1}",
                group=f"Group{(i % 3) + 1}",
                status=["ONLINE", "OFFLINE", "WAITING", "MAINTENANCE"][i % 4]
            )
            hosts.append(host)
        return hosts
    
    @staticmethod
    def create_sample_config(**kwargs) -> AppConfig:
        """Create a sample AppConfig for testing."""
        return AppConfig(
            poll_interval=kwargs.get('poll_interval', 10),
            waiting_timeout=kwargs.get('waiting_timeout', 60),
            offline_timeout=kwargs.get('offline_timeout', 300),
            notifications_enabled=kwargs.get('notifications_enabled', True),
            sound_enabled=kwargs.get('sound_enabled', False),
            max_workers=kwargs.get('max_workers', 20),
            theme=kwargs.get('theme', 'light')
        )
    
    @staticmethod
    def create_repository_with_data(host_count: int = 5) -> tuple:
        """
        Create a repository with sample data.
        
        Returns:
            tuple: (db_manager, data_manager, repository, hosts)
        """
        TestFixtures.setup_qapp()
        db_manager = TestFixtures.create_in_memory_db()
        data_manager = DataManager(db_manager)
        repository = HostRepository(data_manager)
        
        hosts = TestFixtures.create_sample_hosts(host_count)
        for host in hosts:
            repository.add(host)
        
        return db_manager, data_manager, repository, hosts
