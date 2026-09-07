#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for services.py - NotificationService class
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import NotificationService
from models import AppConfig


class TestNotificationService(unittest.TestCase):
    """Tests for NotificationService."""
    
    @patch('services.notification')
    @patch('services.QApplication.beep')
    def test_notify_single_host(self, mock_beep, mock_notification):
        """Test notification for a single offline host."""
        config = AppConfig(notifications_enabled=True, sound_enabled=True)
        hosts = ["Server1"]
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should call beep
        mock_beep.assert_called_once()
        
        # Should call notification with single host title
        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]
        self.assertIn("Узел недоступен", call_args['title'])
        self.assertEqual(call_args['message'], "Server1")
    
    @patch('services.notification')
    @patch('services.QApplication.beep')
    def test_notify_multiple_hosts(self, mock_beep, mock_notification):
        """Test notification for multiple offline hosts."""
        config = AppConfig(notifications_enabled=True, sound_enabled=False)
        hosts = ["Server1", "Server2", "Server3"]
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should NOT call beep (sound disabled)
        mock_beep.assert_not_called()
        
        # Should call notification with grouped message
        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]
        self.assertEqual(call_args['message'], "Server1\nServer2\nServer3")
    
    @patch('services.notification')
    def test_notify_many_hosts_grouped(self, mock_notification):
        """Test notification for many hosts (>3) shows count."""
        config = AppConfig(notifications_enabled=True)
        hosts = [f"Server{i}" for i in range(10)]
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should show count instead of list
        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]
        self.assertIn("Несколько узлов", call_args['title'])
        self.assertIn("10", call_args['message'])
    
    @patch('services.notification')
    def test_no_notification_when_disabled(self, mock_notification):
        """Test that notifications are not sent when disabled."""
        config = AppConfig(notifications_enabled=False)
        hosts = ["Server1"]
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should NOT call notification
        mock_notification.notify.assert_not_called()
    
    @patch('services.notification')
    def test_no_notification_when_no_hosts(self, mock_notification):
        """Test that no notification is sent for empty host list."""
        config = AppConfig(notifications_enabled=True)
        hosts = []
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should NOT call notification
        mock_notification.notify.assert_not_called()
    
    @patch('services.notification', None)
    def test_graceful_handling_when_library_missing(self):
        """Test graceful handling when notification library is not available."""
        config = AppConfig(notifications_enabled=True)
        hosts = ["Server1"]
        
        # Should not raise exception
        try:
            NotificationService.notify_offline_hosts(hosts, config)
        except Exception as e:
            self.fail(f"Should not raise exception: {e}")
    
    @patch('services.notification')
    def test_show_notification(self, mock_notification):
        """Test show_notification method."""
        NotificationService.show_notification("Test Title", "Test Message")
        
        mock_notification.notify.assert_called_once_with(
            title="Test Title",
            message="Test Message",
            app_name="Network Monitor",
            timeout=5
        )
    
    @patch('services.notification', None)
    def test_show_notification_library_missing(self):
        """Test show_notification when library is missing."""
        # Should not raise exception
        try:
            NotificationService.show_notification("Title", "Message")
        except Exception as e:
            self.fail(f"Should not raise exception: {e}")
    
    @patch('services.notification')
    def test_notification_error_handling(self, mock_notification):
        """Test that notification errors are handled gracefully."""
        config = AppConfig(notifications_enabled=True)
        hosts = ["Server1"]
        
        # Simulate notification error
        mock_notification.notify.side_effect = OSError("Notification failed")
        
        # Should not raise exception
        try:
            NotificationService.notify_offline_hosts(hosts, config)
        except Exception as e:
            self.fail(f"Should handle error gracefully: {e}")


if __name__ == '__main__':
    unittest.main()
