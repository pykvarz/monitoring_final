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
