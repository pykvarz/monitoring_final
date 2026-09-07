#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os, unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath('.')))

from PyQt5.QtWidgets import QApplication, QLineEdit, QComboBox, QTableView
from PyQt5.QtCore import Qt
from tests.conftest import TestFixtures
from filter_manager import FilterManager
from table_model import HostTableModel
from monitor_thread import MonitorThread
from models import Host, HostStatus

def _make_host(**kwargs):
    defaults = dict(id='h1', name='Node', ip='192.168.1.1',
                    group='G1', status='ONLINE',
                    address='', offline_since=None, last_seen=None,
                    notifications_enabled=True, notified=False)
    defaults.update(kwargs)
    return Host(**defaults)

class TestDashboardFilterPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()
    def setUp(self):
        db_manager, _, repository, _ = TestFixtures.create_repository_with_data(6)
        self.db_manager = db_manager
        self.table_model = HostTableModel()
        self.table = QTableView()
        self.table.setModel(self.table_model)
        online = [_make_host(id=f'on{i}', name=f'Online{i}', ip=f'1.1.1.{i}', status='ONLINE') for i in range(3)]
        offline = [_make_host(id=f'off{i}', name=f'Offline{i}', ip=f'2.2.2.{i}', status='OFFLINE') for i in range(3)]
        self.table_model.set_hosts(online + offline)
        self.fm = FilterManager(QLineEdit(), None, None, self.table, self.table_model)
    def tearDown(self):
        TestFixtures.cleanup_db(self.db_manager)
    def _visible(self):
        return [self.table_model.get_host(r).status for r in range(self.table_model.rowCount()) if not self.table.isRowHidden(r)]
    def test_shows_only_offline(self):
        self.fm.set_dashboard_status_filter('OFFLINE')
        s = self._visible()
        self.assertTrue(all(x == 'OFFLINE' for x in s), s)
    def test_survives_apply_filters(self):
        self.fm.set_dashboard_status_filter('OFFLINE')
        for _ in range(3): self.fm.apply_filters()
        s = self._visible()
        self.assertTrue(all(x == 'OFFLINE' for x in s), s)
    def test_reset_shows_all(self):
        self.fm.set_dashboard_status_filter('OFFLINE')
        self.fm.reset_filters()
        s = set(self._visible())
        self.assertIn('ONLINE', s)
        self.assertIn('OFFLINE', s)
    def test_none_shows_all(self):
        self.fm.set_dashboard_status_filter('ONLINE')
        self.fm.set_dashboard_status_filter(None)
        self.assertGreaterEqual(len(set(self._visible())), 2)

