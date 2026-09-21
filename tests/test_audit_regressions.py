"""Регрессионные тесты для дефектов, найденных полным аудитом."""

import time
import threading
import json
import asyncio
from unittest.mock import MagicMock
from unittest.mock import AsyncMock, patch

import openpyxl
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from PyQt5.QtWidgets import QApplication

from core.host_repository import HostRepository
from data_manager import DataManager
from database import DatabaseManager
from dialogs import HostDialog
from excel_service import ExcelService
from helpdesk_service import HelpdeskService
from main_window import MainWindow
from models import Host
from models import AppConfig
from monitor_thread import MonitorThread
from storage import StorageManager


_TEST_APP = QApplication.instance() or QApplication([])


def test_monitor_result_does_not_overwrite_maintenance_status(tmp_path):
    """Отложенный результат ping не должен отменять MAINTENANCE оператора."""
    db_manager = DatabaseManager(str(tmp_path / "maintenance-race.db"))
    repository = HostRepository(DataManager(db_manager))
    host = Host(id="host-1", name="ATM-1", ip="127.0.0.1", status="ONLINE")

    try:
        assert repository.add(host)
        repository.update_status(host.id, "MAINTENANCE")
        assert repository.get(host.id).status == "MAINTENANCE"

        assert not repository.apply_monitor_status(host.id, "ONLINE", None)
        assert repository.get(host.id).status == "MAINTENANCE"
        assert repository.get_history_events()[-1]["new_status"] == "MAINTENANCE"
    finally:
        db_manager.close()


def test_interrupted_cycle_emits_notifications_already_collected():
    """Прерывание цикла не должно терять уже подтверждённые переходы статуса."""
    app = _TEST_APP
    first = Host(id="host-1", name="ATM-1", ip="127.0.0.1", status="ONLINE")
    second = Host(id="host-2", name="ATM-2", ip="127.0.0.2", status="ONLINE")
    repository = MagicMock()
    calls = 0

    def get_all(connection_name=None):
        nonlocal calls
        calls += 1
        return [first, second] if calls == 1 else []

    repository.get_all.side_effect = get_all
    config = AppConfig(poll_interval=60, max_workers=1)
    config.waiting_timeout = 0
    config.offline_timeout = 0
    monitor = MonitorThread(repository, config, db_name=":memory:")
    def get_host(host_id, connection_name=None):
        if host_id == first.id:
            monitor.interrupt_cycle()
            return first
        return second

    repository.get.side_effect = get_host
    monitor._check_host = lambda host: (host.id, "OFFLINE", None)
    offline_batches = []
    monitor.hosts_offline.connect(offline_batches.append)

    try:
        monitor.start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not offline_batches:
            app.processEvents()
            time.sleep(0.01)
    finally:
        monitor.stop()

    assert offline_batches == [["ATM-1"]]


def test_monitor_stop_cancels_executor_jobs_that_have_not_started():
    """Остановка мониторинга не должна запускать очередь устаревших ping."""
    monitor = MonitorThread(MagicMock(), AppConfig(max_workers=1), db_name=":memory:")
    release_first = threading.Event()
    first_started = threading.Event()
    started = []

    def job(index):
        started.append(index)
        if index == 0:
            first_started.set()
            release_first.wait(timeout=2)

    for index in range(6):
        monitor._executor.submit(job, index)

    assert first_started.wait(timeout=1)
    monitor.stop()
    release_first.set()
    time.sleep(0.1)

    assert started == [0]


def test_failed_json_migration_keeps_source_file(tmp_path):
    """Неуспешная транзакция не должна помечать JSON как мигрированный."""
    if QSqlDatabase.contains("qt_sql_default_connection"):
        existing = QSqlDatabase.database("qt_sql_default_connection", open=False)
        existing.close()
        del existing
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
    storage = StorageManager(tmp_path)
    assert storage.save_hosts([
        Host(id="host-1", name="ATM-1", ip="10.0.0.1", status="ONLINE")
    ])
    db_manager = DatabaseManager(str(tmp_path / "migration.db"))
    query = QSqlQuery(db_manager.get_db())
    assert query.exec_("PRAGMA query_only = ON")
    query.finish()

    try:
        assert not storage.migrate_to_db(db_manager)
        assert storage.hosts_file.exists()
        assert not storage.hosts_file.with_suffix(".json.bak").exists()
        count_query = QSqlQuery(db_manager.get_db())
        assert count_query.exec_("SELECT COUNT(*) FROM hosts")
        assert count_query.next()
        assert count_query.value(0) == 0
        count_query.finish()
    finally:
        query = QSqlQuery(db_manager.get_db())
        query.exec_("PRAGMA query_only = OFF")
        query.finish()
        db_manager.close()


