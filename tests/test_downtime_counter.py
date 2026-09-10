#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты корректности сброса и расчета счетчика времени простоя (offline_since).
Проверяют сценарии:
- Узел упал на час, восстановился, затем упал снова — время простоя должно начинаться с 0,
  а не накапливать предыдущий час.
- Временная потеря пакетов в статусе ONLINE не должна оставлять устаревший offline_since.
- При переходе в ONLINE offline_since в БД и моделях гарантированно обнуляется.
"""

import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from PyQt5.QtWidgets import QApplication

from monitor_thread import MonitorThread
from models import Host, AppConfig


class TestDowntimeCounterReset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.mock_repo = MagicMock()
        self.config = AppConfig(offline_timeout=30, waiting_timeout=5, poll_interval=2)
        self.thread = MonitorThread(self.mock_repo, self.config)

    def test_downtime_resets_after_recovery_and_second_outage(self):
        """
        Главный кейс пользователя:
        Узел упал на 1 час, восстановился, поработал и снова упал.
        Время простоя при повторном падении должно отсчитываться с момента нового падения,
        а не содержать старый час.
        """
        t0 = datetime.now(timezone.utc) - timedelta(hours=2)
        # Узел упал 2 часа назад
        host = Host(id="h1", ip="10.0.0.1", name="Server-1", status="OFFLINE", offline_since=t0.isoformat())

        # 1. Спустя 1 час узел восстанавливается (ONLINE)
        t_recovery = t0 + timedelta(hours=1)
        st1, os1, up1 = self.thread._calculate_status(host, "ONLINE", t_recovery)
        self.assertEqual(st1, "ONLINE")
        self.assertIsNone(os1, "offline_since должен быть None при переходе в ONLINE")
        self.assertTrue(up1)

        # Симулируем обновление кешей потока и состояния хоста
        self.thread._known_statuses["h1"] = "ONLINE"
        self.thread._recovery_times["h1"] = t_recovery
        host.status = "ONLINE"
        host.offline_since = None

        # 2. Еще через 1 час узел снова падает
        t_second_outage = t_recovery + timedelta(hours=1)
        st2, os2, up2 = self.thread._calculate_status(host, "OFFLINE", t_second_outage)

        self.assertIsNotNone(os2, "offline_since должен быть установлен при падении")
        # Парсим время нового падения
        new_dt = datetime.fromisoformat(os2)
        if new_dt.tzinfo is None:
            new_dt = new_dt.replace(tzinfo=timezone.utc)

        # Длительность должна быть строго 0 на момент первого сбоя
        duration = (t_second_outage - new_dt).total_seconds()
        self.assertAlmostEqual(duration, 0.0, delta=1.0,
                               msg=f"Счетчик простоя должен начаться с 0, а начался с {duration} сек!")

    def test_transient_packet_drop_while_online_cleared_on_next_ping(self):
        """
        Если узел в ONLINE кратковременно потерял 1 пинг, а затем снова ответил,
        offline_since должен полностью сброситься в None, а не 'висеть' в памяти.
        """
        now = datetime.now(timezone.utc)
        host = Host(id="h2", ip="10.0.0.2", name="Server-2", status="ONLINE", offline_since=None)

        # 1-й пинг упал (кратковременный глитч) -> остается ONLINE, но пишет время сбоя
        st1, os1, up1 = self.thread._calculate_status(host, "OFFLINE", now)
        self.assertEqual(st1, "ONLINE")
        self.assertIsNotNone(os1)
        host.offline_since = os1

        # Следующий пинг успешен (ONLINE)
        t_next = now + timedelta(seconds=2)
        st2, os2, up2 = self.thread._calculate_status(host, "ONLINE", t_next)
        self.assertEqual(st2, "ONLINE")
        self.assertIsNone(os2, "offline_since обязан очиститься при успешном пинге, даже если узел уже был ONLINE")
        self.assertTrue(up2, "Должен быть флаг обновления для очистки метки в БД")

    def test_stale_offline_since_discarded_if_older_than_recovery(self):
        """
        Если из БД вычитан старый offline_since (меньше recovery_time),
        он должен быть проигнорирован и заменен на текущее время.
        """
        t_old = datetime.now(timezone.utc) - timedelta(hours=1)
        t_recovered = datetime.now(timezone.utc) - timedelta(minutes=5)
        t_now = datetime.now(timezone.utc)

        host = Host(id="h3", ip="10.0.0.3", name="Server-3", status="OFFLINE", offline_since=t_old.isoformat())
        self.thread._recovery_times["h3"] = t_recovered

        st, os_val, up = self.thread._calculate_status(host, "OFFLINE", t_now)
        new_dt = datetime.fromisoformat(os_val)
        if new_dt.tzinfo is None:
            new_dt = new_dt.replace(tzinfo=timezone.utc)

        duration = (t_now - new_dt).total_seconds()
        self.assertAlmostEqual(duration, 0.0, delta=1.0,
                               msg=f"Устаревший offline_since должен был сброситься, но посчитано {duration} сек!")


if __name__ == '__main__':
    unittest.main()
