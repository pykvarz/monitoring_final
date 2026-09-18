#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервисы приложения
"""
import logging
import platform
import socket
import struct
import subprocess
from typing import List, Union, Optional

try:
    from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QStyle
except ImportError:
    pass

import ctypes

from models import AppConfig
from interfaces import INotificationService, IPingService


class IPV6_ADDRESS_EX(ctypes.Structure):
    _fields_ = [
        ("sin6_port", ctypes.c_ushort),
        ("sin6_flowinfo", ctypes.c_ulong),
        ("sin6_addr", ctypes.c_ushort * 8),
        ("sin6_scope_id", ctypes.c_ulong),
    ]


class ICMPV6_ECHO_REPLY(ctypes.Structure):
    _fields_ = [
        ("Address", IPV6_ADDRESS_EX),
        ("Status", ctypes.c_ulong),
        ("RoundTripTime", ctypes.c_uint),
    ]


_IS_WINDOWS = platform.system().lower() == 'windows'

if _IS_WINDOWS:
    from ctypes import wintypes

    try:
        _iphlpapi = ctypes.windll.iphlpapi

        # IPv4 ICMP Win32 API
        _IcmpCreateFile = _iphlpapi.IcmpCreateFile
        _IcmpCreateFile.argtypes = []
        _IcmpCreateFile.restype = wintypes.HANDLE

        _IcmpCloseHandle = _iphlpapi.IcmpCloseHandle
        _IcmpCloseHandle.argtypes = [wintypes.HANDLE]
        _IcmpCloseHandle.restype = wintypes.BOOL

        class _IP_OPTION_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('Ttl', wintypes.BYTE),
                ('Tos', wintypes.BYTE),
                ('Flags', wintypes.BYTE),
                ('OptionsSize', wintypes.BYTE),
                ('OptionsData', ctypes.c_void_p)
            ]

        class _ICMP_ECHO_REPLY(ctypes.Structure):
            _fields_ = [
                ('Address', wintypes.DWORD),
                ('Status', wintypes.ULONG),
                ('RoundTripTime', wintypes.ULONG),
                ('DataSize', wintypes.USHORT),
                ('Reserved', wintypes.USHORT),
                ('Data', ctypes.c_void_p),
                ('Options', _IP_OPTION_INFORMATION)
            ]

        _IcmpSendEcho = _iphlpapi.IcmpSendEcho
        _IcmpSendEcho.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPCVOID,
            wintypes.WORD,
            ctypes.c_void_p,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD
        ]
        _IcmpSendEcho.restype = wintypes.DWORD

        # IPv6 ICMP Win32 API
        _Icmp6CreateFile = getattr(_iphlpapi, 'Icmp6CreateFile', None)
        if _Icmp6CreateFile:
            _Icmp6CreateFile.argtypes = []
            _Icmp6CreateFile.restype = wintypes.HANDLE

        class _sockaddr_in6(ctypes.Structure):
            _fields_ = [
                ('sin6_family', ctypes.c_short),
                ('sin6_port', ctypes.c_ushort),
                ('sin6_flowinfo', ctypes.c_ulong),
                ('sin6_addr', ctypes.c_ubyte * 16),
                ('sin6_scope_id', ctypes.c_ulong),
            ]

        _Icmp6SendEcho2 = getattr(_iphlpapi, 'Icmp6SendEcho2', None)
        if _Icmp6SendEcho2:
            _Icmp6SendEcho2.argtypes = [
                wintypes.HANDLE,
                wintypes.HANDLE,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(_sockaddr_in6),
                ctypes.POINTER(_sockaddr_in6),
                wintypes.LPCVOID,
                wintypes.WORD,
                ctypes.c_void_p,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD
            ]
            _Icmp6SendEcho2.restype = wintypes.DWORD

        _WIN32_ICMP_AVAILABLE = True
    except Exception as e:
        logging.warning(f"Ошибка инициализации Win32 ICMP: {e}")
        _WIN32_ICMP_AVAILABLE = False
else:
    _WIN32_ICMP_AVAILABLE = False


class NotificationService(INotificationService):
    """Сервис отправки уведомлений (реализация через QSystemTrayIcon)"""
    
    _tray_icon = None

    @classmethod
    def _get_tray_icon(cls) -> Optional['QSystemTrayIcon']:
        if cls._tray_icon is None:
            app = QApplication.instance()
            if app and QSystemTrayIcon.isSystemTrayAvailable():
                cls._tray_icon = QSystemTrayIcon(app)
                if not app.windowIcon().isNull():
                    cls._tray_icon.setIcon(app.windowIcon())
                else:
                    cls._tray_icon.setIcon(app.style().standardIcon(QStyle.SP_DriveNetIcon))
                cls._tray_icon.show()
        return cls._tray_icon

    @staticmethod
    def notify_offline_hosts(hosts: List[str], config: AppConfig, show_tray: bool = True) -> None:
        """Отправка уведомлений об упавших узлах"""
        if not hosts or not config.notifications_enabled:
            return

        if len(hosts) <= 3:
            title = "Узел недоступен"
            message = "\n".join(hosts)
        else:
            title = "Несколько узлов недоступны"
            message = f"Недоступно устройств: {len(hosts)}"

        try:
            if config.sound_enabled:
                QApplication.beep()

            if show_tray:
                tray = NotificationService._get_tray_icon()
                if tray:
                    tray.showMessage(title, message, QSystemTrayIcon.Information, 5000)

        except Exception as e:
            logging.error(f"Ошибка отправки уведомления: {e}", exc_info=True)

    @staticmethod
    def notify_recovered_hosts(hosts: List[str], config: AppConfig, show_tray: bool = True) -> None:
        """Отправка уведомлений о восстановившихся узлах"""
        if not hosts or not config.notifications_enabled:
            return

        if len(hosts) <= 3:
            title = "Узел восстановлен"
            message = "\n".join(hosts)
        else:
            title = "Несколько узлов восстановлены"
            message = f"Восстановлено устройств: {len(hosts)}"

        try:
            if config.sound_enabled:
                QApplication.beep()

            if show_tray:
                tray = NotificationService._get_tray_icon()
                if tray:
                    tray.showMessage(title, message, QSystemTrayIcon.Information, 5000)

        except Exception as e:
            logging.error(f"Ошибка отправки уведомления: {e}", exc_info=True)
    
    @staticmethod
    def show_notification(title: str, message: str) -> None:
        """Показ системного уведомления"""
        try:
            tray = NotificationService._get_tray_icon()
            if tray:
                tray.showMessage(title, message, QSystemTrayIcon.Information, 5000)
        except Exception as e:
            logging.error(f"Ошибка показа уведомления: {e}", exc_info=True)


class PingService(IPingService):
    """
    Сервис для выполнения ping-запросов.
    На Windows использует нативный Win32 ICMP API (iphlpapi.dll) — работает in-process,
    не требует прав администратора и не порождает дочерних процессов ping.exe.
    Для Linux/macOS и в нештатных ситуациях используется системный фоллбэк.
    """

    @staticmethod
    def _win32_ping(host: str, timeout: float = 2.0) -> Optional[bool]:
        """
        Пинг через Win32 IcmpSendEcho (IPv4) или Icmp6SendEcho2 (IPv6).
        Возвращает:
          - True: получен ответ
          - False: хост недоступен / таймаут
          - None: не удалось разрешить имя хоста или Win32 сбой (фоллбэк на ping.exe)
        """
        if not _WIN32_ICMP_AVAILABLE:
            return None

        timeout_ms = max(100, int(timeout * 1000))

        try:
            addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except (socket.gaierror, OSError):
            return None

        if not addr_info:
            return None

        # Ищем IPv4 или IPv6
        target_info = None
        for info in addr_info:
            if info[0] == socket.AF_INET:
                target_info = info
                break
            elif info[0] == socket.AF_INET6 and not target_info:
                target_info = info

        if not target_info:
            return None

        family = target_info[0]

        # 1. IPv4: IcmpCreateFile + IcmpSendEcho
        if family == socket.AF_INET:
            ip_str = target_info[4][0]
            try:
                addr = struct.unpack('<I', socket.inet_aton(ip_str))[0]
            except Exception:
                return None

            handle = _IcmpCreateFile()
            if not handle or handle == wintypes.HANDLE(-1).value:
                return None
            try:
                data = b'NetMonPing'
                reply_size = ctypes.sizeof(_ICMP_ECHO_REPLY) + len(data) + 8
                reply_buffer = ctypes.create_string_buffer(reply_size)
                ret = _IcmpSendEcho(
                    handle,
                    addr,
                    data,
                    len(data),
                    None,
                    reply_buffer,
                    reply_size,
                    timeout_ms
                )
                if ret > 0:
                    reply = _ICMP_ECHO_REPLY.from_buffer_copy(reply_buffer)
                    return reply.Status == 0  # 0 = IP_SUCCESS
                return False
            finally:
                _IcmpCloseHandle(handle)

        # 2. IPv6: Icmp6CreateFile + Icmp6SendEcho2
        elif family == socket.AF_INET6 and _Icmp6CreateFile and _Icmp6SendEcho2:
            sockaddr = target_info[4]
            ip_str = sockaddr[0]
            try:
                dest = _sockaddr_in6()
                dest.sin6_family = socket.AF_INET6
                dest.sin6_port = 0
                dest.sin6_flowinfo = 0
                dest.sin6_scope_id = sockaddr[3] if len(sockaddr) > 3 else 0
                dest_bytes = socket.inet_pton(socket.AF_INET6, ip_str)
                dest.sin6_addr = (ctypes.c_ubyte * 16)(*dest_bytes)

                src = _sockaddr_in6()
                src.sin6_family = socket.AF_INET6

                handle = _Icmp6CreateFile()
                if not handle or handle == wintypes.HANDLE(-1).value:
                    return None
                try:
                    data = b'NetMonPing6'
                    reply_size = 1024
                    reply_buffer = ctypes.create_string_buffer(reply_size)
                    ret = _Icmp6SendEcho2(
                        handle,
                        None,
                        None,
                        None,
                        ctypes.byref(src),
                        ctypes.byref(dest),
                        data,
                        len(data),
                        None,
                        reply_buffer,
                        reply_size,
                        timeout_ms
                    )
                    if ret > 0:
                        # В структуре ICMPV6_ECHO_REPLY поле Status (ULONG) находится со смещением 28
                        # Address (IPV6_ADDRESS_EX, 28 байт) + Status (4 байта, 0 = IP_SUCCESS)
                        try:
                            reply = ICMPV6_ECHO_REPLY.from_buffer_copy(reply_buffer.raw)
                            return reply.Status == 0
                        except Exception:
                            return True
                    return False
                finally:
                    _IcmpCloseHandle(handle)
            except Exception as e:
                logging.debug(f"Ошибка Win32 IPv6 ICMP для {host}: {e}")
                return None

        return None

    @staticmethod
    def ping_host(ip: str, timeout: float = 2.0) -> Optional[bool]:
        """
        Выполнение ping-запроса через нативный Win32 ICMP API (in-process, без прав администратора),
        с автоматическим фоллбэком на системный ping.
        """
        # 1. Попытка через нативный Win32 ICMP API
        if _WIN32_ICMP_AVAILABLE:
            try:
                res = PingService._win32_ping(ip, timeout)
                if res is not None:
                    return res
            except Exception as e:
                logging.debug(f"Ошибка Win32 ICMP для {ip}: {e} (будет использован системный ping)")

        # 2. Фоллбэк на системный ping (при недоступности Win32 API или на Linux)
        if PingService._system_ping(ip, timeout):
            return True
            
        return False

    @staticmethod
    def _system_ping(host: str, timeout: float = 2.0) -> bool:
        """Системный ping через консольную утилиту ОС"""
        is_windows = platform.system().lower() == 'windows'
        param = '-n' if is_windows else '-c'
        timeout_param = '-w' if is_windows else '-W'
        timeout_val = str(int(timeout * 1000)) if is_windows else str(max(1, int(round(timeout))))
        
        command = ['ping', param, '1', timeout_param, timeout_val, host]
        
        try:
            creationflags = 0
            if is_windows:
                creationflags = 0x08000000  # CREATE_NO_WINDOW
                
            result = subprocess.run(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                text=True,
                timeout=timeout + 2.0
            )
            output = result.stdout.upper()
            if result.returncode == 0:
                if is_windows:
                    if "TTL=" in output:
                        return True
                    if "100%" not in output and ("TIME<" in output or "ВРЕМЯ<" in output or "0%" in output):
                        return True
                    return False
                return True
            return False
        except subprocess.TimeoutExpired:
            logging.debug(f"Таймаут системного ping для {host}")
            return False
        except Exception:
            return False