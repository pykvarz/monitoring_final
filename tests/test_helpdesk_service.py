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


if __name__ == '__main__':
    unittest.main()
