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
    
    @patch.object(NotificationService, '_get_tray_icon')
    @patch('services.QApplication.beep')
    def test_notify_single_host(self, mock_beep, mock_get_tray):
        """Test notification for a single offline host."""
        mock_tray = MagicMock()
        mock_get_tray.return_value = mock_tray

        config = AppConfig(notifications_enabled=True, sound_enabled=True)
        hosts = ["Server1"]
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should call beep
        mock_beep.assert_called_once()
        
        # Should call showMessage with single host title
        mock_tray.showMessage.assert_called_once()
        call_args = mock_tray.showMessage.call_args[0]
        self.assertIn("Узел недоступен", call_args[0])
        self.assertEqual(call_args[1], "Server1")
    
    @patch.object(NotificationService, '_get_tray_icon')
    @patch('services.QApplication.beep')
    def test_notify_multiple_hosts(self, mock_beep, mock_get_tray):
        """Test notification for multiple offline hosts."""
        mock_tray = MagicMock()
        mock_get_tray.return_value = mock_tray

        config = AppConfig(notifications_enabled=True, sound_enabled=False)
        hosts = ["Server1", "Server2", "Server3"]
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should NOT call beep (sound disabled)
        mock_beep.assert_not_called()
        
        # Should call notification with grouped message
        mock_tray.showMessage.assert_called_once()
        call_args = mock_tray.showMessage.call_args[0]
        self.assertEqual(call_args[1], "Server1\nServer2\nServer3")
    
    @patch.object(NotificationService, '_get_tray_icon')
    def test_notify_many_hosts_grouped(self, mock_get_tray):
        """Test notification for many hosts (>3) shows count."""
        mock_tray = MagicMock()
        mock_get_tray.return_value = mock_tray

        config = AppConfig(notifications_enabled=True)
        hosts = [f"Server{i}" for i in range(10)]
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should show count instead of list
        mock_tray.showMessage.assert_called_once()
        call_args = mock_tray.showMessage.call_args[0]
        self.assertIn("Несколько узлов", call_args[0])
        self.assertIn("10", call_args[1])
    
    @patch.object(NotificationService, '_get_tray_icon')
    def test_no_notification_when_disabled(self, mock_get_tray):
        """Test that notifications are not sent when disabled."""
        mock_tray = MagicMock()
        mock_get_tray.return_value = mock_tray

        config = AppConfig(notifications_enabled=False)
        hosts = ["Server1"]
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should NOT call notification
        mock_tray.showMessage.assert_not_called()
    
    @patch.object(NotificationService, '_get_tray_icon')
    def test_no_notification_when_no_hosts(self, mock_get_tray):
        """Test that no notification is sent for empty host list."""
        mock_tray = MagicMock()
        mock_get_tray.return_value = mock_tray

        config = AppConfig(notifications_enabled=True)
        hosts = []
        
        NotificationService.notify_offline_hosts(hosts, config)
        
        # Should NOT call notification
        mock_tray.showMessage.assert_not_called()
    
    @patch.object(NotificationService, '_get_tray_icon', return_value=None)
    def test_graceful_handling_when_tray_unavailable(self, mock_get_tray):
        """Test graceful handling when system tray is not available."""
        config = AppConfig(notifications_enabled=True)
        hosts = ["Server1"]
        
        # Should not raise exception
        try:
            NotificationService.notify_offline_hosts(hosts, config)
        except Exception as e:
            self.fail(f"Should not raise exception: {e}")
    
    @patch.object(NotificationService, '_get_tray_icon')
    def test_show_notification(self, mock_get_tray):
        """Test show_notification method."""
        mock_tray = MagicMock()
        mock_get_tray.return_value = mock_tray

        NotificationService.show_notification("Test Title", "Test Message")
        
        mock_tray.showMessage.assert_called_once()
        args = mock_tray.showMessage.call_args[0]
        self.assertEqual(args[0], "Test Title")
        self.assertEqual(args[1], "Test Message")
    
    @patch.object(NotificationService, '_get_tray_icon', return_value=None)
    def test_show_notification_tray_unavailable(self, mock_get_tray):
        """Test show_notification when tray is unavailable."""
        try:
            NotificationService.show_notification("Title", "Message")
        except Exception as e:
            self.fail(f"Should not raise exception: {e}")
    
    @patch.object(NotificationService, '_get_tray_icon')
    def test_notification_error_handling(self, mock_get_tray):
        """Test that notification errors are handled gracefully."""
        mock_tray = MagicMock()
        mock_tray.showMessage.side_effect = RuntimeError("Tray error")
        mock_get_tray.return_value = mock_tray

        config = AppConfig(notifications_enabled=True)
        hosts = ["Server1"]
        
        # Should not raise exception
        try:
            NotificationService.notify_offline_hosts(hosts, config)
        except Exception as e:
            self.fail(f"Should handle error gracefully: {e}")

    @patch.object(NotificationService, '_get_tray_icon')
    @patch('services.QApplication.beep')
    def test_notify_offline_hosts_show_tray_false(self, mock_beep, mock_get_tray):
        """Test notify_offline_hosts does not call tray.showMessage when show_tray is False, but still beeps if sound is enabled."""
        mock_tray = MagicMock()
        mock_get_tray.return_value = mock_tray

        config = AppConfig(notifications_enabled=True, sound_enabled=True)
        hosts = ["Server1"]

        NotificationService.notify_offline_hosts(hosts, config, show_tray=False)

        mock_beep.assert_called_once()
        mock_tray.showMessage.assert_not_called()

    @patch.object(NotificationService, '_get_tray_icon')
    def test_notify_recovered_hosts_show_tray_false(self, mock_get_tray):
        """Test notify_recovered_hosts does not call tray.showMessage when show_tray is False."""
        mock_tray = MagicMock()
        mock_get_tray.return_value = mock_tray

        config = AppConfig(notifications_enabled=True, sound_enabled=False)
        hosts = ["Server1"]

        NotificationService.notify_recovered_hosts(hosts, config, show_tray=False)

        mock_tray.showMessage.assert_not_called()


if __name__ == '__main__':
    unittest.main()

