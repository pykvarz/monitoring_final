"""Уведомления о восстановлении только после подтверждённого OFFLINE."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from PyQt5.QtWidgets import QApplication

from models import AppConfig, Host
from monitor_thread import MonitorThread
from services import PingService


_APP = QApplication.instance() or QApplication([])


@pytest.mark.parametrize("previous_status, notifications_enabled, expected", [
    ("WAITING", True, []),
    ("OFFLINE", True, [["Recovery host"]]),
    ("OFFLINE", False, []),
    ("ONLINE", True, []),
])
def test_recovery_notification_requires_offline(previous_status, notifications_enabled, expected, monkeypatch):
    host = Host(
        id="recovery-host", name="Recovery host", ip="127.0.0.1",
        status=previous_status, notifications_enabled=notifications_enabled,
        offline_since=(datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
    )
    repository = MagicMock()
    repository.get_all.return_value = [host]
    repository.get.return_value = host
    monkeypatch.setattr(PingService, "ping_host", lambda *args, **kwargs: True)
    monitor = MonitorThread(repository, AppConfig(poll_interval=60), db_name=":memory:")
    recovered, updates, completed = [], [], []
    monitor.hosts_recovered.connect(recovered.append)
    monitor.host_status_changed.connect(lambda *args: updates.append(args))
    monitor.scan_finished.connect(lambda: completed.append(True))
    try:
        monitor.start()
        deadline = time.monotonic() + 3
        while not completed and time.monotonic() < deadline:
            _APP.processEvents()
            time.sleep(0.01)
    finally:
        monitor.stop()
        _APP.processEvents()

    assert completed, "Цикл мониторинга не завершился"
    assert updates == [(host.id, "ONLINE", None)]
    assert recovered == expected