def test_failed_config_write_preserves_previous_file(tmp_path):
    """Ошибка записи не должна оставлять усечённый config.json."""
    storage = StorageManager(tmp_path)
    original = AppConfig(poll_interval=77)
    assert storage.save_config(original)

    def partial_dump(data, stream, **kwargs):
        stream.write("{")
        raise OSError("disk full")

    with patch("storage.json.dump", side_effect=partial_dump):
        assert not storage.save_config(AppConfig(poll_interval=88))

    assert storage.load_config().poll_interval == 77


def test_non_object_config_uses_defaults(tmp_path):
    """Корректный JSON неверного типа не должен срывать запуск приложения."""
    storage = StorageManager(tmp_path)
    storage.config_file.write_text("[]", encoding="utf-8")

    config = storage.load_config()

    assert config == AppConfig()


def test_host_dialog_returns_copy_when_editing_existing_host():
    """Диалог не должен менять объект таблицы до успешного сохранения в БД."""
    original = Host(
        id="host-1",
        name="ATM-1",
        ip="10.0.0.1",
        address="Old address",
        group="ATM",
        status="OFFLINE",
        offline_since="2026-01-01T00:00:00+00:00",
    )
    dialog = HostDialog(None, host=original, groups=["ATM"])
    dialog._ip_edit.setText("10.0.0.2")

    edited = dialog.get_host()

    assert edited is not original
    assert edited.ip == "10.0.0.2"
    assert original.ip == "10.0.0.1"
    assert edited.status == "OFFLINE"
    assert edited.offline_since == original.offline_since


def test_global_notification_switch_disables_toasts():
    """Глобальное отключение уведомлений распространяется и на toast."""
    window = MagicMock()
    window._config = AppConfig(notifications_enabled=False)
    window._toast_manager = MagicMock()

    with patch("main_window.NotificationService.notify_offline_hosts") as notify:
        MainWindow._on_hosts_offline(window, ["ATM-1"])

    window._toast_manager.show_offline.assert_not_called()
    notify.assert_not_called()


def test_excel_import_preserves_model_valid_hostname(tmp_path):
    """Импорт не должен обрезать допустимое имя узла длиннее 100 символов."""
    hostname = ".".join(["a" * 32, "b" * 32, "c" * 32, "d" * 32])
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Название", "IP адрес", "Адрес", "Группа"])
    sheet.append(["ATM-1", hostname, "Address", "ATM"])
    path = tmp_path / "hosts.xlsx"
    workbook.save(path)
    workbook.close()

    hosts, skipped, errors = ExcelService.import_hosts(str(path), set())

    assert skipped == 0
    assert errors == []
    assert hosts[0].ip == hostname


def test_host_dialog_uses_model_field_limits():
    """Ограничения полей диалога должны совпадать с моделью Host."""
    dialog = HostDialog(None, groups=["ATM"])

    assert dialog._name_edit.maxLength() == 100
    assert dialog._ip_edit.maxLength() == 253
    assert dialog._address_edit.maxLength() == 200


def test_helpdesk_rejects_login_redirect_after_save():
    """Закрытие формы через редирект на вход не подтверждает создание заявки."""
    async def run():
        page = MagicMock()
        page.url = "https://helpdesk.example/login"
        with patch.object(
            HelpdeskService,
            "_wait_for_form_closed",
            new=AsyncMock(return_value=True),
        ):
            return await HelpdeskService._confirm_ticket_saved(
                page,
                MagicMock(),
                "https://helpdesk.example/sd/operator/",
            )

    assert not asyncio.run(run())


def test_helpdesk_rejects_error_page_after_save():
    async def run():
        page = MagicMock()
        page.url = "https://helpdesk.example/error"
        page.locator.return_value.first.inner_text = AsyncMock(return_value="Ошибка сервера")
        with patch.object(HelpdeskService, "_wait_for_form_closed", new=AsyncMock(return_value=True)):
            return await HelpdeskService._confirm_ticket_saved(page, MagicMock(), "https://helpdesk.example/form")
    assert not asyncio.run(run())


