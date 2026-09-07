#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для модуля всплывающих уведомлений ToastNotification и ToastManager.
"""

import unittest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication, QWidget

from toast_notification import ToastNotification, ToastManager, ToastType


class TestToastNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.manager = ToastManager(self.parent, get_theme_fn=lambda: "dark")

    def tearDown(self):
        self.parent.deleteLater()

    def test_create_offline_toast(self):
        """Создание уведомления об упавших узлах"""
        toast = ToastNotification(
            parent=self.parent,
            toast_type=ToastType.OFFLINE,
            title="⚠️ Узел недоступен",
            hosts=["Server-01", "Server-02"],
            theme="dark"
        )
        self.assertEqual(toast._toast_type, ToastType.OFFLINE)
        self.assertEqual(len(toast._hosts), 2)
        toast.deleteLater()

    def test_create_recovered_toast(self):
        """Создание уведомления о восстановившихся узлах"""
        toast = ToastNotification(
            parent=self.parent,
            toast_type=ToastType.RECOVERED,
            title="✅ Узел восстановлен",
            hosts=["Server-01"],
            theme="light"
        )
        self.assertEqual(toast._toast_type, ToastType.RECOVERED)
        toast.deleteLater()

    def test_manager_show_offline(self):
        """Проверка добавления в стек через ToastManager"""
        self.manager.show_offline(["HostA", "HostB"])
        self.assertEqual(len(self.manager._active_toasts), 1)
        toast = self.manager._active_toasts[0]
        self.assertEqual(toast._toast_type, ToastType.OFFLINE)

    def test_manager_show_recovered(self):
        """Проверка показа восстановления через ToastManager"""
        self.manager.show_recovered(["HostA"])
        self.assertEqual(len(self.manager._active_toasts), 1)
        toast = self.manager._active_toasts[0]
        self.assertEqual(toast._toast_type, ToastType.RECOVERED)

    def test_manager_show_pause(self):
        """Проверка показа паузы и возобновления через ToastManager"""
        self.manager.show_pause(is_paused=True)
        self.assertEqual(len(self.manager._active_toasts), 1)
        toast = self.manager._active_toasts[0]
        self.assertEqual(toast._toast_type, ToastType.WARNING)

        self.manager.show_pause(is_paused=False)
        self.assertEqual(len(self.manager._active_toasts), 2)
        toast2 = self.manager._active_toasts[1]
        self.assertEqual(toast2._toast_type, ToastType.INFO)

    def test_manager_max_toasts_limit(self):
        """Проверка ограничения на максимальное число одновременных тостов"""
        for i in range(10):
            self.manager.show_info(f"Title {i}", f"Message {i}")
        self.assertLessEqual(len(self.manager._active_toasts), self.manager._max_toasts)


if __name__ == '__main__':
    unittest.main()
