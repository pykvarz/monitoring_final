import unittest
from unittest.mock import MagicMock
import sys
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import AppConfig
from history_views import EventLogPanel, FloatingEventLogWindow
import constants


class TestFloatingEventLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_app_config_floating_fields(self):
        """Проверка наличия полей плавающего окна в AppConfig"""
        config = AppConfig()
        self.assertFalse(config.event_log_floating)
        self.assertTrue(config.event_log_on_top)
        self.assertEqual(config.event_log_geometry, [])

    def test_svg_popout_and_pin_icons(self):
        """Проверка генерации SVG-иконок для открепления и закрепления"""
        svg_popout = constants.get_svg_popout("dark")
        svg_dock = constants.get_svg_dock("dark")
        svg_pin = constants.get_svg_pin("dark", pinned=True)
        self.assertIn("<svg", svg_popout)
        self.assertIn("<svg", svg_dock)
        self.assertIn("<svg", svg_pin)

    def test_event_log_panel_dock_buttons(self):
        """Проверка кнопок открепления и закрепления в панели EventLogPanel"""
        mock_repo = MagicMock()
        panel = EventLogPanel(repository=mock_repo, theme="dark")
        self.assertIsNotNone(panel._btn_dock)
        self.assertIsNotNone(panel._btn_pin)
        self.assertFalse(panel.is_floating)
        self.assertFalse(panel._btn_pin.isVisible())

        # Переключаем в плавающий режим
        panel.set_floating_mode(True, is_pinned=True)
        self.assertTrue(panel.is_floating)
        self.assertFalse(panel._btn_pin.isHidden())

        # Возвращаем в прикрепленный режим
        panel.set_floating_mode(False)
        self.assertFalse(panel.is_floating)
        self.assertTrue(panel._btn_pin.isHidden())

    def test_floating_event_log_window_docking_cycle(self):
        """Проверка жизненного цикла открепления и возврата панели в FloatingEventLogWindow"""
        mock_repo = MagicMock()
        panel = EventLogPanel(repository=mock_repo, theme="dark")
        floating_win = FloatingEventLogWindow(parent=None, theme="dark")

        # Прикрепляем панель в плавающее окно
        floating_win.set_panel(panel)
        self.assertEqual(floating_win.current_panel(), panel)
        self.assertEqual(panel.parent(), floating_win)

        # Проверяем Always on Top
        floating_win.set_on_top(True)
        self.assertTrue(bool(floating_win.windowFlags() & Qt.WindowStaysOnTopHint))

        floating_win.set_on_top(False)
        self.assertFalse(bool(floating_win.windowFlags() & Qt.WindowStaysOnTopHint))

        # Забираем панель обратно
        taken = floating_win.take_panel()
        self.assertEqual(taken, panel)
        self.assertIsNone(floating_win.current_panel())

    def test_floating_window_close_emits_dock_requested(self):
        """Проверка, что закрытие плавающего окна эмитит сигнал dock_requested"""
        floating_win = FloatingEventLogWindow(parent=None, theme="dark")
        signal_mock = MagicMock()
        floating_win.dock_requested.connect(signal_mock)
        floating_win.close()
        signal_mock.assert_called_once()

    def test_floating_window_set_theme(self):
        """Проверка смены темы плавающего окна"""
        mock_repo = MagicMock()
        panel = EventLogPanel(repository=mock_repo, theme="dark")
        floating_win = FloatingEventLogWindow(parent=None, theme="dark")
        floating_win.set_panel(panel)
        floating_win.set_theme("tactical")
        self.assertEqual(floating_win._theme, "tactical")
        self.assertEqual(panel._theme, "tactical")
