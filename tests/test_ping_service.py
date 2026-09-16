
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import subprocess
import platform

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import PingService
import services

class TestPingService(unittest.TestCase):
    
    @patch('services.PingService._win32_ping')
    def test_win32_ping_success(self, mock_win32):
        mock_win32.return_value = True
        
        result = PingService.ping_host("127.0.0.1")
        
        self.assertTrue(result)
        mock_win32.assert_called_once()
    
    @patch('services.PingService._win32_ping')
    def test_win32_ping_host_offline(self, mock_win32):
        # Host is offline: win32 ping returns False (timeout/no reply)
        mock_win32.return_value = False
        
        result = PingService.ping_host("192.168.1.250")
        
        self.assertFalse(result)
        mock_win32.assert_called_once()
    
    @patch('services.PingService._win32_ping')
    @patch('services.PingService._system_ping')
    def test_win32_fallback_to_system_ping(self, mock_system, mock_win32):
        # If win32_ping returns None (e.g. unhandled error or unresolved)
        mock_win32.return_value = None
        mock_system.return_value = True
        
        result = PingService.ping_host("example.com")
        
        self.assertTrue(result)
        mock_win32.assert_called_once()
        mock_system.assert_called_once()
        
    @patch('services.PingService._win32_ping')
    @patch('services.PingService._system_ping')
    def test_both_fail(self, mock_system, mock_win32):
        mock_win32.return_value = None
        mock_system.return_value = False
        
        result = PingService.ping_host("invalid.host")
        
        self.assertFalse(result)

    @patch('services._WIN32_ICMP_AVAILABLE', False)
    @patch('services.PingService._system_ping')
    def test_non_windows_or_no_win32_system_ping(self, mock_system):
        mock_system.return_value = True
        
        result = PingService.ping_host("127.0.0.1")
        
        self.assertTrue(result)
        mock_system.assert_called_once()

    @patch('services._WIN32_ICMP_AVAILABLE', False)
    @patch('subprocess.run')
    def test_system_ping_timeout_passed_to_subprocess(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "TTL=64"
        mock_subprocess.return_value = mock_result

        PingService.ping_host("127.0.0.1", timeout=2.5)

        self.assertTrue(mock_subprocess.called)
        _, kwargs = mock_subprocess.call_args
        self.assertIn('timeout', kwargs, "subprocess.run must be called with an explicit timeout")
        self.assertGreaterEqual(kwargs['timeout'], 2.5)

    @patch('services._WIN32_ICMP_AVAILABLE', False)
    @patch('subprocess.run')
    def test_system_ping_handles_timeout_expired(self, mock_subprocess):
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=['ping'], timeout=3.0)

        result = PingService.ping_host("10.255.255.1", timeout=2.0)
        self.assertFalse(result, "TimeoutExpired must be caught and return False")

    @unittest.skipUnless(platform.system().lower() == 'windows', "Windows only native test")
    def test_real_win32_ping_ipv4_loopback(self):
        """Реальный тест Win32 IcmpSendEcho на 127.0.0.1 без моков"""
        self.assertTrue(PingService._win32_ping("127.0.0.1", timeout=1.0))

    @unittest.skipUnless(platform.system().lower() == 'windows', "Windows only native test")
    def test_real_win32_ping_ipv6_loopback(self):
        """Реальный тест Win32 Icmp6SendEcho2 на ::1 без моков"""
        self.assertTrue(PingService._win32_ping("::1", timeout=1.0))


if __name__ == '__main__':
    unittest.main()
