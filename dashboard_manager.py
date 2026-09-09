#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DashboardManager - Управление панелью статистики (Dashboard)
"""

import base64
from typing import Dict
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import QTimer
from models import HostStatus, AppConfig
from constants import (
    COLOR_TOTAL, SVG_CARD_TOTAL, SVG_CARD_ONLINE, SVG_CARD_WAITING,
    SVG_CARD_OFFLINE, SVG_CARD_MAINTENANCE, get_stat_card_style
)


class DashboardManager:
    """Менеджер управления Dashboard со статистикой"""

    def __init__(self, dashboard_labels: Dict[str, QLabel], config: AppConfig):
        """
        Инициализация менеджера дашборда
        
        Args:
            dashboard_labels: Словарь меток дашборда (total, online, waiting, offline, maintenance)
            config: Конфигурация приложения
        """
        self._dashboard_labels = dashboard_labels
        self._config = config
        
        # Счетчики статусов
        self._stats_counts = {
            "ONLINE": 0,
            "WAITING": 0,
            "OFFLINE": 0,
            "MAINTENANCE": 0
        }
        
        # Таймер для отложенного обновления (debounce)
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(500)  # 500ms задержка
        self._update_timer.timeout.connect(self._refresh_ui)

    def update_stats(self, stats_counts: Dict[str, int]) -> None:
        """
        Обновление счетчиков статусов
        
        Args:
            stats_counts: Словарь с количеством хостов по статусам
        """
        self._stats_counts = stats_counts.copy()
        self.schedule_update()

    def increment_status(self, status: str) -> None:
        """
        Инкрементальное увеличение счетчика статуса
        
        Args:
            status: Название статуса (ONLINE, WAITING, OFFLINE, MAINTENANCE)
        """
        if status in self._stats_counts:
            self._stats_counts[status] += 1
            self.schedule_update()

    def decrement_status(self, status: str) -> None:
        """
        Инкрементальное уменьшение счетчика статуса
        
        Args:
            status: Название статуса
        """
        if status in self._stats_counts:
            self._stats_counts[status] = max(0, self._stats_counts[status] - 1)
            self.schedule_update()

    def update_status_transition(self, old_status: str, new_status: str) -> None:
        """
        Обновление при смене статуса хоста
        
        Args:
            old_status: Предыдущий статус
            new_status: Новый статус
        """
        if old_status in self._stats_counts:
            self._stats_counts[old_status] = max(0, self._stats_counts[old_status] - 1)
        if new_status in self._stats_counts:
            self._stats_counts[new_status] += 1
        self.schedule_update()

    def schedule_update(self) -> None:
        """Запланировать обновление UI (с debounce)"""
        self._update_timer.start()

    def _refresh_ui(self) -> None:
        """Фактическое обновление UI Dashboard с использованием SVG и учетом темы"""
        theme = getattr(self._config, 'theme', 'dark')
        title_color = "#ffffff"
        
        # Используем значение TOTAL из словаря или считаем сумму (исключая сам ключ TOTAL если он есть)
        if "TOTAL" in self._stats_counts:
            total_hosts = self._stats_counts["TOTAL"]
        else:
            total_hosts = sum(v for k, v in self._stats_counts.items() if k != "TOTAL")
        
        # Обновление карточки "Всего узлов"
        b64_total = self._get_b64_svg(SVG_CARD_TOTAL)
        val_color_total = "#ffffff" if theme == "dark" else COLOR_TOTAL
        self._dashboard_labels['total'].setStyleSheet(get_stat_card_style('total', theme))
        self._dashboard_labels['total'].setText(f"""
            <table width='100%' cellpadding='0' cellspacing='0'>
                <tr>
                    <td width='44' valign='middle' align='center'><img src='data:image/svg+xml;base64,{b64_total}' width='36' height='36'></td>
                    <td valign='middle' style='padding-left: 10px;'>
                        <div style='color: {title_color}; font-size: 13px; font-weight: bold; line-height: 120%; margin-bottom: 2px;'>Всего узлов</div>
                        <div style='font-size: 26px; font-weight: 900; color: {val_color_total}; line-height: 100%;'>{total_hosts}</div>
                    </td>
                </tr>
            </table>
        """)

        # Обновление карточек статусов
        cards_info = [
            ("online", HostStatus.ONLINE, SVG_CARD_ONLINE),
            ("waiting", HostStatus.WAITING, SVG_CARD_WAITING),
            ("offline", HostStatus.OFFLINE, SVG_CARD_OFFLINE),
            ("maintenance", HostStatus.MAINTENANCE, SVG_CARD_MAINTENANCE)
        ]
        for status_key, status_obj, card_svg in cards_info:
            count = self._stats_counts.get(status_obj.name, 0)
            b64_icon = self._get_b64_svg(card_svg)
            val_color = "#ffffff" if theme == "dark" else status_obj.color
            lbl = self._dashboard_labels[status_key]
            lbl.setStyleSheet(get_stat_card_style(status_key, theme))
            lbl.setText(f"""
                <table width='100%' cellpadding='0' cellspacing='0'>
                    <tr>
                        <td width='44' valign='middle' align='center'><img src='data:image/svg+xml;base64,{b64_icon}' width='36' height='36'></td>
                        <td valign='middle' style='padding-left: 10px;'>
                            <div style='color: {title_color}; font-size: 13px; font-weight: bold; line-height: 120%; margin-bottom: 2px;'>{status_obj.title}</div>
                            <div style='font-size: 26px; font-weight: 900; color: {val_color}; line-height: 100%;'>{count}</div>
                        </td>
                    </tr>
                </table>
            """)

    def force_refresh(self) -> None:
        """Принудительное немедленное обновление UI"""
        self._update_timer.stop()
        self._refresh_ui()

    def get_stats_counts(self) -> Dict[str, int]:
        """Получение текущих счетчиков статусов"""
        return self._stats_counts.copy()

    @staticmethod
    def _get_b64_svg(svg_data: str) -> str:
        """
        Конвертация SVG данных в base64
        
        Args:
            svg_data: SVG данные в виде строки
            
        Returns:
            Base64 строка
        """
        return base64.b64encode(svg_data.encode('utf-8')).decode('utf-8')
