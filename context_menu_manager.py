#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер контекстных меню
"""

import sys
import subprocess
import ipaddress
from typing import List, Callable
from PyQt5.QtWidgets import QMenu, QMessageBox, QAction
from PyQt5.QtCore import QPoint, Qt

from models import Host, validate_ip_or_hostname
from host_manager import HostManager
from ui_components import UIComponents
from constants import (
    get_menu_style, SVG_MAINTENANCE, SVG_ONLINE, SVG_OFFLINE, SVG_WAITING,
    get_svg_add_group, get_svg_delete, get_svg_ping, get_svg_edit, get_svg_history
)
from core.host_repository import HostRepository
from helpdesk_service import HelpdeskService

class ContextMenuManager:
    """
    Класс для управления контекстными меню таблицы
    """

    def __init__(self, parent, table, table_model, groups: List[str], 
                 theme_getter: Callable, repository: HostRepository):
        """
        Инициализация менеджера контекстных меню
        
        Args:
            parent: Родительский виджет (MainWindow)
            table: Виджет таблицы
            table_model: Модель таблицы
            groups: Список групп
            theme_getter: Функция получения текущей темы
            repository: Репозиторий хостов
        """
        self._parent = parent
        self._table = table
        self._table_model = table_model
        self._groups = groups
        self._get_theme = theme_getter
        self._repository = repository

    def update_groups(self, groups):
        """Обновление списка групп"""
        self._groups = groups

    def show_host_context_menu(self, position: QPoint) -> None:
        """Показ контекстного меню для хоста"""
        row = self._table.rowAt(position.y())
        if row < 0:
            return

        theme = self._get_theme()
        menu = QMenu()
        menu.setStyleSheet(get_menu_style(theme))

        host = self._table_model.get_host(row)

        action_ping = menu.addAction(UIComponents._get_qicon(get_svg_ping(theme)), "Пинг в CMD")

        # "Пинг Cisco (IP-1)" — у циско-коммутатора рядом с узлом IP обычно
        # на 1 меньше последнего октета узла (192.168.14.100 -> .99).
        # Показываем пункт, только если IP узла — валидный IPv4 и вычислить
        # адрес циско вообще возможно (не показываем для хостнеймов и т.п.)
        action_ping_cisco = None
        cisco_ip = self._compute_cisco_ip(host.ip) if host else None
        if cisco_ip:
            action_ping_cisco = menu.addAction(
                UIComponents._get_qicon(get_svg_ping(theme)), f"Пинг Cisco ({cisco_ip})"
            )

        action_edit = menu.addAction(UIComponents._get_qicon(get_svg_edit(theme)), "Редактировать")
        action_history = menu.addAction(UIComponents._get_qicon(get_svg_history(theme)), "📋 История узла")
        action_delete = menu.addAction(UIComponents._get_qicon(get_svg_delete(theme)), "Удалить")
        menu.addSeparator()
        
        if host:
            if host.status == "MAINTENANCE":
                action_maint = menu.addAction(UIComponents._get_qicon(SVG_ONLINE), "Снять с тех.обслуживания")
            else:
                action_maint = menu.addAction(UIComponents._get_qicon(SVG_MAINTENANCE), "Поставить на тех.обслуживание")

            if host.notifications_enabled:
                action_notify = menu.addAction(UIComponents._get_qicon(SVG_WAITING), "Отключить уведомления")
            else:
                action_notify = menu.addAction(UIComponents._get_qicon(SVG_ONLINE), "Включить уведомления")
                
            # Helpdesk Integration
            action_hd_set = None
            action_hd_remove = None
            if hasattr(self._parent, '_config') and self._parent._config.helpdesk_enabled:
                menu.addSeparator()
                action_hd_set = menu.addAction(UIComponents._get_qicon(SVG_OFFLINE), "Создать тикет (Установить Статус 13)")
                action_hd_remove = menu.addAction(UIComponents._get_qicon(SVG_ONLINE), "Создать тикет (Снять Статус 13)")
        # ---
        
        action = menu.exec_(self._table.viewport().mapToGlobal(position))

        if action == action_ping:
            self._ping_host_cmd(row)
        elif action_ping_cisco is not None and action == action_ping_cisco:
            self._ping_cmd(cisco_ip, label="Cisco")
        elif action == action_edit:
            HostManager.edit_host(self._parent, row, self._table_model, self._groups, self._repository)
        elif action == action_history:
            self._show_host_history(row)
        elif action == action_delete:
            HostManager.delete_host(self._parent, row, self._table_model, self._repository)
        elif action == action_maint:
            HostManager.toggle_maintenance(self._parent, row, self._table_model, self._repository)
        elif action == action_notify:
            HostManager.toggle_notifications(self._parent, row, self._table_model, self._repository)
        elif action_hd_set is not None and action == action_hd_set:
            HelpdeskService.process_offline([host.name], self._parent._config)
            QMessageBox.information(self._parent, "Helpdesk", "Процесс создания тикета (Установка статуса) запущен в фоне.")
        elif action_hd_remove is not None and action == action_hd_remove:
            HelpdeskService.process_recovered([host.name], self._parent._config)
            QMessageBox.information(self._parent, "Helpdesk", "Процесс создания тикета (Снятие статуса) запущен в фоне.")

    @staticmethod
    def _compute_cisco_ip(ip: str) -> str:
        """
        IP циско-коммутатора = IP узла с последним октетом минус 1.
        Возвращает None, если ip не является валидным IPv4, или если
        последний октет уже 0 (вычитать некуда — соседний адрес ушёл бы
        в другую подсеть, это почти наверняка не циско).
        """
        try:
            addr = ipaddress.IPv4Address(ip)
        except (ipaddress.AddressValueError, ValueError):
            return None

        octets = str(addr).split(".")
        last = int(octets[-1])
        if last <= 0:
            return None

        octets[-1] = str(last - 1)
        return ".".join(octets)



    def show_bulk_menu(self, sender):
        """Показ меню массовых действий"""
        theme = self._get_theme()
        menu = QMenu(self._parent)
        menu.setStyleSheet(get_menu_style(theme))

        action_maint = menu.addAction(UIComponents._get_qicon(SVG_MAINTENANCE), "Переключить тех.обслуживание")
        action_group = menu.addAction(UIComponents._get_qicon(get_svg_add_group(theme)), "Изменить группу")
        action_notify = menu.addAction(UIComponents._get_qicon(SVG_WAITING), "Переключить уведомления")
        menu.addSeparator()
        action_delete = menu.addAction(UIComponents._get_qicon(get_svg_delete(theme)), "Удалить выбранные")

        action = menu.exec_(sender.mapToGlobal(sender.rect().bottomLeft()))

        if action == action_maint:
            HostManager.toggle_maintenance_selected(self._parent, self._table_model, self._repository)
        elif action == action_group:
            HostManager.change_group_selected(self._parent, self._table_model, self._groups, self._repository)
        elif action == action_notify:
            HostManager.toggle_notifications_selected(self._parent, self._table_model, self._repository)
        elif action == action_delete:
            HostManager.delete_selected(self._parent, self._table_model, self._repository)

    def show_header_context_menu(self, pos: QPoint, config) -> None:
        """Контекстное меню заголовка таблицы"""
        header = self._table.horizontalHeader()
        menu = QMenu(self._parent)
        menu.setStyleSheet(get_menu_style(config.theme))
        
        from table_model import HostTableModel
        column_names = HostTableModel.COLUMNS
        
        for i, name in enumerate(column_names):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not self._table.isColumnHidden(i))
            if i == 1:  # Не даем скрыть колонку "Название"
                action.setEnabled(False)
                
            def toggle_col(checked, col_idx=i):
                self._table.setColumnHidden(col_idx, not checked)
                if hasattr(self._parent, 'update_hidden_columns_config'):
                    self._parent.update_hidden_columns_config()
                
            action.triggered.connect(toggle_col)
            
        menu.exec_(header.mapToGlobal(pos))

    def _ping_host_cmd(self, row: int):
        """Открытие CMD с ping -t для основного узла"""
        host = self._table_model.get_host(row)
        if not host:
            return
        
        self._ping_cmd(host.ip)

    def _ping_cmd(self, ip: str, label: str = None):
        """Открытие CMD/терминала с ping -t по произвольному IP (используется и для Cisco)"""
        if not ip or not validate_ip_or_hostname(ip):
            QMessageBox.warning(self._parent, "Ошибка", f"Некорректный IP адрес: {ip}")
            return

        try:
            if sys.platform == "win32":
                subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k', 'ping', '-t', ip])
            else:
                subprocess.Popen(['xterm', '-e', 'ping', ip])
        except Exception as e:
            QMessageBox.warning(self._parent, "Ошибка", f"Не удалось открыть терминал: {e}")

    def _show_host_history(self, row: int):
        """Открыть диалог истории для конкретного узла"""
        host = self._table_model.get_host(row)
        if not host:
            return

        from history_views import HostHistoryDialog
        dlg = HostHistoryDialog(self._parent, host, self._repository, theme=self._get_theme())

        if not hasattr(self._parent, "_host_history_dialogs"):
            self._parent._host_history_dialogs = []
        self._parent._host_history_dialogs = [
            d for d in self._parent._host_history_dialogs if d.isVisible()
        ]
        self._parent._host_history_dialogs.append(dlg)

        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
