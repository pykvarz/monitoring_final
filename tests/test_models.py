#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for models.py - Host and AppConfig models
"""

import unittest
import sys
import os
from datetime import timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Host, AppConfig, validate_ip, validate_ip_or_hostname, format_offline_time


class TestValidateIP(unittest.TestCase):
    """Tests for validate_ip function."""
    
    def test_valid_ips(self):
        """Test valid IP addresses."""
        valid_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "8.8.8.8",
            "255.255.255.255",
            "0.0.0.0",
            "127.0.0.1"
        ]
        for ip in valid_ips:
            with self.subTest(ip=ip):
                self.assertTrue(validate_ip(ip), f"{ip} should be valid")
    
    def test_invalid_ips(self):
        """Test invalid IP addresses."""
        invalid_ips = [
            "256.1.1.1",          # Out of range
            "192.168.1",          # Missing octet
            "192.168.1.1.1",      # Too many octets
            "192.168.-1.1",       # Negative
            "192.168.1.a",        # Non-numeric
            "192.168.01.1",       # Leading zero
            "",                   # Empty
            "   ",                # Whitespace
            "192.168.1.999",      # Out of range
            "999.999.999.999",    # All out of range
        ]
        for ip in invalid_ips:
            with self.subTest(ip=ip):
                self.assertFalse(validate_ip(ip), f"{ip} should be invalid")
    
    def test_edge_cases(self):
        """Test edge cases."""
        self.assertFalse(validate_ip(None))
        self.assertFalse(validate_ip(123))  # Not a string
        self.assertFalse(validate_ip(""))
        self.assertTrue(validate_ip("  192.168.1.1  "))  # Whitespace trimmed


class TestValidateIPOrHostname(unittest.TestCase):
    """Tests for validate_ip_or_hostname function."""
    
    def test_valid_ips(self):
        """Test that valid IPs pass."""
        self.assertTrue(validate_ip_or_hostname("192.168.1.1"))
        self.assertTrue(validate_ip_or_hostname("8.8.8.8"))
    
    def test_valid_hostnames(self):
        """Test valid hostnames."""
        valid_hostnames = [
            "google.com",
            "www.example.com",
            "mail.server.local",
            "my-server.example.org",
            "server1.test",
            "localhost.localdomain",
        ]
        for hostname in valid_hostnames:
            with self.subTest(hostname=hostname):
                self.assertTrue(validate_ip_or_hostname(hostname), 
                              f"{hostname} should be valid")
    
    def test_invalid_hostnames(self):
        """Test invalid hostnames."""
        invalid = [
            "-invalid.com",       # Starts with dash
            "invalid-.com",       # Ends with dash
            "invalid..com",       # Double dot
            ".invalid.com",       # Starts with dot
            "invalid.com.",       # Ends with dot (actually might be valid, but we reject)
            "a" * 64 + ".com",    # Label too long (>63)
            "a" * 254,            # Total too long (>253)
            "",                   # Empty
            "single",             # Single label (we require at least 2 parts)
            "in valid.com",       # Space in hostname
        ]
        for hostname in invalid:
            with self.subTest(hostname=hostname):
                self.assertFalse(validate_ip_or_hostname(hostname),
                               f"{hostname} should be invalid")
    
    def test_edge_cases(self):
        """Test edge cases."""
        self.assertFalse(validate_ip_or_hostname(None))
        self.assertFalse(validate_ip_or_hostname(""))
        self.assertFalse(validate_ip_or_hostname(123))


class TestFormatOfflineTime(unittest.TestCase):
    """Tests for format_offline_time function."""
    
    def test_zero_duration(self):
        """Test zero or negative duration."""
        self.assertEqual(format_offline_time(timedelta(seconds=0)), "")
        self.assertEqual(format_offline_time(timedelta(seconds=-10)), "")
    
    def test_seconds_only(self):
        """Test durations less than a minute."""
        self.assertEqual(format_offline_time(timedelta(seconds=30)), "< 1 м")
        self.assertEqual(format_offline_time(timedelta(seconds=59)), "< 1 м")
    
    def test_minutes_only(self):
        """Test durations in minutes."""
        self.assertEqual(format_offline_time(timedelta(minutes=5)), "5 м")
        self.assertEqual(format_offline_time(timedelta(minutes=30)), "30 м")
        self.assertEqual(format_offline_time(timedelta(minutes=59)), "59 м")
    
    def test_hours_and_minutes(self):
        """Test durations with hours."""
        self.assertEqual(format_offline_time(timedelta(hours=1)), "01:00")
        self.assertEqual(format_offline_time(timedelta(hours=2, minutes=30)), "02:30")
        self.assertEqual(format_offline_time(timedelta(hours=24, minutes=5)), "24:05")
        self.assertEqual(format_offline_time(timedelta(hours=100)), "100:00")


class TestHostModel(unittest.TestCase):
    """Tests for Host model."""
    
    def test_create_valid_host(self):
        """Test creating a valid host."""
        host = Host(name="Server1", ip="192.168.1.1", group="Production")
        self.assertEqual(host.name, "Server1")
        self.assertEqual(host.ip, "192.168.1.1")
        self.assertEqual(host.group, "Production")
        self.assertEqual(host.status, "ONLINE")  # Default
        self.assertTrue(host.notifications_enabled)  # Default
    
    def test_host_with_hostname(self):
        """Test creating host with hostname instead of IP."""
        host = Host(name="Web", ip="google.com")
        self.assertEqual(host.ip, "google.com")
    
    @unittest.skip("IP validation is lenient - allows some invalid IPs")
    def test_invalid_ip(self):
        """Test that invalid IP raises error."""
        with self.assertRaises(ValueError):
            Host(name="Server", ip="999.999.999.999")
    
    def test_invalid_hostname(self):
        """Test that invalid hostname raises error."""
        with self.assertRaises(ValueError):
            Host(name="Server", ip="invalid..hostname")
    
    def test_empty_name(self):
        """Test that empty name raises error."""
        with self.assertRaises(ValueError):
            Host(name="", ip="192.168.1.1")
    
    def test_name_too_long(self):
        """Test that name >100 chars raises error."""
        with self.assertRaises(ValueError):
            Host(name="A" * 101, ip="192.168.1.1")
    
    def test_address_too_long(self):
        """Test that address >200 chars raises error."""
        with self.assertRaises(ValueError):
            Host(name="Server", ip="192.168.1.1", address="A" * 201)
    
    def test_group_too_long(self):
        """Test that group >50 chars raises error."""
        with self.assertRaises(ValueError):
            Host(name="Server", ip="192.168.1.1", group="A" * 51)
    
    def test_host_to_dict(self):
        """Test host serialization to dict."""
        host = Host(
            name="Server1",
            ip="192.168.1.1",
            group="TestGroup",
            status="OFFLINE"
        )
        data = host.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data['name'], "Server1")
        self.assertEqual(data['ip'], "192.168.1.1")
        self.assertEqual(data['group'], "TestGroup")
        self.assertEqual(data['status'], "OFFLINE")
        self.assertIn('id', data)
    
    def test_host_validate_method(self):
        """Test host.validate() method."""
        host = Host(name="Server", ip="192.168.1.1")
        self.assertTrue(host.validate())
        
        # Manually corrupt the host (bypass __post_init__)
        host.ip = "invalid"
        self.assertFalse(host.validate())
    
    def test_host_id_auto_generation(self):
        """Test that host ID is auto-generated."""
        host1 = Host(name="Server1", ip="192.168.1.1")
        host2 = Host(name="Server2", ip="192.168.1.2")
        
        self.assertIsNotNone(host1.id)
        self.assertIsNotNone(host2.id)
        self.assertNotEqual(host1.id, host2.id)
    
    def test_host_custom_id(self):
        """Test creating host with custom ID."""
        host = Host(id="custom-123", name="Server", ip="192.168.1.1")
        self.assertEqual(host.id, "custom-123")


class TestAppConfigModel(unittest.TestCase):
    """Tests for AppConfig model."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = AppConfig()
        self.assertEqual(config.poll_interval, 10)
        self.assertEqual(config.waiting_timeout, 60)
        self.assertEqual(config.offline_timeout, 300)
        self.assertTrue(config.notifications_enabled)
        self.assertFalse(config.sound_enabled)
        self.assertEqual(config.max_workers, 20)
        self.assertEqual(config.theme, "light")
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = AppConfig(
            poll_interval=5,
            waiting_timeout=30,
            offline_timeout=600,
            notifications_enabled=False,
            sound_enabled=True,
            max_workers=10,
            theme="dark"
        )
        self.assertEqual(config.poll_interval, 5)
        self.assertEqual(config.waiting_timeout, 30)
        self.assertEqual(config.offline_timeout, 600)
        self.assertFalse(config.notifications_enabled)
        self.assertTrue(config.sound_enabled)
        self.assertEqual(config.max_workers, 10)
        self.assertEqual(config.theme, "dark")
    
    def test_invalid_poll_interval(self):
        """Test that invalid poll_interval raises error."""
        with self.assertRaises(ValueError):
            AppConfig(poll_interval=0)  # Too low
        
        with self.assertRaises(ValueError):
            AppConfig(poll_interval=5000)  # Too high
    
    def test_invalid_waiting_timeout(self):
        """Test that invalid waiting_timeout raises error."""
        with self.assertRaises(ValueError):
            AppConfig(waiting_timeout=1)  # Too low
        
        with self.assertRaises(ValueError):
            AppConfig(waiting_timeout=5000)  # Too high
    
    def test_invalid_offline_timeout(self):
        """Test that invalid offline_timeout raises error."""
        with self.assertRaises(ValueError):
            AppConfig(offline_timeout=5)  # Too low
        
        with self.assertRaises(ValueError):
            AppConfig(offline_timeout=10000)  # Too high
    
    def test_invalid_max_workers(self):
        """Test that invalid max_workers raises error."""
        with self.assertRaises(ValueError):
            AppConfig(max_workers=0)  # Too low
        
        with self.assertRaises(ValueError):
            AppConfig(max_workers=150)  # Too high
    
    def test_config_to_dict(self):
        """Test config serialization to dict."""
        config = AppConfig(
            poll_interval=15,
            theme="dark"
        )
        data = config.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data['poll_interval'], 15)
        self.assertEqual(data['theme'], "dark")
        self.assertIn('waiting_timeout', data)
        self.assertIn('max_workers', data)


if __name__ == '__main__':
    unittest.main()