def test_helpdesk_rejects_non_ticket_id_redirect():
    async def run():
        page = MagicMock()
        page.url = "https://helpdesk.example/request/error"
        page.locator.return_value.first.inner_text = AsyncMock(return_value="Ошибка сервера")
        with patch.object(HelpdeskService, "_wait_for_form_closed", new=AsyncMock(return_value=True)):
            return await HelpdeskService._confirm_ticket_saved(page, MagicMock(), "https://helpdesk.example/form")
    assert not asyncio.run(run())


def test_helpdesk_requires_positive_save_confirmation():
    async def run(message):
        page = MagicMock()
        page.url = "https://helpdesk.example/form"
        page.locator.return_value.first.inner_text = AsyncMock(return_value=message)
        with patch.object(HelpdeskService, "_wait_for_form_closed", new=AsyncMock(return_value=True)):
            return await HelpdeskService._confirm_ticket_saved(page, MagicMock(), page.url)
    assert not asyncio.run(run("Форма закрыта"))
    assert not asyncio.run(run("Заявка не создана"))
    assert asyncio.run(run("Заявка успешно создана №12345"))


def test_helpdesk_accepts_confirmation_in_iframe():
    async def run():
        page = MagicMock()
        page.url = "https://helpdesk.example/sd/operator/"
        page.locator.return_value.first.inner_text = AsyncMock(return_value="Оператор")
        frame = MagicMock()
        frame.locator.return_value.first.inner_text = AsyncMock(return_value="Заявка успешно создана №12345")
        page.frames = [frame]
        with patch.object(HelpdeskService, "_wait_for_form_closed", new=AsyncMock(return_value=True)):
            return await HelpdeskService._confirm_ticket_saved(page, frame, page.url)
    assert asyncio.run(run())


def test_load_hosts_skips_non_object_entries(tmp_path):
    storage = StorageManager(tmp_path)
    storage.hosts_file.write_text(json.dumps([None, {"name": "ATM", "ip": "127.0.0.1"}]), encoding="utf-8")
    assert [host.name for host in storage.load_hosts()] == ["ATM"]


def test_load_config_rejects_invalid_nested_types(tmp_path):
    storage = StorageManager(tmp_path)
    storage.config_file.write_text(json.dumps({"poll_interval": 77, "column_widths": [100]}), encoding="utf-8")
    config = storage.load_config()
    assert config.poll_interval == 77
    assert config.column_widths == {}


def test_load_config_rejects_invalid_collection_elements(tmp_path):
    storage = StorageManager(tmp_path)
    storage.config_file.write_text(json.dumps({"custom_groups": ["ATM", 42], "column_widths": {"0": "wide"}}), encoding="utf-8")
    config = storage.load_config()
    assert config.custom_groups == []
    assert config.column_widths == {}


def test_helpdesk_reports_every_missing_required_field():
    """Все обязательные поля Helpdesk должны участвовать в проверке до Save."""
    missing = HelpdeskService._missing_required_fields({
        "Соглашение/Услуга": False,
        "Категория услуги": True,
        "Подкатегория": False,
        "Местонахождение": True,
        "Тема": True,
        "Описание": False,
    })

    assert missing == ["Соглашение/Услуга", "Подкатегория", "Описание"]


def test_late_playwright_start_is_closed_after_wrapper_timeout():
    """Ресурсы, появившиеся после cleanup-снимка, закрываются самой сессией."""
    async def run():
        playwright = MagicMock()
        browser = MagicMock()
        playwright.stop = AsyncMock()
        browser.close = AsyncMock()
        browser.new_context = AsyncMock(side_effect=RuntimeError("stop after launch"))
        playwright.chromium.launch = AsyncMock(return_value=browser)
        starter = MagicMock()

        async def delayed_start():
            await asyncio.sleep(0.03)
            return playwright

        starter.start = AsyncMock(side_effect=delayed_start)
        previous_semaphore = HelpdeskService._semaphore
        try:
            HelpdeskService._semaphore = asyncio.Semaphore(1)
            with patch.object(HelpdeskService, "TICKET_TIMEOUT_SECONDS", 0.005), patch(
                "playwright.async_api.async_playwright",
                return_value=starter,
            ):
                await HelpdeskService._process_ticket_task_async(
                    "https://helpdesk.example/form",
                    "1234",
                    "Установить",
                    headless=True,
                )
        finally:
            HelpdeskService._semaphore = previous_semaphore

        playwright.chromium.launch.assert_not_awaited()
        browser.close.assert_not_awaited()
        playwright.stop.assert_awaited_once()

    asyncio.run(run())


