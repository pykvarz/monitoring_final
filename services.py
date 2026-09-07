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
    from plyer import notification
    # Explicit import to force PyInstaller to bundle the Windows implementation
    import sys
    if sys.platform == 'win32':
        import plyer.platforms.win.notification
except ImportError:
    notification = None

from PyQt5.QtWidgets import QApplication
from typing import List, Union, Optional

from models import AppConfig
from interfaces import INotificationService, IPingService


class NotificationService(INotificationService):
    """Сервис отправки уведомлений (реализация через plyer)"""

    @staticmethod
    def notify_offline_hosts(hosts: List[str], config: AppConfig) -> None:
        """Отправка уведомлений об упавших узлах"""
        if not hosts or not config.notifications_enabled or not notification:
            return

        if len(hosts) <= 3:
            title = "⚠️ Узел недоступен"
            message = "\n".join(hosts)
        else:
            title = "⚠️ Несколько узлов недоступны"
            message = f"Недоступно устройств: {len(hosts)}"

        try:
            if config.sound_enabled:
                QApplication.beep()

            # Уведомление в трее
            notification.notify(
                title=title,
                message=message,
                app_name="Network Monitor",
                timeout=5
            )

        except (ImportError, RuntimeError, OSError) as e:
            logging.error(f"Ошибка отправки уведомления: {e}", exc_info=True)

    @staticmethod
    def notify_recovered_hosts(hosts: List[str], config: AppConfig) -> None:
        """Отправка уведомлений о восстановившихся узлах"""
        if not hosts or not config.notifications_enabled or not notification:
            return

        if len(hosts) <= 3:
            title = "✅ Узел восстановлен"
            message = "\n".join(hosts)
        else:
            title = "✅ Несколько узлов восстановлены"
            message = f"Восстановлено устройств: {len(hosts)}"

        try:
            if config.sound_enabled:
                QApplication.beep()

            notification.notify(
                title=title,
                message=message,
                app_name="Network Monitor",
                timeout=5
            )

        except (ImportError, RuntimeError, OSError) as e:
            logging.error(f"Ошибка отправки уведомления: {e}", exc_info=True)
    
    @staticmethod
    def show_notification(title: str, message: str) -> None:
        """Показ системного уведомления"""
        if not notification:
            return
        
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Network Monitor",
                timeout=5
            )
        except (ImportError, RuntimeError, OSError) as e:
            logging.error(f"Ошибка показа уведомления: {e}", exc_info=True)


class PingService(IPingService):
    """Сервис для выполнения ping-запросов (реализация через ping3)"""

    @staticmethod
    def ping_host(ip: str, timeout: float = 2.0) -> Optional[bool]:
        """Выполнение ping-запроса с фоллбэком на системный ping"""
        # 1. Попытка через ping3 (быстро, но требует прав)
        if ping:
            try:
                res = ping(ip, timeout=timeout)
                if isinstance(res, float):
                    return True
            except (OSError, ValueError, RuntimeError, PermissionError) as e:
                logging.warning(f"Ошибка ping3 {ip}: {e}")
        
        # 2. Фоллбэк на системный ping (работает всегда)
        return PingService._system_ping(ip, timeout)

    @staticmethod
    def _system_ping(host: str, timeout: float = 2.0) -> bool:
        import subprocess
        import platform
        
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_ms = int(timeout * 1000)
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        
        command = ['ping', param, '1', timeout_param, str(timeout_ms), host]
        
        try:
            creationflags = 0
            if platform.system().lower() == 'windows':
                creationflags = 0x08000000  # CREATE_NO_WINDOW
                
            subprocess.check_call(
                command, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )
            return True
        except (subprocess.CalledProcessError, Exception):
            return False