class TestTableResortOnStatusChange(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()
    def _model_sorted(self):
        m = HostTableModel()
        hosts = [_make_host(id='a', name='Alpha', ip='1.1.1.1', status='ONLINE'),
                 _make_host(id='b', name='Beta',  ip='1.1.1.2', status='ONLINE'),
                 _make_host(id='c', name='Gamma', ip='1.1.1.3', status='ONLINE')]
        m.set_hosts(hosts)
        m.sort(0, Qt.DescendingOrder)
        return m
    def _order(self, m):
        return [m.get_host(r).status for r in range(m.rowCount())]
    def test_resort_on_status_change(self):
        m = self._model_sorted()
        m.update_hosts([_make_host(id='b', name='Beta', ip='1.1.1.2', status='OFFLINE')])
        self.assertEqual(self._order(m)[0], 'OFFLINE', self._order(m))
    def test_no_resort_without_status_change(self):
        m = self._model_sorted()
        before = self._order(m)
        m.update_hosts([_make_host(id='a', name='Alpha', ip='1.1.1.1', status='ONLINE')])
        self.assertEqual(before, self._order(m))
    def test_host_map_correct_after_resort(self):
        m = self._model_sorted()
        m.update_hosts([_make_host(id='c', name='Gamma', ip='1.1.1.3', status='OFFLINE')])
        for r in range(m.rowCount()):
            h = m.get_host(r)
            self.assertEqual(m._host_map.get(h.id), r)
    def test_no_sort_column_no_resort(self):
        m = HostTableModel()
        m.set_hosts([_make_host(id='a', status='ONLINE'), _make_host(id='b', status='ONLINE')])
        m.update_hosts([_make_host(id='a', status='OFFLINE')])
        self.assertEqual(m.get_host(0).status, 'OFFLINE')

class TestOfflineSinceReset(unittest.TestCase):
    def setUp(self):
        cfg = MagicMock()
        cfg.offline_timeout = 30
        cfg.waiting_timeout = 5
        cfg.poll_interval = 2
        cfg.max_workers = 5
        self.thread = MonitorThread(MagicMock(), cfg)
    def test_resets_on_refailure(self):
        """Повторное падение после восстановления: offline_since обнуляется."""
        now = datetime.now(timezone.utc)
        recovery_time = now - timedelta(seconds=30)  # восстановился 30 сек назад
        self.thread._recovery_times['h1'] = recovery_time

        # В БД лежит устаревший offline_since (от прошлого падения, до восстановления)
        old = (now - timedelta(minutes=10)).isoformat()
        host = _make_host(id='h1', status='ONLINE', offline_since=old)

        _, offline_since, _ = self.thread._calculate_status(host, 'OFFLINE', now)

        new_dt = datetime.fromisoformat(offline_since).replace(tzinfo=timezone.utc)
        self.assertLess(abs((new_dt - now).total_seconds()), 5,
                        "offline_since должен быть ~now, а не старым значением")

    def test_stale_db_ignored(self):
        """Устаревший offline_since из БД (предшествует восстановлению) игнорируется."""
        now = datetime.now(timezone.utc)
        recovery_time = now - timedelta(minutes=5)  # восстановился 5 минут назад
        self.thread._recovery_times['h2'] = recovery_time

        # Устаревший offline_since: был выставлен час назад (до восстановления)
        stale = (now - timedelta(hours=1)).isoformat()
        host = _make_host(id='h2', status='ONLINE', offline_since=stale)

        _, offline_since, upd = self.thread._calculate_status(host, 'OFFLINE', now)

        self.assertTrue(upd)
        new_dt = datetime.fromisoformat(offline_since).replace(tzinfo=timezone.utc)
        self.assertLess(abs((new_dt - now).total_seconds()), 5,
                        "Стale offline_since должен быть заменён текущим временем")

    def test_timer_accumulates_across_pings(self):
        """
        Критически важно: при нескольких подряд неудачных пингах после восстановления
        таймер должен накапливаться, а НЕ сбрасываться на каждом пинге.
        Это проверяет, что после первого сброса (offline_since=now) следующие пинги
        не сбрасывают его снова (т.к. offline_since уже > recovery_time).
        """
        recovery_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.thread._recovery_times['h1'] = recovery_time

        # Имитируем: на первом пинге был сброшен, выставлен как T1
        T1 = datetime.now(timezone.utc)
        host_after_first_ping = _make_host(id='h1', status='ONLINE',
                                           offline_since=T1.isoformat())

        # Второй пинг — offline_since (T1) > recovery_time → не сбрасывается
        _, offline_since2, _ = self.thread._calculate_status(
            host_after_first_ping, 'OFFLINE', T1 + timedelta(seconds=3))

        result_dt = datetime.fromisoformat(offline_since2).replace(tzinfo=timezone.utc)
        # offline_since должен остаться T1, а не обнулиться снова
        self.assertLess(abs((result_dt - T1).total_seconds()), 1,
                        "offline_since не должен сбрасываться на втором подряд неудачном пинге")

    def test_already_offline_preserves_since(self):
        now = datetime.now(timezone.utc)
        orig = (now - timedelta(minutes=3)).isoformat()
        host = _make_host(id='h3', status='OFFLINE', offline_since=orig)
        self.thread._known_statuses['h3'] = 'OFFLINE'
        _, offline_since, _ = self.thread._calculate_status(host, 'OFFLINE', now)
        self.assertEqual(offline_since, orig)

    def test_recovery_clears_since(self):
        now = datetime.now(timezone.utc)
        host = _make_host(id='h5', status='OFFLINE', offline_since=(now - timedelta(minutes=5)).isoformat())
        ns, offline_since, upd = self.thread._calculate_status(host, 'ONLINE', now)
        self.assertEqual(ns, 'ONLINE')
        self.assertIsNone(offline_since)
        self.assertTrue(upd)


if __name__ == '__main__':
    unittest.main(verbosity=2)

