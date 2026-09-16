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


if __name__ == '__main__':
    unittest.main()

