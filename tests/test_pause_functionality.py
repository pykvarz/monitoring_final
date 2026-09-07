#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты функциональности паузы мониторинга.
"""

import unittest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject

from monitor_thread import MonitorThread
from models import AppConfig


class TestPauseFunctionality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_config = AppConfig(poll_interval=1, max_workers=2)
        self.thread = MonitorThread(self.mock_repo, self.mock_config)

    def tearDown(self):
        self.thread.stop()

    def test_initial_pause_state(self):
        """По умолчанию поток мониторинга не на паузе"""
        self.assertFalse(self.thread.is_paused())

    def test_pause_and_resume(self):
        """Проверка методов pause() и resume()"""
        signal_mock = MagicMock()
        self.thread.paused_state_changed.connect(signal_mock)

        self.thread.pause()
        self.assertTrue(self.thread.is_paused())
        signal_mock.assert_called_with(True)

        self.thread.resume()
        self.assertFalse(self.thread.is_paused())
        signal_mock.assert_called_with(False)

    def test_toggle_pause(self):
        """Проверка toggle_pause()"""
        # 1-й вызов -> пауза
        result1 = self.thread.toggle_pause()
        self.assertTrue(result1)
        self.assertTrue(self.thread.is_paused())

        # 2-й вызов -> возобновление
        result2 = self.thread.toggle_pause()
        self.assertFalse(result2)
        self.assertFalse(self.thread.is_paused())


if __name__ == '__main__':
    unittest.main()
