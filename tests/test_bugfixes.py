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


class TestStatusMachineStuckOnline(unittest.TestCase):
    """Регрессия: хост не переходил из ONLINE в WAITING/OFFLINE.

    Корневая причина: _record_to_host() принудительно обнулял offline_since
    для хостов со статусом ONLINE. Статус-машина в MonitorThread на каждом
    цикле видела offline_since=None, ставила offline_since=now(), но длительность
    простоя всегда была ~0 — пороги waiting_timeout/offline_timeout никогда
    не достигались.
    """

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def setUp(self):
        self.db_manager, self.data_manager, self.repository, _ = (
            TestFixtures.create_repository_with_data(0)
        )
        self.config = MagicMock()
        self.config.waiting_timeout = 60
        self.config.offline_timeout = 300
        self.config.max_workers = 2

    def tearDown(self):
        TestFixtures.cleanup_db(self.db_manager)

    def test_offline_since_preserved_for_online_hosts(self):
        """offline_since должен читаться из БД даже если status=ONLINE.

        Статус-машина пишет offline_since при первом неудачном пинге,
        но status ещё остаётся ONLINE (порог не достигнут). При следующем
        чтении offline_since не должен обнуляться.
        """
        host = _make_host(id='h1', ip='10.0.0.1')
        self.data_manager.add_host(host)

        # Эмулируем: первый пинг не прошёл, статус-машина записала
        # offline_since, но статус всё ещё ONLINE (порог не достигнут)
        offline_ts = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc).isoformat()
        self.data_manager.update_host_status('h1', 'ONLINE', offline_ts)

        # Читаем обратно — offline_since НЕ должен быть обнулён
        hosts = self.data_manager.get_all_hosts()
        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0].status, 'ONLINE')
        self.assertIsNotNone(hosts[0].offline_since,
                             "offline_since обнулился при чтении ONLINE-хоста — "
                             "статус-машина не сможет отследить длительность простоя")
        self.assertEqual(hosts[0].offline_since, offline_ts)

    def test_status_machine_transitions_to_waiting(self):
        """Хост переходит из ONLINE в WAITING только после waiting_timeout.
    
        Шаг 1: При первом сбое фиксируем offline_since, но оставляем ONLINE.
        Шаг 2: После waiting_timeout статус меняется на WAITING.
        """
        mt = MonitorThread(self.repository, self.config, db_name=":memory:")
    
        # Цикл 1: host ONLINE, пинг не прошёл
        t1 = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)
        host = _make_host(status='ONLINE', offline_since=None)
        ns, os_val, upd = mt._calculate_status(host, 'OFFLINE', t1)
    
        # Статус пока ONLINE, offline_since установлен
        self.assertEqual(ns, 'ONLINE')
        self.assertIsNotNone(os_val)
        self.assertTrue(upd)
    
        # Цикл 2: через 90 секунд (> waiting_timeout=60)
        t2 = t1 + timedelta(seconds=90)
        host2 = _make_host(status='ONLINE', offline_since=os_val)
        ns2, os_val2, upd2 = mt._calculate_status(host2, 'OFFLINE', t2)

        self.assertEqual(ns2, 'WAITING',
                         "Хост должен был перейти в WAITING после 90 секунд простоя")
        self.assertEqual(os_val2, os_val,
                         "offline_since не должен сбрасываться между циклами")

    def test_status_machine_transitions_to_offline(self):
        """Хост должен перейти из WAITING в OFFLINE после offline_timeout."""
        mt = MonitorThread(self.repository, self.config, db_name=":memory:")

        t_start = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)
        offline_since = t_start.isoformat()

        # Через 310 сек (> offline_timeout=300)
        t_now = t_start + timedelta(seconds=310)
        host = _make_host(status='WAITING', offline_since=offline_since)
        ns, os_val, upd = mt._calculate_status(host, 'OFFLINE', t_now)

        self.assertEqual(ns, 'OFFLINE',
                         "Хост должен был перейти в OFFLINE после 310 секунд простоя")


