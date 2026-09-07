#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Components Factory
Методы для создания UI элементов главного окна
"""

from PyQt5.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QPushButton, QLineEdit,
    QComboBox, QTableView, QHeaderView
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QByteArray, pyqtSignal
import base64
from typing import Dict, List, Tuple

from table_model import HostTableModel
from models import HostStatus
from constants import (
    get_table_style, get_dashboard_style, get_stat_card_style,
    get_button_style, COLOR_ONLINE, COLOR_WAITING, COLOR_OFFLINE,
    COLOR_MAINTENANCE, COLOR_TOTAL, SVG_ONLINE, SVG_OFFLINE,
    SVG_WAITING, SVG_MAINTENANCE, get_svg_total, get_svg_add_host, get_svg_add_group,
    get_svg_import, get_svg_export, get_svg_scan, get_svg_bulk, get_svg_theme,
    get_svg_settings, get_svg_delete, get_menu_style,
    SVG_CARD_TOTAL, SVG_CARD_ONLINE, SVG_CARD_WAITING, SVG_CARD_OFFLINE, SVG_CARD_MAINTENANCE
)

class ClickableLabel(QLabel):
    """QLabel с поддержкой клика"""
    clicked = pyqtSignal(str)

    def __init__(self, key: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)


class UIComponents:
    """Фабрика UI компонентов"""
    
    @staticmethod
    def _get_qicon(svg_data: str, size: int = 16) -> QIcon:
        """Вспомогательный метод для создания QIcon из SVG строки"""
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    
    @staticmethod
    def create_table(parent, theme="light") -> Tuple[QTableView, HostTableModel]:
        """Создание таблицы хостов"""
        table_model = HostTableModel(theme=theme)
        table = QTableView()
        table.setModel(table_model)
        
        # Настройка таблицы
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionsMovable(True)
        header.setStretchLastSection(False)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableView.SelectRows)
        table.setSelectionMode(QTableView.ExtendedSelection)
        table.setShowGrid(True)
        table.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        
        # Начальные ширины колонок
        table.setColumnWidth(0, 70)  # Статус
        table.setColumnWidth(1, 250) # Название
        table.setColumnWidth(2, 130) # IP
        table.setColumnWidth(3, 150) # Адрес
        table.setColumnWidth(4, 120) # Группа
        table.setColumnWidth(5, 120) # Время offline
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Стилизация
        table.setStyleSheet(get_table_style(theme))
        
        return table, table_model
    
    @staticmethod
    def create_dashboard(theme="light") -> Tuple[QFrame, Dict[str, QLabel]]:
        """Создание Dashboard со статистикой в стиле карточек из макета"""
        frame = QFrame()
        frame.setStyleSheet(get_dashboard_style(theme))
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Создаем карточки статистики
        dashboard_labels = {
            'total': UIComponents._create_stat_card("total", SVG_CARD_TOTAL, "Всего узлов", "0", COLOR_TOTAL, theme),
            'online': UIComponents._create_stat_card("online", SVG_CARD_ONLINE, "Online", "0", COLOR_ONLINE, theme),
            'waiting': UIComponents._create_stat_card("waiting", SVG_CARD_WAITING, "Ожидание", "0", COLOR_WAITING, theme),
            'offline': UIComponents._create_stat_card("offline", SVG_CARD_OFFLINE, "Offline", "0", COLOR_OFFLINE, theme),
            'maintenance': UIComponents._create_stat_card("maintenance", SVG_CARD_MAINTENANCE, "Тех.обсл.", "0", COLOR_MAINTENANCE, theme)
        }
        
        for label in dashboard_labels.values():
            layout.addWidget(label)
        
        frame.setLayout(layout)
        
        return frame, dashboard_labels
    
    @staticmethod
    def create_search_bar(parent, groups, theme: str = "light"):
        """Создает поиск и фильтр по группам (справа сверху над таблицей)"""
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        # Добавляем растяжку слева чтобы элементы были справа
        search_layout.addStretch()
        
        # Фильтр по группам
        group_filter = QComboBox()
        group_filter.addItem("📁 Все группы")
        group_filter.addItems(groups)
        group_filter.setMinimumWidth(150)
        
        # Поле поиска
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("🔍 Поиск...")
        search_edit.setMinimumWidth(250)
        search_edit.setClearButtonEnabled(True)
        
        search_layout.addWidget(group_filter)
        search_layout.addWidget(search_edit)
        
        return search_layout, search_edit, group_filter
    
    @staticmethod
    def _create_stat_card(key: str, svg_data: str, title: str, value: str, color: str, theme="light") -> ClickableLabel:
        """Создание карточки статистики"""
        label = ClickableLabel(key)
        label.setStyleSheet(get_stat_card_style(key, theme))
        
        # Конвертируем SVG в base64 для отображения в QLabel
        b64_svg = base64.b64encode(svg_data.encode('utf-8')).decode('utf-8')
        img_tag = f"<img src='data:image/svg+xml;base64,{b64_svg}' width='36' height='36'>"
        
        title_color = "#ffffff" if theme == "dark" else "#1e293b"
        val_color = "#ffffff" if theme == "dark" else color
        
        label.setText(f"""
            <table width='100%' cellpadding='0' cellspacing='0'>
                <tr>
                    <td width='44' valign='middle' align='center'>{img_tag}</td>
                    <td valign='middle' style='padding-left: 10px;'>
                        <div style='color: {title_color}; font-size: 13px; font-weight: bold; line-height: 120%; margin-bottom: 2px;'>{title}</div>
                        <div style='font-size: 26px; font-weight: 900; color: {val_color}; line-height: 100%;'>{value}</div>
                    </td>
                </tr>
            </table>
        """)
        label.setAlignment(Qt.AlignCenter)
        return label
    
    # create_toolbar and create_filters methods removed - no longer used in UI\r\n