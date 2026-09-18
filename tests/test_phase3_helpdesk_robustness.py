#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для Этапа 3: Селекторы, валидация сохранения во фрейме и уведомления об ошибках очереди Helpdesk
"""

import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from PyQt5.QtWidgets import QApplication

from helpdesk_service import HelpdeskService
from models import AppConfig


class TestPhase3HelpdeskRobustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_find_form_context_does_not_mix_css_and_xpath(self):
        """
        Проверка: _find_form_context не должен объединять CSS и xpath= через запятую,
        чтобы Chromium/Edge не выбрасывали синтаксическую ошибку DOMException.
        """
        import inspect
        source = inspect.getsource(HelpdeskService._find_form_context)
        # Проверяем, что в вызовах locator нет объединения css и xpath= через запятую
        self.assertNotIn("xpath=//*", source.split("locator(")[1].split(")")[0] if "locator(" in source else "")

    def test_find_form_context_locates_iframe(self):
        """Проверка успешного нахождения формы во фрейме с раздельным поиском"""
        async def _run_test():
            mock_page = MagicMock()
            mock_frame = MagicMock()
            mock_page.frames = [mock_frame]

            # На page маркеров нет
            mock_page_locator = MagicMock()
            mock_page_locator.first = MagicMock()
            mock_page_locator.first.count = AsyncMock(return_value=0)
            mock_page_locator.first.is_visible = AsyncMock(return_value=False)
            mock_page.locator.return_value = mock_page_locator

            # Во фрейме маркер найден
            mock_frame_locator = MagicMock()
            mock_frame_locator.first = MagicMock()
            mock_frame_locator.first.count = AsyncMock(return_value=1)
            mock_frame_locator.first.is_visible = AsyncMock(return_value=True)
            mock_frame.locator.return_value = mock_frame_locator

            ctx = await HelpdeskService._find_form_context(mock_page)
            self.assertEqual(ctx, mock_frame)

        asyncio.run(_run_test())

    def test_log_future_error_emits_ticket_failed_signal(self):
        """
        Проверка: callback _log_future_error при ошибке/таймауте корутины
        гарантированно эмитит сигнал ticket_failed с текстом ошибки.
        """
        signal_received = []

        def _on_failed(host, action, err):
            signal_received.append((host, action, err))

        HelpdeskService.signals.ticket_failed.connect(_on_failed)
        try:
            future = MagicMock()
            future.result.side_effect = asyncio.TimeoutError("Таймаут ожидания в очереди")
            
            HelpdeskService._log_future_error(future, "1234", "Установить")
            # Извлекаем коллбек, добавленный в future
            callback = future.add_done_callback.call_args[0][0]
            callback(future)

            self.assertEqual(len(signal_received), 1)
            self.assertEqual(signal_received[0][0], "1234")
            self.assertEqual(signal_received[0][1], "Установить")
            self.assertIn("Таймаут", signal_received[0][2])
        finally:
            HelpdeskService.signals.ticket_failed.disconnect(_on_failed)

    def test_detached_form_frame_counts_as_closed(self):
        """Удалённый после сохранения iframe означает, что форма закрылась успешно."""
        async def _run_test():
            frame = MagicMock()
            marker = MagicMock()
            marker.first = marker
            marker.wait_for = AsyncMock(side_effect=RuntimeError("Frame was detached"))
            frame.locator.return_value = marker
            frame.is_detached.return_value = True

            closed = await HelpdeskService._wait_for_form_closed(frame)

            self.assertTrue(closed)

        asyncio.run(_run_test())

    def test_ticket_timeout_starts_after_semaphore_is_acquired(self):
        """Зависшая браузерная сессия ограничена таймаутом и освобождает очередь."""
        async def _run_test():
            started = asyncio.Event()
            stopped = asyncio.Event()
            failures = []
            playwright = MagicMock()

            async def stop_playwright():
                stopped.set()

            playwright.stop = AsyncMock(side_effect=stop_playwright)

            async def hanging_session(*args, **kwargs):
                kwargs["browser_holder"]["playwright"] = playwright
                started.set()
                await stopped.wait()

            def on_failed(host, action, error):
                failures.append((host, action, error))

            previous_semaphore = HelpdeskService._semaphore
            HelpdeskService.signals.ticket_failed.connect(on_failed)
            try:
                HelpdeskService._semaphore = asyncio.Semaphore(1)
                with patch.object(HelpdeskService, "TICKET_TIMEOUT_SECONDS", 0.01), \
                     patch.object(HelpdeskService, "_process_ticket_session_async", side_effect=hanging_session):
                    await HelpdeskService._semaphore.acquire()
                    task = asyncio.create_task(
                        HelpdeskService._process_ticket_task_async(
                            "https://helpdesk.invalid", "1234", "Установить", headless=True
                        )
                    )
                    await asyncio.sleep(0.03)
                    self.assertFalse(task.done())
                    HelpdeskService._semaphore.release()

                    await task

                self.assertTrue(started.is_set())
                self.assertTrue(stopped.is_set())
                self.assertEqual(len(failures), 1)
                self.assertIn("таймаут", failures[0][2].lower())
                self.assertFalse(HelpdeskService._get_semaphore().locked())
            finally:
                HelpdeskService.signals.ticket_failed.disconnect(on_failed)
                HelpdeskService._semaphore = previous_semaphore

        asyncio.run(_run_test())

    def test_browser_cleanup_error_does_not_change_ticket_outcome(self):
        """Ошибка закрытия браузера после результата заявки не выходит из task wrapper."""
        async def _run_test():
            browser = MagicMock()
            browser.close = AsyncMock(side_effect=RuntimeError("close failed"))

            async def successful_session(*args, **kwargs):
                kwargs["browser_holder"]["browser"] = browser

            previous_semaphore = HelpdeskService._semaphore
            try:
                HelpdeskService._semaphore = asyncio.Semaphore(1)
                with patch.object(
                    HelpdeskService,
                    "_process_ticket_session_async",
                    side_effect=successful_session,
                ):
                    await HelpdeskService._process_ticket_task_async(
                        "https://helpdesk.invalid", "1234", "Установить", headless=True
                    )
            finally:
                HelpdeskService._semaphore = previous_semaphore

            browser.close.assert_awaited_once()

        asyncio.run(_run_test())

    def test_confirmed_ticket_is_not_converted_to_timeout(self):
        """Таймаут очистки после ticket_created не создаёт второй terminal result."""
        async def _run_test():
            stopped = asyncio.Event()
            playwright = MagicMock()

            async def stop_playwright():
                stopped.set()

            playwright.stop = AsyncMock(side_effect=stop_playwright)

            async def confirmed_then_hanging_session(*args, **kwargs):
                kwargs["browser_holder"]["terminal_emitted"] = True
                kwargs["browser_holder"]["playwright"] = playwright
                await stopped.wait()

            previous_semaphore = HelpdeskService._semaphore
            try:
                HelpdeskService._semaphore = asyncio.Semaphore(1)
                with patch.object(HelpdeskService, "TICKET_TIMEOUT_SECONDS", 0.01), \
                     patch.object(
                         HelpdeskService,
                         "_process_ticket_session_async",
                         side_effect=confirmed_then_hanging_session,
                     ):
                    await HelpdeskService._process_ticket_task_async(
                        "https://helpdesk.invalid", "1234", "Установить", headless=True
                    )
            finally:
                HelpdeskService._semaphore = previous_semaphore

        asyncio.run(_run_test())

    def test_cancelled_wrapper_holds_semaphore_until_session_stops(self):
        """Внешняя отмена не запускает вторую сессию до завершения cleanup."""
        async def _run_test():
            started = asyncio.Event()
            stop_started = asyncio.Event()
            allow_stop = asyncio.Event()
            stopped = asyncio.Event()
            playwright = MagicMock()

            async def stop_playwright():
                stop_started.set()
                await allow_stop.wait()
                stopped.set()

            playwright.stop = AsyncMock(side_effect=stop_playwright)

            async def session(*args, **kwargs):
                kwargs["browser_holder"]["playwright"] = playwright
                started.set()
                await stopped.wait()

            previous_semaphore = HelpdeskService._semaphore
            try:
                HelpdeskService._semaphore = asyncio.Semaphore(1)
                with patch.object(
                    HelpdeskService,
                    "_process_ticket_session_async",
                    side_effect=session,
                ):
                    task = asyncio.create_task(
                        HelpdeskService._process_ticket_task_async(
                            "https://helpdesk.invalid", "1234", "Установить", headless=True
                        )
                    )
                    await started.wait()
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

                    await stop_started.wait()
                    self.assertTrue(HelpdeskService._get_semaphore().locked())
                    allow_stop.set()
                    for _ in range(20):
                        if not HelpdeskService._get_semaphore().locked():
                            break
                        await asyncio.sleep(0.01)
                    self.assertFalse(HelpdeskService._get_semaphore().locked())
            finally:
                HelpdeskService._semaphore = previous_semaphore

        asyncio.run(_run_test())

    def test_shutdown_does_not_start_queued_session(self):
        """Graceful shutdown отменяет очередь до запуска второй Playwright-сессии."""
        async def _run_test():
            started = []
            stopped = asyncio.Event()
            playwright = MagicMock()

            async def stop_playwright():
                stopped.set()

            playwright.stop = AsyncMock(side_effect=stop_playwright)

            async def session(*args, **kwargs):
                started.append(args[1])
                kwargs["browser_holder"]["playwright"] = playwright
                await stopped.wait()

            previous_semaphore = HelpdeskService._semaphore
            previous_shutdown = HelpdeskService._shutting_down
            try:
                HelpdeskService._semaphore = asyncio.Semaphore(1)
                HelpdeskService._shutting_down = False
                with patch.object(
                    HelpdeskService,
                    "_process_ticket_session_async",
                    side_effect=session,
                ):
                    active = asyncio.create_task(
                        HelpdeskService._process_ticket_task_async(
                            "https://helpdesk.invalid", "first", "Установить", headless=True
                        )
                    )
                    while not started:
                        await asyncio.sleep(0)
                    queued = asyncio.create_task(
                        HelpdeskService._process_ticket_task_async(
                            "https://helpdesk.invalid", "second", "Установить", headless=True
                        )
                    )
                    await asyncio.sleep(0)

                    HelpdeskService._shutting_down = True
                    await HelpdeskService._graceful_shutdown()
                    await asyncio.gather(active, queued, return_exceptions=True)

                self.assertEqual(started, ["first"])
            finally:
                HelpdeskService._shutting_down = previous_shutdown
                HelpdeskService._semaphore = previous_semaphore

        asyncio.run(_run_test())