class TestLastSeenMapping(unittest.TestCase):
    """Регрессия: last_seen не маппился из БД → heartbeat throttling не работал."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def setUp(self):
        self.db_manager, self.data_manager, self.repository, _ = (
            TestFixtures.create_repository_with_data(0)
        )

    def tearDown(self):
        TestFixtures.cleanup_db(self.db_manager)

    def test_last_seen_read_from_db(self):
        """last_seen должен корректно читаться из БД после update_host_status."""
        host = _make_host(id='h1', ip='10.0.0.1')
        self.data_manager.add_host(host)

        # update_host_status пишет last_seen = datetime.now().isoformat()
        self.data_manager.update_host_status('h1', 'ONLINE')

        hosts = self.data_manager.get_all_hosts()
        self.assertEqual(len(hosts), 1)
        self.assertIsNotNone(hosts[0].last_seen,
                             "last_seen не читается из БД — heartbeat throttling сломан")


class TestHelpdeskServiceArgs(unittest.TestCase):
    """Регрессия: HelpdeskService вызывался с Host вместо list[str]."""

    def test_process_offline_expects_list(self):
        """process_offline принимает list строк, не объект Host."""
        from helpdesk_service import HelpdeskService
        config = MagicMock()
        config.helpdesk_enabled = False  # Не будет реально отправлять

        # Не должно бросать TypeError
        HelpdeskService.process_offline(["test_host"], config)

    def test_process_recovered_expects_list(self):
        """process_recovered принимает list строк, не объект Host."""
        from helpdesk_service import HelpdeskService
        config = MagicMock()
        config.helpdesk_enabled = False

        HelpdeskService.process_recovered(["test_host"], config)


class TestTableSortWithHostnames(unittest.TestCase):
    """Регрессия: сортировка по колонке IP падала с TypeError при наличии доменных имен."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def test_sort_ip_column_with_mixed_ipv4_and_hostname(self):
        model = HostTableModel()
        h1 = _make_host(id='1', name='H1', ip='192.168.1.10')
        h2 = _make_host(id='2', name='H2', ip='router.local')
        h3 = _make_host(id='3', name='H3', ip='10.0.0.1')
        h4 = _make_host(id='4', name='H4', ip='api.corp.net')
        model.set_hosts([h1, h2, h3, h4])

        # Не должно вызывать TypeError: '<' not supported between instances of 'list' and 'str'
        model.sort(2, Qt.AscendingOrder)
        hosts_asc = [model.get_host(i).ip for i in range(model.rowCount())]
        self.assertEqual(len(hosts_asc), 4)

        model.sort(2, Qt.DescendingOrder)
        hosts_desc = [model.get_host(i).ip for i in range(model.rowCount())]
        self.assertEqual(len(hosts_desc), 4)

class TestOfflineTimeTooltip(unittest.TestCase):
    """Проверка подсказки ToolTip для колонки времени простоя (колонка 5)."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def test_offline_time_tooltip_shows_exact_time(self):
        model = HostTableModel()
        h = _make_host(id='1', name='H1', ip='192.168.1.1', status='OFFLINE', offline_since='2026-09-14T10:15:30+00:00')
        model.set_hosts([h])

        idx = model.index(0, 5)
        tooltip = model.data(idx, Qt.ToolTipRole)
        self.assertIsNotNone(tooltip)
        self.assertIn("Недоступен с:", tooltip)


class TestSortWithNoneValues(unittest.TestCase):
    """Регрессия CRIT-1: сортировка по колонкам Название, Адрес, Группа падала при наличии None."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def test_sort_group_column_with_none(self):
        model = HostTableModel()
        h1 = _make_host(id='1', name='H1', ip='192.168.1.1', group='Servers')
        h2 = _make_host(id='2', name='H2', ip='192.168.1.2')
        h2.group = None
        model.set_hosts([h1, h2])

        # Не должно вызывать AttributeError: 'NoneType' object has no attribute 'lower'
        model.sort(4, Qt.AscendingOrder)
        self.assertEqual(model.rowCount(), 2)
        model.sort(4, Qt.DescendingOrder)
        self.assertEqual(model.rowCount(), 2)

    def test_sort_name_column_with_none(self):
        model = HostTableModel()
        h1 = _make_host(id='1', name='H1', ip='192.168.1.1')
        h2 = _make_host(id='2', name='H2', ip='192.168.1.2')
        h2.name = None
        model.set_hosts([h1, h2])

        model.sort(1, Qt.AscendingOrder)
        self.assertEqual(model.rowCount(), 2)
        model.sort(1, Qt.DescendingOrder)
        self.assertEqual(model.rowCount(), 2)

    def test_sort_address_column_with_none(self):
        model = HostTableModel()
        h1 = _make_host(id='1', name='H1', ip='192.168.1.1', address='Room 101')
        h2 = _make_host(id='2', name='H2', ip='192.168.1.2')
        h2.address = None
        model.set_hosts([h1, h2])

        model.sort(3, Qt.AscendingOrder)
        self.assertEqual(model.rowCount(), 2)
        model.sort(3, Qt.DescendingOrder)
        self.assertEqual(model.rowCount(), 2)