def test_host_none_address_normalizes_to_empty():
    """Host(address=None) не должен падать с TypeError, address нормализуется в пустую строку."""
    host = Host(name="ATM-1", ip="10.0.0.1", address=None)
    assert host.address == ""


def test_host_none_group_normalizes_to_default():
    """Host(group=None) не должен падать с TypeError, group нормализуется в 'Без группы'."""
    host = Host(name="ATM-1", ip="10.0.0.1", group=None)
    assert host.group == "Без группы"


def test_migration_rename_succeeds_when_bak_exists(tmp_path):
    """Миграция не падает с FileExistsError, если hosts.json.bak уже существует."""
    if QSqlDatabase.contains("qt_sql_default_connection"):
        existing = QSqlDatabase.database("qt_sql_default_connection", open=False)
        existing.close()
        del existing
        QSqlDatabase.removeDatabase("qt_sql_default_connection")

    storage = StorageManager(tmp_path)
    assert storage.save_hosts([
        Host(id="host-1", name="ATM-1", ip="10.0.0.1", status="ONLINE")
    ])
    # Создаём уже существующий .bak
    bak_path = storage.hosts_file.with_suffix(".json.bak")
    bak_path.write_text('["old backup"]', encoding="utf-8")

    db_manager = DatabaseManager(str(tmp_path / "bak-test.db"))
    try:
        result = storage.migrate_to_db(db_manager)
        assert result is True
        assert not storage.hosts_file.exists(), "hosts.json должен быть переименован"
        assert bak_path.exists(), "hosts.json.bak должен существовать"
    finally:
        db_manager.close()


def test_helpdesk_allows_same_domain_path_redirect():
    """Смена path на том же домене (редирект на карточку заявки) — это успех, не ошибка."""
    async def run():
        page = MagicMock()
        # Редирект с формы создания на карточку созданной заявки (реальная смена path)
        page.url = "https://helpdesk.example/sd/ticket/12345"
        with patch.object(
            HelpdeskService,
            "_wait_for_form_closed",
            new=AsyncMock(return_value=True),
        ):
            return await HelpdeskService._confirm_ticket_saved(
                page,
                MagicMock(),
                "https://helpdesk.example/sd/createTicket.html",
            )

    assert asyncio.run(run()) is True


def test_monitor_interrupt_cycle_cancels_pending_futures():
    """Прерывание цикла должно отменять незавершённые задачи (futures)."""
    app = _TEST_APP
    h1 = Host(id="h1", name="H1", ip="127.0.0.1", status="ONLINE")
    h2 = Host(id="h2", name="H2", ip="127.0.0.2", status="ONLINE")
    repository = MagicMock()
    calls = 0

    def get_all(connection_name=None):
        nonlocal calls
        calls += 1
        return [h1, h2] if calls == 1 else []

    repository.get_all.side_effect = get_all
    repository.get.return_value = h1
    config = AppConfig(poll_interval=60, max_workers=1)
    monitor = MonitorThread(repository, config, db_name=":memory:")

    h2_started = threading.Event()
    h2_blocked = threading.Event()

    def check_host(host):
        if host.id == "h1":
            monitor.interrupt_cycle()
            return (host.id, "ONLINE", None)
        else:
            h2_started.set()
            h2_blocked.wait(timeout=2)
            return (host.id, "ONLINE", None)

    monitor._check_host = check_host
    try:
        monitor.start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and monitor._running:
            app.processEvents()
            time.sleep(0.02)
            if not monitor._interrupt_flag and calls > 1:
                break
    finally:
        h2_blocked.set()
        monitor.stop()

    assert not h2_started.is_set(), "h2 должен был быть отменён в очереди пула при прерывании цикла"


