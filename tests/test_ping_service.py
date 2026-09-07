
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import subprocess

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import PingService

class TestPingService(unittest.TestCase):
    
    @patch('services.ping')
    def test_ping3_success(self, mock_ping):
        # Setup mock to return float (success)
        mock_ping.return_value = 0.123
        
        result = PingService.ping_host("127.0.0.1")
        
        self.assertTrue(result)
        mock_ping.assert_called_once()
    
    @patch('services.ping')
    @patch('subprocess.check_call')
    def test_ping3_failure_fallback_success(self, mock_subprocess, mock_ping):
        # ping3 return None (timeout)
        mock_ping.return_value = None 
        
        # subprocess checks call. Returns 0 (success) implicitly if no exception.
        mock_subprocess.return_value = 0
        
        result = PingService.ping_host("127.0.0.1")
        
        self.assertTrue(result)
        mock_ping.assert_called_once()
        mock_subprocess.assert_called_once()
        
    @patch('services.ping')
    @patch('subprocess.check_call')
    def test_ping3_exception_fallback_success(self, mock_subprocess, mock_ping):
        # ping3 raises PermissionError
        mock_ping.side_effect = PermissionError("Access denied")
        
        mock_subprocess.return_value = 0
        
        result = PingService.ping_host("127.0.0.1")
        
        self.assertTrue(result)
        mock_subprocess.assert_called_once()

    @patch('services.ping')
    @patch('subprocess.check_call')
    def test_both_fail(self, mock_subprocess, mock_ping):
        mock_ping.return_value = None
        
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "ping")
        
        result = PingService.ping_host("127.0.0.1")
        
        self.assertFalse(result)
        
    @patch('services.ping', None) 
    @patch('subprocess.check_call')
    def test_no_ping3_library(self, mock_subprocess):
        # If ping3 is not available (None)
        # It should go straight to system ping
        
        mock_subprocess.return_value = 0
        
        result = PingService.ping_host("127.0.0.1")
        
        self.assertTrue(result)
        mock_subprocess.assert_called_once()

if __name__ == '__main__':
    unittest.main()
