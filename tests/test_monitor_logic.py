
import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor_thread import MonitorThread
from models import Host, AppConfig

class TestMonitorLogic(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.offline_timeout = 30 # seconds
        self.mock_config.waiting_timeout = 5 # seconds
        self.mock_config.poll_interval = 2
        self.mock_config.max_workers = 5
        
        self.thread = MonitorThread(self.mock_repo, self.mock_config)

    def test_online_remains_online(self):
        # Case 1: Just updated (Fresh) -> No DB Write
        now = datetime.now(timezone.utc)
        host = Host(id="1", ip="127.0.0.1", name="Local", status="ONLINE", last_seen=now.isoformat())
        ping_status = "ONLINE"
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "ONLINE")
        self.assertFalse(update) # Should trigger throttling (0 seconds diff)

    def test_online_throttling_expired(self):
        # Case 2: Old update -> DB Write
        old_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        host = Host(id="1", ip="127.0.0.1", name="Local", status="ONLINE", last_seen=old_time.isoformat())
        ping_status = "ONLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "ONLINE")
        self.assertTrue(update) # Threshold exceeded, should update

    def test_initial_failure_remains_online(self):
        # Initial failure leaves status as ONLINE but sets offline_since
        host = Host(id="1", ip="127.0.0.1", name="Local", status="ONLINE")
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "ONLINE")
        self.assertIsNotNone(offline_since)
        self.assertTrue(update)

    def test_waiting_logic(self):
        # 10 seconds later (Waiting phase)
        start_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        host = Host(id="1", ip="127.0.0.1", name="Local", status="ONLINE", offline_since=start_time.isoformat())
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "WAITING")
        self.assertTrue(update)

    def test_waiting_to_offline(self):
        # 40 seconds later (Offline phase)
        start_time = datetime.now(timezone.utc) - timedelta(seconds=40)
        # Note: Previous status could be WAITING or ONLINE depending on checks
        host = Host(id="1", ip="127.0.0.1", name="Local", status="WAITING", offline_since=start_time.isoformat())
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "OFFLINE")
        self.assertTrue(update)

    def test_offline_remains_offline(self):
        start_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        host = Host(id="1", ip="127.0.0.1", name="Local", status="OFFLINE", offline_since=start_time.isoformat())
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "OFFLINE")
        
    def test_offline_to_online(self):
        host = Host(id="1", ip="127.0.0.1", name="Local", status="OFFLINE", offline_since="some_date")
        ping_status = "ONLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "ONLINE")
        self.assertIsNone(offline_since)
        self.assertTrue(update)

    def test_maintenance_ignores_offline(self):
        host = Host(id="1", ip="127.0.0.1", name="Local", status="MAINTENANCE")
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        self.assertEqual(new_status, "MAINTENANCE")
        self.assertFalse(update)
        
    def test_continuous_outage_transitions_to_waiting_and_offline(self):
        """Проверка непрерывного сбоя: ONLINE -> WAITING (через waiting_timeout) -> OFFLINE (через offline_timeout)"""
        host = Host(id="h_cont", ip="192.168.1.50", name="Server-X", status="ONLINE")
        t0 = datetime.now(timezone.utc)
        
        # Цикл 1: первый сбой (T=0)
        st1, os1, up1 = self.thread._calculate_status(host, "OFFLINE", t0)
        self.assertEqual(st1, "ONLINE")
        self.assertIsNotNone(os1)
        self.assertTrue(up1)
        host.offline_since = os1
        
        # Имитируем поведение run(): статус в кеше потока
        self.thread._known_statuses[host.id] = st1
        self.thread._offline_since_cache[host.id] = os1
        
        # Цикл 2: сбой продолжается спустя 65 сек (> waiting_timeout 5с в тесте)
        t_wait = t0 + timedelta(seconds=10)
        st2, os2, up2 = self.thread._calculate_status(host, "OFFLINE", t_wait)
        self.assertEqual(st2, "WAITING")
        self.assertEqual(os2, os1, "offline_since не должен сбрасываться!")
        self.assertTrue(up2)
        host.status = st2
        self.thread._known_statuses[host.id] = st2
        
        # Цикл 3: сбой продолжается спустя 35 сек (> offline_timeout 30с в тесте)
        t_off = t0 + timedelta(seconds=35)
        st3, os3, up3 = self.thread._calculate_status(host, "OFFLINE", t_off)
        self.assertEqual(st3, "OFFLINE")
        self.assertEqual(os3, os1, "offline_since должен сохранять исходное время начала сбоя!")
        self.assertTrue(up3)

if __name__ == '__main__':
    unittest.main()