def test_data_manager_maintenance_preserves_last_seen_even_without_flag(tmp_path):
    """Смена статуса на MAINTENANCE не обновляет last_seen, даже если флаг update_last_seen не задан."""
    db_manager = DatabaseManager(str(tmp_path / "last_seen_maint.db"))
    dm = DataManager(db_manager)
    repo = HostRepository(dm)
    h = Host(id="h-last-seen", name="ATM-LastSeen", ip="127.0.0.1", status="ONLINE")
    repo.add(h)

    old_ts = "2026-09-01T10:00:00+00:00"
    q = QSqlQuery(db_manager.get_db())
    q.prepare("UPDATE hosts SET last_seen = :ls WHERE id = :id")
    q.bindValue(":ls", old_ts)
    q.bindValue(":id", h.id)
    assert q.exec_()
    q.finish()

    # Прямой вызов update_status без передачи update_last_seen
    dm.update_host_status(h.id, "MAINTENANCE")
    updated = repo.get(h.id)
    assert updated.status == "MAINTENANCE"
    assert updated.last_seen == old_ts, f"last_seen был подделан! {updated.last_seen} != {old_ts}"
    db_manager.close()


def test_helpdesk_confirm_saved_matches_russian_incident_and_request():
    """Проверка подтверждения Helpdesk для терминов «обращение» и «инцидент» с ID."""
    async def run():
        page = MagicMock()
        page.url = "https://helpdesk.example/sd/operator/"
        page.frames = []

        # Контейнер уведомлений с сообщением «Обращение №12345 зарегистрировано»
        notify_el = MagicMock()
        notify_el.inner_text = AsyncMock(return_value="Обращение №12345 успешно зарегистрировано")
        locator_mock = MagicMock()
        locator_mock.count = AsyncMock(return_value=1)
        locator_mock.nth.return_value = notify_el

        page.locator.return_value = locator_mock

        with patch.object(HelpdeskService, "_wait_for_form_closed", new=AsyncMock(return_value=True)):
            res = await HelpdeskService._confirm_ticket_saved(
                page,
                MagicMock(),
                "https://helpdesk.example/sd/createTicket.html",
            )
            assert res is True

            # Проверка, что неизменившийся URL карточки не подтверждает сохранение
            page_same_url = MagicMock()
            page_same_url.url = "https://helpdesk.example/sd/ticket/12345"
            page_same_url.frames = []
            empty_locator = MagicMock()
            empty_locator.count = AsyncMock(return_value=0)
            page_same_url.locator.return_value = empty_locator
            res_same = await HelpdeskService._confirm_ticket_saved(
                page_same_url,
                MagicMock(),
                "https://helpdesk.example/sd/ticket/12345",
            )
            assert res_same is False

    asyncio.run(run())


def test_excel_sanitize_cell_value_tabs_and_formulas():
    """Проверка экранирования формул и спецсимволов при экспорте в Excel."""
    assert ExcelService.sanitize_cell_value("\tcalc") == "'\tcalc"
    assert ExcelService.sanitize_cell_value("\rtest") == "'\rtest"
    assert ExcelService.sanitize_cell_value("=1+1") == "'=1+1"
    assert ExcelService.sanitize_cell_value("+cmd") == "'+cmd"
    assert ExcelService.sanitize_cell_value("-123") == "'-123"
    assert ExcelService.sanitize_cell_value("@SUM(A1)") == "'@SUM(A1)"
    assert ExcelService.sanitize_cell_value("   =SUM(B2)") == "'   =SUM(B2)"
    assert ExcelService.sanitize_cell_value("Normal host") == "Normal host"


def test_storage_scalar_types_validation(tmp_path):
    """Проверка валидации скалярных типов конфигурации config.json."""
    storage = StorageManager(base_dir=str(tmp_path))
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps({
            "poll_interval": 12.5,
            "helpdesk_url": 42,
            "notifications_enabled": "false",
            "history_retention_days": "infinite"
        }),
        encoding="utf-8"
    )
    loaded = storage.load_config()
    assert type(loaded.poll_interval) is int and loaded.poll_interval == 10
    assert type(loaded.helpdesk_url) is str and loaded.helpdesk_url == ""
    assert type(loaded.notifications_enabled) is bool and loaded.notifications_enabled is True
    assert type(loaded.history_retention_days) is int and loaded.history_retention_days == 90


def test_export_import_manager_filter_removes_xls():
    """Диалог импорта не должен предлагать устаревший формат .xls."""
    from export_import_manager import ExportImportManager
    from unittest.mock import patch

    with patch("export_import_manager.QFileDialog.getOpenFileName") as mock_dialog:
        mock_dialog.return_value = ("", "")
        mgr = ExportImportManager(None, MagicMock())
        mgr.import_from_excel()
        assert mock_dialog.called
        filter_arg = mock_dialog.call_args[0][3]
        assert "*.xls " not in filter_arg and not filter_arg.endswith("*.xls)")
        assert "*.xlsx" in filter_arg
