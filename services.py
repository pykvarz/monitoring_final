#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервисы приложения
"""
import logging

try:
    from ping3 import ping
except ImportError:
    ping = None

try:
    from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QStyle
except ImportError:
    pass

from typing import List, Union, Optional

from models import AppConfig
from interfaces import INotificationService, IPingService


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
    """Сервис для выполнения ping-запросов (реализация через ping3)"""

    @staticmethod
    def ping_host(ip: str, timeout: float = 2.0) -> Optional[bool]:
        """Выполнение ping-запроса с фоллбэком на системный ping (без внутренних повторов)"""
        # 1. Попытка через ping3 (быстро, но требует прав)
        if ping:
            try:
                res = ping(ip, timeout=timeout)
                if isinstance(res, float):
                    return True
            except (OSError, ValueError, RuntimeError, PermissionError) as e:
                logging.warning(f"Ошибка ping3 {ip}: {e} (будет использован системный ping)")
        
        # 2. Фоллбэк на системный ping (работает всегда)
        if PingService._system_ping(ip, timeout):
            return True
            
        return False

    @staticmethod
    def _system_ping(host: str, timeout: float = 2.0) -> bool:
        import subprocess
        import platform
        
        is_windows = platform.system().lower() == 'windows'
        param = '-n' if is_windows else '-c'
        timeout_param = '-w' if is_windows else '-W'
        timeout_val = str(int(timeout * 1000)) if is_windows else str(max(1, int(round(timeout))))
        
        command = ['ping', param, '1', timeout_param, timeout_val, host]
        
        try:
            creationflags = 0
            if platform.system().lower() == 'windows':
                creationflags = 0x08000000  # CREATE_NO_WINDOW
                
            result = subprocess.run(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                text=True,
                timeout=timeout + 2.0
            )
            # Windows ping returns 0 even on "Request timed out". 
            # We must check for "TTL=" (English) or "TTL=" (Russian) to confirm a real reply.
            output = result.stdout.upper()
            if result.returncode == 0 and "TTL=" in output:
                return True
            return False
        except subprocess.TimeoutExpired:
            logging.debug(f"Таймаут системного ping для {host}")
            return False
        except Exception:
            return False