class TestUnknownStatusHandling(unittest.TestCase):
    """Регрессия CRIT-2: экспорт в Excel и тултип таблицы падали с KeyError при статусе UNKNOWN."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def test_excel_export_with_unknown_status(self):
        from excel_service import ExcelService
        import tempfile
        h = _make_host(id='1', name='NodeUnknown', ip='10.0.0.99', status='UNKNOWN')
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tf:
            tmp_path = tf.name

        try:
            # Не должно вызывать KeyError: 'UNKNOWN'
            ExcelService.export_hosts(tmp_path, [h])
            self.assertTrue(os.path.exists(tmp_path))
            self.assertGreater(os.path.getsize(tmp_path), 0)
        finally:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass

    def test_table_model_tooltip_with_unknown_status(self):
        model = HostTableModel()
        h = _make_host(id='1', name='NodeUnknown', ip='10.0.0.99', status='UNKNOWN')
        model.set_hosts([h])

        # Не должно вызывать KeyError: 'UNKNOWN'
        idx = model.index(0, 0)
        tooltip = model.data(idx, Qt.ToolTipRole)
        self.assertIn("UNKNOWN", str(tooltip))


class TestFloatingEventLogCloseLifecycle(unittest.TestCase):
    """Регрессия CRIT-3: при штатном закрытии MainWindow сброс event_log_floating обратно в False."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def test_close_event_preserves_event_log_floating(self):
        from main_window import MainWindow
        from di_container import setup_container
        container = setup_container()
        mw = MainWindow(container)

        try:
            mw._undock_event_log()
            self.assertTrue(mw._config.event_log_floating)

            class MockCloseEvent:
                def accept(self): pass

            mw.closeEvent(MockCloseEvent())
            self.assertTrue(mw._config.event_log_floating, "event_log_floating must remain True on app exit")
        finally:
            mw.close()


class TestSettingsDialogPreservesHUDConfig(unittest.TestCase):
    """Регрессия HIGH-1: SettingsDialog.get_config() сбрасывал splitter_sizes и параметры плавающего HUD."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def test_get_config_preserves_hud_and_splitter_settings(self):
        from dialogs import SettingsDialog
        from models import AppConfig

        orig_config = AppConfig(
            splitter_sizes=[250, 450],
            event_log_floating=True,
            event_log_on_top=False,
            event_log_geometry=[150, 250, 500, 600]
        )

        dlg = SettingsDialog(None, orig_config)
        new_config = dlg.get_config()

        self.assertEqual(new_config.splitter_sizes, [250, 450])
        self.assertTrue(new_config.event_log_floating)
        self.assertFalse(new_config.event_log_on_top)
        self.assertEqual(new_config.event_log_geometry, [150, 250, 500, 600])


class TestContextMenuManagerBulkMenu(unittest.TestCase):
    """Регрессия HIGH-2: ContextMenuManager.show_bulk_menu падал с NameError: SVG_MAINTENANCE."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def test_show_bulk_menu_no_name_error(self):
        from context_menu_manager import ContextMenuManager
        from PyQt5.QtWidgets import QWidget, QPushButton
        from unittest.mock import patch, MagicMock

        parent = QWidget()
        repo = MagicMock()
        cmm = ContextMenuManager(parent, MagicMock(), MagicMock(), ["Default"], lambda: "dark", repo)
        sender = QPushButton("Bulk", parent)

        # Мокаем exec_ меню, чтобы окно не блокировало тест
        with patch("PyQt5.QtWidgets.QMenu.exec_", return_value=None):
            # Не должно вызывать NameError
            cmm.show_bulk_menu(sender)


class TestStorageMigrateToDbPreservesAddress(unittest.TestCase):
    """Регрессия HIGH-3: StorageManager.migrate_to_db терял поле address и не передавал дескриптор БД."""

    @classmethod
    def setUpClass(cls):
        TestFixtures.setup_qapp()

    def test_migrate_to_db_copies_address_and_finishes_query(self):
        import tempfile
        import json
        from pathlib import Path
        from storage import StorageManager

        db_manager = TestFixtures.create_in_memory_db()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                hosts_file = Path(tmpdir) / "hosts.json"
                raw_data = [
                    {
                        "id": "h_mig_1",
                        "name": "Server 1",
                        "ip": "192.168.10.50",
                        "address": "Floor 2, Rack 5",
                        "group": "Servers",
                        "status": "ONLINE",
                        "notifications_enabled": True
                    }
                ]
                with open(hosts_file, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f)

                storage = StorageManager()
                storage._hosts_file = hosts_file
                success = storage.migrate_to_db(db_manager)
                self.assertTrue(success)

                # Проверяем, что в БД поле address сохранилось
                db = db_manager.get_db()
                from PyQt5.QtSql import QSqlQuery
                q = QSqlQuery(db)
                q.exec_("SELECT address FROM hosts WHERE id = 'h_mig_1'")
                self.assertTrue(q.next())
                saved_address = q.value(0)
                q.finish()

                self.assertEqual(saved_address, "Floor 2, Rack 5")
        finally:
            TestFixtures.cleanup_db(db_manager)


if __name__ == '__main__':
    unittest.main(verbosity=2)


