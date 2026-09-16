#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for helpdesk_service.py
"""

import unittest
from helpdesk_service import HelpdeskService


class TestHelpdeskServiceFormatting(unittest.TestCase):
    """Тестирование форматирования номеров банкоматов для Helpdesk."""

    def test_format_atm_number_adds_0000_prefix(self):
        """Проверка добавления префикса 0000 к номеру."""
        self.assertEqual(HelpdeskService.format_atm_number("1234"), "00001234")
        self.assertEqual(HelpdeskService.format_atm_number("42"), "000042")
        self.assertEqual(HelpdeskService.format_atm_number("ATM_99"), "0000ATM_99")

    def test_format_atm_number_no_duplicate_prefix(self):
        """Проверка защиты от повторного добавления 0000."""
        self.assertEqual(HelpdeskService.format_atm_number("00001234"), "00001234")
        self.assertEqual(HelpdeskService.format_atm_number("0000"), "0000")
        self.assertEqual(HelpdeskService.format_atm_number("0000_ATM"), "0000_ATM")

    def test_format_atm_number_handles_whitespace(self):
        """Проверка обрезки пробелов."""
        self.assertEqual(HelpdeskService.format_atm_number("  1234  "), "00001234")
        self.assertEqual(HelpdeskService.format_atm_number("  00005678  "), "00005678")

    def test_format_atm_number_empty_or_none(self):
        """Проверка пустых значений."""
        self.assertEqual(HelpdeskService.format_atm_number(""), "")
        self.assertEqual(HelpdeskService.format_atm_number("   "), "")
        self.assertEqual(HelpdeskService.format_atm_number(None), "")



class TestHelpdeskServiceUrlAndSelectors(unittest.TestCase):
    """Тестирование нормализации URL и селекторов кнопок Helpdesk."""

    def test_normalize_url_adds_https(self):
        """Проверка авто-добавления https:// к URL без схемы."""
        raw = "helpdesk.eub.kz/sd/operator/#add:serviceCall$request"
        normalized = HelpdeskService.normalize_url(raw)
        self.assertEqual(normalized, "https://helpdesk.eub.kz/sd/operator/#add:serviceCall$request")

    def test_normalize_url_preserves_existing_https(self):
        """Проверка сохранения уже существующей схемы https://."""
        raw = "https://helpdesk.eub.kz/sd/operator/"
        self.assertEqual(HelpdeskService.normalize_url(raw), "https://helpdesk.eub.kz/sd/operator/")

    def test_normalize_url_handles_empty(self):
        """Проверка обработки пустых значений."""
        self.assertEqual(HelpdeskService.normalize_url(""), "")
        self.assertEqual(HelpdeskService.normalize_url("   "), "")
        self.assertEqual(HelpdeskService.normalize_url(None), "")

    def test_save_button_selector_contains_gwt_debug_apply(self):
        """Проверка наличия точного идентификатора gwt-debug-apply в селекторе."""
        self.assertIn("#gwt-debug-apply", HelpdeskService.SAVE_BUTTON_SELECTOR)
        self.assertIn("g-button", HelpdeskService.SAVE_BUTTON_SELECTOR)

    def test_process_offline_with_headless_config(self):
        """Проверка передачи флага headless в process_offline/recovered."""
        from models import AppConfig
        config = AppConfig(helpdesk_enabled=False, helpdesk_headless=True)
        HelpdeskService.process_offline(["test_host"], config)
        config.helpdesk_headless = False
        HelpdeskService.process_recovered(["test_host"], config)


class TestSettingsDialogHelpdeskHeadless(unittest.TestCase):
    """Тестирование переключателя headless в SettingsDialog."""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_dialog_loads_and_saves_headless(self):
        from dialogs import SettingsDialog
        from models import AppConfig

        # 1. По умолчанию False
        cfg = AppConfig(helpdesk_headless=False)
        dlg = SettingsDialog(None, cfg)
        self.assertFalse(dlg._hd_headless.isChecked())
        saved_cfg = dlg.get_config()
        self.assertFalse(saved_cfg.helpdesk_headless)

        # 2. Если включено True
        cfg_true = AppConfig(helpdesk_headless=True)
        dlg_true = SettingsDialog(None, cfg_true)
        self.assertTrue(dlg_true._hd_headless.isChecked())
        saved_cfg_true = dlg_true.get_config()
        self.assertTrue(saved_cfg_true.helpdesk_headless)


if __name__ == '__main__':
    unittest.main()


