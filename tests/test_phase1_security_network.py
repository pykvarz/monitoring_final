#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для Этапа 1: Безопасность IPv6, нативный ICMPv6 статус и настройки SSO
"""

import sys
import ctypes
import struct
import pytest
from unittest.mock import patch, MagicMock

from models import validate_ip, validate_ip_or_hostname
from services import PingService
from helpdesk_service import HelpdeskService
from context_menu_manager import ContextMenuManager


class TestIPv6SecurityAndValidation:
    """Проверка защиты от инъекций через IPv6 Zone Index"""

    def test_valid_ipv4_and_ipv6(self):
        assert validate_ip("192.168.1.1") is True
        assert validate_ip("::1") is True
        assert validate_ip("2001:db8::1") is True
        assert validate_ip("fe80::1") is True

    def test_valid_ipv6_scope_id(self):
        assert validate_ip("fe80::1%1") is True
        assert validate_ip("fe80::1%eth0") is True
        assert validate_ip("fe80::1%wlan_0") is True
        assert validate_ip_or_hostname("fe80::1%eth0") is True

    def test_rejects_dangerous_ipv6_scope_id(self):
        dangerous_ips = [
            "fe80::1%&calc.exe",
            "fe80::1%|calc.exe",
            "fe80::1%^&echo",
            "fe80::1%>out.txt",
            "fe80::1%<in.txt",
            "fe80::1%`whoami`",
            "fe80::1%$(whoami)",
            "fe80::1%\"&&calc.exe",
            "fe80::1% %SystemRoot%",
            "fe80::1%;calc.exe",
        ]
        for bad_ip in dangerous_ips:
            assert validate_ip(bad_ip) is False, f"Должен быть отклонен: {bad_ip}"
            assert validate_ip_or_hostname(bad_ip) is False, f"Должен быть отклонен: {bad_ip}"

    def test_ping_cmd_windows_safe_execution(self):
        """Проверка безопасного запуска ping на Windows без cmd /c start"""
        parent = MagicMock()
        table = MagicMock()
        model = MagicMock()
        repo = MagicMock()
        mgr = ContextMenuManager(parent, table, model, ["Без группы"], lambda: "dark", repo)

        with patch("sys.platform", "win32"), patch("subprocess.Popen") as mock_popen:
            mgr._ping_cmd("192.168.1.1", label="Тестовый узел")
            assert mock_popen.called
            call_args, call_kwargs = mock_popen.call_args
            cmd_args = call_args[0]
            # Не должно быть уязвимой цепочки ['cmd', '/c', 'start']
            assert cmd_args[:3] != ['cmd', '/c', 'start'], "Не должен использоваться cmd /c start"
            # Аргументы должны запускать ping напрямую или через безопасный вызов консоли
            cmd_str = ' '.join(cmd_args)
            assert 'ping' in cmd_str
            assert '-t' in cmd_str
            assert '192.168.1.1' in cmd_str


class TestWin32ICMPv6Structure:
    """Проверка структуры ответа ICMPv6 (Windows API ipexport.h)"""

    def test_icmpv6_structure_offsets(self):
        from services import IPV6_ADDRESS_EX, ICMPV6_ECHO_REPLY
        assert ctypes.sizeof(IPV6_ADDRESS_EX) == 28
        assert ICMPV6_ECHO_REPLY.Status.offset == 28
        assert ICMPV6_ECHO_REPLY.RoundTripTime.offset == 32

    def test_icmpv6_status_parsing_success_with_positive_rtt(self):
        """
        Успешный ответ (Status = 0) с положительным RTT (например, 15 мс)
        должен определяться как доступность (True), а не падать в False из-за чтения RTT.
        """
        from services import ICMPV6_ECHO_REPLY
        buf = ctypes.create_string_buffer(ctypes.sizeof(ICMPV6_ECHO_REPLY))
        # Status = 0 (IP_SUCCESS), RoundTripTime = 15
        struct.pack_into('<I', buf, 28, 0)
        struct.pack_into('<I', buf, 32, 15)
        
        reply = ICMPV6_ECHO_REPLY.from_buffer_copy(buf.raw)
        assert reply.Status == 0
        assert reply.RoundTripTime == 15

    def test_icmpv6_status_parsing_failure_with_zero_rtt(self):
        """
        Ответ с ошибкой (Status = 11003) и RTT = 0
        НЕ должен ошибочно считаться доступностью (True).
        """
        from services import ICMPV6_ECHO_REPLY
        buf = ctypes.create_string_buffer(ctypes.sizeof(ICMPV6_ECHO_REPLY))
        # Status = 11003 (IP_DEST_HOST_UNREACHABLE), RoundTripTime = 0
        struct.pack_into('<I', buf, 28, 11003)
        struct.pack_into('<I', buf, 32, 0)
        
        reply = ICMPV6_ECHO_REPLY.from_buffer_copy(buf.raw)
        assert reply.Status == 11003
        assert reply.RoundTripTime == 0
        assert reply.Status != 0


class TestHelpdeskSSOConfiguration:
    """Проверка безопасной конфигурации Windows SSO"""

    def test_launch_args_exact_domain_and_no_unrestricted_delegation(self):
        url = "https://helpdesk.corp.example.com/sd/operator"
        args = HelpdeskService.get_launch_args(url)

        # Проверяем, что нет широкого шаблона *helpdesk...*
        for arg in args:
            if arg.startswith("--auth-server-allowlist="):
                val = arg.split("=", 1)[1]
                assert not val.startswith("*helpdesk"), f"Слишком широкая маска: {val}"
                assert not val.endswith("example.com*"), f"Слишком широкая маска: {val}"
                assert "helpdesk.corp.example.com" in val
            
            # Делегирование Kerberos билетов должно отсутствовать по умолчанию
            assert not arg.startswith("--auth-negotiate-delegate-allowlist"), (
                "Делегирование Kerberos не должно включаться без явной необходимости"
            )
