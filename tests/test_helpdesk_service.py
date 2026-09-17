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

    def test_error_screenshot_path_in_temp(self):
        """Проверка генерации пути скриншота ошибки во временной папке tempfile."""
        import tempfile, os
        path = HelpdeskService._get_error_screenshot_path("ATM-01 & test")
        self.assertTrue(path.startswith(tempfile.gettempdir()))
        self.assertIn("helpdesk_error_ATM-01___test.png", path)


class TestHelpdeskLaunchArgs(unittest.TestCase):
    """Тестирование формирования аргументов браузера для Windows SSO / NTLM / Kerberos."""

    def test_launch_args_no_quotes_and_contains_auth_flags(self):
        """Проверка отсутствия кавычек в флагах авторизации и наличия NTLM/Kerberos параметров."""
        args = HelpdeskService.get_launch_args("https://helpdesk.eub.kz/sd/operator/#add:serviceCall$request")

        # 1. Ни в одном аргументе не должно быть двойных кавычек
        for arg in args:
            self.assertNotIn('"', arg, f"Аргумент содержит двойные кавычки: {arg}")

        # 2. Должен быть правильный auth-server-allowlist без кавычек
        self.assertIn("--auth-server-allowlist=*helpdesk.eub.kz*", args)

        # 3. Должно быть делегирование Kerberos
        self.assertIn("--auth-negotiate-delegate-allowlist=*helpdesk.eub.kz*", args)

        # 4. Должны быть схемы авторизации
        self.assertIn("--auth-schemes=basic,digest,ntlm,negotiate", args)

        # 5. Скрытие автоматизации
        self.assertIn("--disable-blink-features=AutomationControlled", args)

    def test_launch_args_handles_ports_and_paths(self):
        """Проверка извлечения чистого домена при наличии порта."""
        args = HelpdeskService.get_launch_args("http://hd.company.local:8080/sd/")
        self.assertIn("--auth-server-allowlist=*hd.company.local*", args)
        self.assertIn("--auth-negotiate-delegate-allowlist=*hd.company.local*", args)

    def test_launch_args_fallback_on_empty_url(self):
        """Проверка формирования аргументов при пустом или некорректном URL."""
        args = HelpdeskService.get_launch_args("")
        self.assertIn("--auth-schemes=basic,digest,ntlm,negotiate", args)
        self.assertIn("--disable-blink-features=AutomationControlled", args)



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


class TestHelpdeskXPathEscape(unittest.TestCase):
    """Тестирование экранирования XPath (MED-1)."""

    def test_simple_string_single_quotes(self):
        """Обычная строка без кавычек — оборачивается в одинарные."""
        result = HelpdeskService._xpath_escape("Местонахождение")
        self.assertEqual(result, "'Местонахождение'")

    def test_string_with_single_quote_uses_double(self):
        """Строка с одинарной кавычкой, но без двойных — оборачивается в двойные."""
        result = HelpdeskService._xpath_escape("it's a test")
        self.assertEqual(result, '"it\'s a test"')

    def test_string_with_both_quotes_uses_concat(self):
        """Строка с обоими типами кавычек — используется concat()."""
        result = HelpdeskService._xpath_escape("it's a \"test\"")
        self.assertIn("concat(", result)


    def test_string_with_double_quote_uses_single(self):
        """Строка с двойными кавычками, но без одинарных — одинарные обёртки."""
        result = HelpdeskService._xpath_escape('say "hello"')
        self.assertEqual(result, "'say \"hello\"'")

    def test_empty_string(self):
        """Пустая строка."""
        result = HelpdeskService._xpath_escape("")
        self.assertEqual(result, "''")


class TestHelpdeskFormMethodsMock(unittest.IsolatedAsyncioTestCase):
    """Тестирование методов заполнения формы с mock Playwright (INFO-1)."""

    def _make_locator(self, count=1, visible=True):
        """Создаёт mock Locator с нужным поведением."""
        from unittest.mock import AsyncMock, MagicMock, PropertyMock
        loc = AsyncMock()
        loc.count = AsyncMock(return_value=count)
        loc.is_visible = AsyncMock(return_value=visible)
        loc.first = loc
        loc.last = loc
        loc.scroll_into_view_if_needed = AsyncMock()
        loc.click = AsyncMock()
        loc.fill = AsyncMock()
        loc.press = AsyncMock()
        loc.press_sequentially = AsyncMock()
        loc.get_attribute = AsyncMock(return_value=None)
        loc.wait_for = AsyncMock()
        loc.locator = MagicMock(return_value=loc)
        loc.get_by_text = MagicMock(return_value=loc)
        return loc

    def _make_page(self, locator_count=1, visible=True):
        from unittest.mock import AsyncMock, MagicMock
        loc = self._make_locator(count=locator_count, visible=visible)
        page = MagicMock()
        page.locator = MagicMock(return_value=loc)
        page.get_by_text = MagicMock(return_value=loc)
        page.wait_for_timeout = AsyncMock()
        page.frames = []
        return page, loc

    async def test_fill_field_by_gwt_id_success(self):
        """Заполнение поля по gwt-debug ID — возвращает True."""
        page, loc = self._make_page(locator_count=1, visible=True)
        result = await HelpdeskService._fill_field(page, page, "gwt-debug-location-value", "Местонахождение", "00001234")
        self.assertTrue(result)
        loc.fill.assert_called()

    async def test_fill_field_not_found_returns_false(self):
        """Поле не найдено ни по ID, ни по метке — возвращает False."""
        page, loc = self._make_page(locator_count=0, visible=False)
        result = await HelpdeskService._fill_field(page, page, "nonexistent-id", "НесуществующееПоле", "value")
        self.assertFalse(result)

    async def test_select_dropdown_trigger_found_and_option_clicked(self):
        """Dropdown триггер найден, опция найдена и кликнута."""
        page, loc = self._make_page(locator_count=1, visible=True)
        result = await HelpdeskService._select_dropdown(page, page, "gwt-debug-servCategory-value", "Категория услуги", "ATM")
        self.assertTrue(result)

    async def test_select_dropdown_trigger_not_found(self):
        """Dropdown триггер не найден — возвращает False."""
        page, loc = self._make_page(locator_count=0, visible=False)
        result = await HelpdeskService._select_dropdown(page, page, "nonexistent", "Нет", "Нет")
        self.assertFalse(result)

    async def test_fill_description_by_id(self):
        """Заполнение описания по gwt-debug ID."""
        page, loc = self._make_page(locator_count=1, visible=True)
        result = await HelpdeskService._fill_description(page, page, "Тестовое описание")
        self.assertTrue(result)
        loc.fill.assert_called_with("Тестовое описание")


if __name__ == '__main__':
    unittest.main()
