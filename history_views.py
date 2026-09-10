#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI для журнала истории событий (падения/восстановления узлов).

Два представления:
- HistoryPanel   — узкая панель справа от таблицы: история ВЫБРАННОГО узла.
- HistoryDialog  — отдельное окно: общий журнал по ВСЕМ узлам с фильтрами.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QDialog, QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush

from models import HostStatus
from constants import (
    get_table_style, get_svg_delete, get_svg_refresh,
    get_combobox_style, get_main_style, get_button_style,
    COLOR_ONLINE, COLOR_OFFLINE, COLOR_WAITING, COLOR_MAINTENANCE
)
from theme_manager import set_dark_titlebar
from ui_components import UIComponents


def _status_title(status_code: str) -> str:
    """Код статуса ('ONLINE') -> человекочитаемое название ('Online')"""
    if not status_code:
        return "—"
    try:
        return HostStatus[status_code].title
    except KeyError:
        return status_code


def _status_color(status_code: str) -> str:
    try:
        return HostStatus[status_code].color
    except KeyError:
        return "#888888"


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _format_ts(ts: str) -> str:
    dt = _parse_ts(ts)
    if not dt:
        return ts or ""
    local = dt.astimezone()
    return local.strftime("%d.%m.%Y %H:%M:%S")


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} сек"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    minutes = minutes % 60
    if hours < 24:
        return f"{hours} ч {minutes} мин"
    days = hours // 24
    hours = hours % 24
    return f"{days} дн {hours} ч"


class EventCardWidget(QFrame):
    """Карточка отдельного события в ленте журнала (крупные шрифты и просторные бейджи)"""
    def __init__(self, when_str: str, full_time: str, host_name: str, status_code: str, theme="dark"):
        super().__init__()
        status_info = {
            "ONLINE":       ("Online",              COLOR_ONLINE, "rgba(16, 185, 129, 0.15)", "●"),
            "OFFLINE":      ("Offline",             COLOR_OFFLINE, "rgba(239, 68, 68, 0.15)", "●"),
            "WAITING":      ("Waiting",             COLOR_WAITING, "rgba(245, 158, 11, 0.15)", "●"),
            "MAINTENANCE":  ("Тех.обсл.",           COLOR_MAINTENANCE, "rgba(139, 92, 246, 0.15)", "●"),
        }
        st_title, st_color, st_bg, st_icon = status_info.get(status_code, (status_code, "#888888", "rgba(136, 136, 136, 0.15)", "•"))

        is_dark = theme in ("dark", "tactical")
        if theme == "tactical":
            bg = "#0D1117"
            bg_hover = "#161B22"
            border = "#1F232D"
            self.name_color = "#E2E8F0"
        else:
            bg = "#1e222b" if is_dark else "#ffffff"
            bg_hover = "#252b37" if is_dark else "#f8fafc"
            border = "#2a2f3d" if is_dark else "#e2e8f0"
            self.name_color = "#f1f5f9" if is_dark else "#1e293b"
            
        border_radius = "0px" if theme == "tactical" else "8px"
        self.setStyleSheet(f"""
            EventCardWidget {{
                background-color: {bg};
                border: 1px solid {border};
                border-left: 4px solid {st_color};
                border-radius: {border_radius};
            }}
            EventCardWidget:hover {{
                background-color: {bg_hover};
                border-color: {st_color};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Верхняя строка: "5 мин назад" + Бейдж статуса
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        time_lbl = QLabel(when_str)
        time_lbl.setToolTip(full_time)
        time_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500; border: none; background: transparent;")
        top_row.addWidget(time_lbl)
        top_row.addStretch()

        badge = QLabel(f"{st_icon} {st_title}")
        badge.setAlignment(Qt.AlignCenter)
        badge_radius = '0px' if theme == 'tactical' else '9px'
        badge.setStyleSheet(f"""
            QLabel {{
                color: {st_color};
                border: 1px solid {st_color};
                background-color: {st_bg};
                border-radius: {badge_radius};
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
                min-height: 18px;
            }}
        """)
        top_row.addWidget(badge)
        layout.addLayout(top_row)

        # Нижняя строка: Имя узла
        name_lbl = QLabel(host_name)
        name_lbl.setStyleSheet(f"color: {self.name_color}; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(name_lbl)


class EventLogPanel(QFrame):
    """
    Правая боковая панель: живой журнал событий по ВСЕМ узлам.
    Показывает последние события с авто-обновлением каждые 10 сек.
    """

    STATUS_FILTER_OPTIONS = [
        ("Все", None),
        ("Online", "ONLINE"),
        ("Offline", "OFFLINE"),
        ("Waiting", "WAITING"),
        ("Тех.обсл.", "MAINTENANCE"),
    ]

    def __init__(self, repository, parent=None, theme: str = "light"):
        super().__init__(parent)
        self._repository = repository
        self._theme = theme
        self._btn_clear = None
        self._btn_refresh = None
        self._init_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(10000)  # 10 сек
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()

        self.refresh()

    def _init_ui(self):
        self.setMinimumWidth(250)
        self.setMaximumWidth(16777215)
        self.setFrameShape(QFrame.StyledPanel)
        
        is_dark = self._theme in ("dark", "tactical")
        bg_color = '#090A0F' if self._theme == 'tactical' else ('#181c26' if is_dark else '#ffffff')
        border_color = '#1F232D' if self._theme == 'tactical' else ('#282e3d' if is_dark else '#d0d7de')
        border_radius = '0px' if self._theme == 'tactical' else '8px'
        self.setStyleSheet(f"""
            EventLogPanel {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {border_radius};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        # Заголовок + Фильтр + кнопки
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        title = QLabel("Журнал событий")
        title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {'#f1f5f9' if is_dark else '#1e293b'}; border: none; background: transparent;")
        header_row.addWidget(title)
        header_row.addStretch()

        self._status_combo = QComboBox()
        for label, _ in self.STATUS_FILTER_OPTIONS:
            self._status_combo.addItem(label)
        self._status_combo.currentIndexChanged.connect(self.refresh)
        self._status_combo.setMaximumWidth(110)
        self._status_combo.setFixedHeight(26)
        self._status_combo.setStyleSheet(get_combobox_style(self._theme))
        header_row.addWidget(self._status_combo)

        btn_style_clear = f"""
            QPushButton {{
                background-color: {'#1e222b' if is_dark else '#f8fafc'};
                border: 1px solid {'#2a2f3d' if is_dark else '#d0d7de'};
                border-radius: 5px;
                padding: 3px;
            }}
            QPushButton:hover {{
                background-color: {'#2a1619' if is_dark else '#fee2e2'};
                border-color: #ef4444;
            }}
        """
        self._btn_clear = QPushButton()
        self._btn_clear.setIcon(UIComponents._get_qicon(get_svg_delete(self._theme), 14))
        self._btn_clear.setFixedSize(26, 26)
        self._btn_clear.setToolTip("Очистить журнал событий")
        self._btn_clear.setStyleSheet(btn_style_clear)
        self._btn_clear.clicked.connect(self.clear_history)
        header_row.addWidget(self._btn_clear)

        btn_style_refresh = f"""
            QPushButton {{
                background-color: {'#1e222b' if is_dark else '#f8fafc'};
                border: 1px solid {'#2a2f3d' if is_dark else '#d0d7de'};
                border-radius: 5px;
                padding: 3px;
            }}
            QPushButton:hover {{
                background-color: {'#172554' if is_dark else '#eff6ff'};
                border-color: #3b82f6;
            }}
        """
        self._btn_refresh = QPushButton()
        self._btn_refresh.setIcon(UIComponents._get_qicon(get_svg_refresh(self._theme), 14))
        self._btn_refresh.setFixedSize(26, 26)
        self._btn_refresh.setToolTip("Обновить журнал")
        self._btn_refresh.setStyleSheet(btn_style_refresh)
        self._btn_refresh.clicked.connect(self.refresh)
        header_row.addWidget(self._btn_refresh)

        layout.addLayout(header_row)

        # Лента карточек событий
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.NoSelection)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 4px 0px;
            }
        """)
        layout.addWidget(self._list, 1)

        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet("color: #94a3b8; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(self._summary_label)

    def clear_history(self):
        """Очистка журнала событий с подтверждением"""
        if not self._repository:
            return
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Очистка журнала",
            "Вы уверены, что хотите очистить весь журнал событий?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._repository.clear_history()
            self.refresh()

    @staticmethod
    def _relative_time(ts: str) -> str:
        """Возвращает 'N мин назад' / 'N ч назад' / дату"""
        dt = _parse_ts(ts)
        if not dt:
            return ts or ""
        now = datetime.now(timezone.utc)
        diff = int((now - dt).total_seconds())
        if diff < 60:
            return "только что"
        if diff < 3600:
            return f"{diff // 60} мин назад"
        if diff < 86400:
            return f"{diff // 3600} ч назад"
        return _format_ts(ts)[:10]  # DD.MM.YYYY

    def refresh(self):
        """Обновить данные из БД"""
        if self._repository is None:
            return

        idx = self._status_combo.currentIndex()
        status_filter = self.STATUS_FILTER_OPTIONS[idx][1] if 0 <= idx < len(self.STATUS_FILTER_OPTIONS) else None

        events = self._repository.get_history_events(
            limit=200,
            status_filter=status_filter,
        )

        self._list.clear()
        if not events:
            placeholder = QLabel("Событий пока нет")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder_color = "#94a3b8" if self._theme == "dark" else "#64748b"
            placeholder.setStyleSheet(f"color: {placeholder_color}; font-size: 13px; padding: 40px 10px; border: none; background: transparent;")
            list_item = QListWidgetItem()
            list_item.setSizeHint(placeholder.sizeHint())
            self._list.addItem(list_item)
            self._list.setItemWidget(list_item, placeholder)
        else:
            for ev in events:
                when_str = self._relative_time(ev["timestamp"])
                full_time = _format_ts(ev["timestamp"])
                host_name = ev.get("host_name") or ev.get("host_id", "")
                status_code = ev.get("new_status", "")

                item_widget = EventCardWidget(when_str, full_time, host_name, status_code, theme=self._theme)
                list_item = QListWidgetItem()
                list_item.setSizeHint(item_widget.sizeHint())
                self._list.addItem(list_item)
                self._list.setItemWidget(list_item, item_widget)

        count = len(events)
        suffix = " (последние 200)" if count >= 200 else ""
        self._summary_label.setText(f"Событий: {count}{suffix}")

    def set_theme(self, theme: str):
        self._theme = theme
        is_dark = theme in ("dark", "tactical")
        bg_color = '#090A0F' if theme == 'tactical' else ('#181c26' if is_dark else '#ffffff')
        border_color = '#1F232D' if theme == 'tactical' else ('#282e3d' if is_dark else '#d0d7de')
        border_radius = '0px' if theme == 'tactical' else '8px'
        self.setStyleSheet(f"""
            EventLogPanel {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {border_radius};
            }}
        """)
        if hasattr(self, '_btn_clear') and self._btn_clear:
            self._btn_clear.setIcon(UIComponents._get_qicon(get_svg_delete(theme), 14))
            self._btn_clear.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#1e222b' if is_dark else '#f8fafc'};
                    border: 1px solid {'#2a2f3d' if is_dark else '#d0d7de'};
                    border-radius: 5px;
                    padding: 3px;
                }}
                QPushButton:hover {{
                    background-color: {'#2a1619' if is_dark else '#fee2e2'};
                    border-color: #ef4444;
                }}
            """)
        if hasattr(self, '_btn_refresh') and self._btn_refresh:
            self._btn_refresh.setIcon(UIComponents._get_qicon(get_svg_refresh(theme), 14))
            self._btn_refresh.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#1e222b' if is_dark else '#f8fafc'};
                    border: 1px solid {'#2a2f3d' if is_dark else '#d0d7de'};
                    border-radius: 5px;
                    padding: 3px;
                }}
                QPushButton:hover {{
                    background-color: {'#172554' if is_dark else '#eff6ff'};
                    border-color: #3b82f6;
                }}
            """)
        if hasattr(self, '_status_combo') and self._status_combo:
            self._status_combo.setStyleSheet(get_combobox_style(theme))
        self.refresh()


class HostHistoryDialog(QDialog):
    """
    Компактная карточка истории конкретного узла:
    - Сводка (название, IP, группа, адрес, текущий статус)
    - 3 карточки ключевых метрик (сбоев, суммарный простой, текущий аптайм)
    - Хронологическая таблица событий с длительностями
    - Экспорт в Excel и очистка истории данного узла
    """

    EVENT_LABELS = {
        "ONLINE":       ("●", "Online",              COLOR_ONLINE),
        "OFFLINE":      ("●", "Offline",             COLOR_OFFLINE),
        "WAITING":      ("●", "Waiting",             COLOR_WAITING),
        "MAINTENANCE":  ("●", "Тех.обслуживание",    COLOR_MAINTENANCE),
    }

    def __init__(self, parent, host, repository, theme: str = "light"):
        super().__init__(parent)
        self._host = host
        self._repository = repository
        if parent and hasattr(parent, '_config'):
            self._theme = getattr(parent._config, 'theme', theme)
        else:
            self._theme = theme
        self._events: List[Dict] = []
        self.setWindowTitle(f"История узла — {host.name}")
        self.resize(720, 540)
        self.setMinimumSize(580, 440)
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        is_dark = self._theme in ("dark", "tactical")
        self.setStyleSheet(get_main_style(self._theme))
        set_dark_titlebar(self, is_dark)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Шапка с информацией об узле
        header_card = QFrame()
        if self._theme == "tactical":
            card_bg = "#0D1117"
            card_border = "#1F232D"
            text_color = "#E2E8F0"
            text_sec = "#64748B"
        else:
            card_bg = "#2b2d30" if is_dark else "#f6f8fa"
            card_border = "#404040" if is_dark else "#d0d7de"
            text_color = "#e1e1e1" if is_dark else "#24292f"
            text_sec = "#aaaaaa" if is_dark else "#57606a"

        card_radius = "0px" if self._theme == "tactical" else "8px"
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: {card_radius};
                padding: 10px;
            }}
        """)
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(6)

        # Верхняя строка шапки: Имя + Бейдж статуса
        top_row = QHBoxLayout()
        name_lbl = QLabel(f"🖥️ {self._host.name}")
        name_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_color}; border: none;")
        top_row.addWidget(name_lbl)
        top_row.addStretch()

        # Бейдж текущего статуса
        st = self._host.status or "UNKNOWN"
        emoji, st_label, st_color = self.EVENT_LABELS.get(st, ("⚪", st, "#888"))
        self._status_badge = QLabel(f"{emoji} {st_label}")
        self._status_badge.setStyleSheet(f"""
            QLabel {{
                font-weight: bold;
                font-size: 12px;
                color: {st_color};
                border: 1px solid {st_color};
                border-radius: 12px;
                padding: 3px 10px;
                background-color: transparent;
            }}
        """)
        top_row.addWidget(self._status_badge)
        header_layout.addLayout(top_row)

        # Нижняя строка шапки: IP, группа, адрес
        info_text = f"IP: <b>{self._host.ip}</b>   •   Группа: <b>{self._host.group}</b>"
        if self._host.address:
            info_text += f"   •   Адрес: <b>{self._host.address}</b>"
        info_lbl = QLabel(info_text)
        info_lbl.setStyleSheet(f"color: {text_sec}; font-size: 11px; border: none;")
        header_layout.addWidget(info_lbl)

        layout.addWidget(header_card)

        # 2. Карточки метрик (3 штуки)
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(8)

        def _create_metric_box(title: str):
            box = QFrame()
            box_radius = "0px" if self._theme == "tactical" else "6px"
            box.setStyleSheet(f"""
                QFrame {{
                    background-color: {card_bg};
                    border: 1px solid {card_border};
                    border-radius: {box_radius};
                    padding: 6px;
                }}
            """)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(10, 8, 10, 8)
            box_layout.setSpacing(3)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(f"color: {text_sec}; font-size: 10px; font-weight: normal; border: none;")
            v_lbl = QLabel("—")
            v_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {text_color}; border: none;")
            box_layout.addWidget(t_lbl)
            box_layout.addWidget(v_lbl)
            return box, v_lbl

        self._box_incidents, self._val_incidents = _create_metric_box("📉 Всего сбоев (Offline)")
        self._box_downtime, self._val_downtime = _create_metric_box("⏱️ Суммарный простой")
        self._box_uptime, self._val_uptime = _create_metric_box("📊 Текущее состояние")

        metrics_layout.addWidget(self._box_incidents)
        metrics_layout.addWidget(self._box_downtime)
        metrics_layout.addWidget(self._box_uptime)
        layout.addLayout(metrics_layout)

        # 3. Таблица хронологии событий
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Дата и время", "Событие", "Длительность состояния"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(True)
        hdr.setMinimumSectionSize(60)
        self._table.setColumnWidth(0, 160)
        self._table.setColumnWidth(1, 130)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setDefaultSectionSize(26)
        self._table.setStyleSheet(get_table_style(self._theme))
        layout.addWidget(self._table, 1)

        # 4. Нижняя панель действий
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self._btn_export = QPushButton("📊 Экспорт в Excel")
        self._btn_export.setToolTip("Сохранить историю узла в Excel-файл")
        self._btn_export.setStyleSheet(get_button_style(self._theme))
        self._btn_export.clicked.connect(self._export_to_excel)
        bottom_bar.addWidget(self._btn_export)

        self._btn_clear = QPushButton("🗑 Очистить историю")
        self._btn_clear.setToolTip("Удалить все события истории для этого узла")
        self._btn_clear.setStyleSheet(get_button_style(self._theme))
        self._btn_clear.clicked.connect(self._clear_host_history)
        bottom_bar.addWidget(self._btn_clear)

        bottom_bar.addStretch()

        self._btn_refresh = QPushButton("↻ Обновить")
        self._btn_refresh.setStyleSheet(get_button_style(self._theme))
        self._btn_refresh.clicked.connect(self.refresh)
        bottom_bar.addWidget(self._btn_refresh)

        self._btn_close = QPushButton("Закрыть")
        self._btn_close.setStyleSheet(get_button_style(self._theme))
        self._btn_close.clicked.connect(self.close)
        bottom_bar.addWidget(self._btn_close)

        layout.addLayout(bottom_bar)

    def refresh(self):
        """Загрузка данных истории и расчёт аналитики"""
        if not self._repository:
            return

        events = self._repository.get_host_history(self._host.id, limit=500)
        self._events = events

        # Расчет метрик
        offline_count = 0
        total_offline_seconds = 0.0
        now = datetime.now(timezone.utc)

        self._table.setRowCount(0)
        self._table.setRowCount(len(events))

        for i, ev in enumerate(events):
            new_status = ev.get("new_status", "")
            old_status = ev.get("old_status", "")
            ts = ev.get("timestamp", "")

            if new_status == "OFFLINE":
                offline_count += 1

            # Расчёт длительности нахождения в новом статусе
            this_dt = _parse_ts(ts)
            if i == 0:
                end_dt = now
            else:
                end_dt = _parse_ts(events[i - 1]["timestamp"])

            duration_str = "—"
            if this_dt and end_dt:
                sec = max(0.0, (end_dt - this_dt).total_seconds())
                dur_text = _format_duration(sec)
                if i == 0:
                    duration_str = f"длится {dur_text}"
                else:
                    duration_str = f"длилось {dur_text}"

                if new_status == "OFFLINE":
                    total_offline_seconds += sec

            emoji, label, color = self.EVENT_LABELS.get(new_status, ("⚪", new_status, "#888"))

            time_item = QTableWidgetItem(_format_ts(ts))
            time_item.setTextAlignment(Qt.AlignCenter)
            
            event_item = QTableWidgetItem(f"{emoji} {label}")
            event_item.setForeground(QBrush(QColor(color)))

            dur_item = QTableWidgetItem(duration_str)

            for item in (time_item, event_item, dur_item):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self._table.setItem(i, 0, time_item)
            self._table.setItem(i, 1, event_item)
            self._table.setItem(i, 2, dur_item)

        # Обновляем плашки метрик
        self._val_incidents.setText(f"{offline_count} раз" if offline_count > 0 else "0 (стабилен)")
        if offline_count > 0:
            self._val_incidents.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_OFFLINE}; border: none;")
        else:
            self._val_incidents.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_ONLINE}; border: none;")

        if total_offline_seconds > 0:
            self._val_downtime.setText(_format_duration(total_offline_seconds))
            self._val_downtime.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_WAITING}; border: none;")
        else:
            self._val_downtime.setText("0 сек")
            self._val_downtime.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_ONLINE}; border: none;")

        # Текущее состояние
        cur_st = self._host.status
        if events:
            latest_dt = _parse_ts(events[0]["timestamp"])
            if latest_dt:
                cur_dur = _format_duration(max(0, (now - latest_dt).total_seconds()))
                if cur_st == "ONLINE":
                    self._val_uptime.setText(f"Online: {cur_dur}")
                    self._val_uptime.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_ONLINE}; border: none;")
                elif cur_st == "OFFLINE":
                    self._val_uptime.setText(f"Offline: {cur_dur}")
                    self._val_uptime.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLOR_OFFLINE}; border: none;")
                else:
                    self._val_uptime.setText(f"{cur_st}: {cur_dur}")
            else:
                self._val_uptime.setText(cur_st)
        else:
            self._val_uptime.setText(f"{cur_st} (без событий)")

    def _export_to_excel(self):
        """Экспорт истории узла в Excel"""
        if not self._events:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "Экспорт", "История данного узла пуста — нечего экспортировать.")
            return

        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        from excel_service import ExcelService

        default_filename = f"history_{self._host.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить историю узла в Excel",
            default_filename,
            "Excel Files (*.xlsx);;All Files (*)"
        )

        if not file_path:
            return

        try:
            ExcelService.export_host_history(file_path, self._host.name, self._host.ip, self._events)
            QMessageBox.information(self, "Успех", f"История узла успешно сохранена в:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", f"Не удалось сохранить файл: {e}")

    def _clear_host_history(self):
        """Очистка истории только для текущего узла"""
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Очистка истории",
            f"Вы уверены, что хотите удалить историю событий узла «{self._host.name}»?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._repository.clear_host_history(self._host.id)
            self.refresh()
            QMessageBox.information(self, "Очищено", f"История узла «{self._host.name}» очищена.")


class HistoryDialog(QDialog):
    """
    Общий журнал событий по ВСЕМ узлам — отдельное окно с фильтрами.
    Открывается через меню 'Вид -> Журнал событий' (Ctrl+H).
    """

    STATUS_FILTER_OPTIONS = [
        ("Все события", None),
        ("Упал (Offline)", "OFFLINE"),
        ("Восстановлен (Online)", "ONLINE"),
        ("Не отвечает (Waiting)", "WAITING"),
        ("Тех.обслуживание", "MAINTENANCE"),
    ]

    def __init__(self, parent, repository, groups: List[str], theme: str = "light"):
        super().__init__(parent)
        self._repository = repository
        self._groups = groups
        if parent and hasattr(parent, '_config'):
            self._theme = getattr(parent._config, 'theme', theme)
        else:
            self._theme = theme
        self.setWindowTitle("Журнал событий")
        self.setModal(False)
        self.resize(900, 560)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        is_dark = self._theme in ("dark", "tactical")
        self.setStyleSheet(get_main_style(self._theme))
        set_dark_titlebar(self, is_dark)
        layout = QVBoxLayout(self)

        # --- Панель фильтров ---
        filters_layout = QHBoxLayout()

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Поиск по имени / IP / адресу...")
        self._search_edit.textChanged.connect(self._schedule_refresh)
        filters_layout.addWidget(self._search_edit, 2)

        self._group_combo = QComboBox()
        self._group_combo.addItem("Все группы")
        self._group_combo.addItems(self._groups)
        self._group_combo.setStyleSheet(get_combobox_style(self._theme))
        self._group_combo.currentIndexChanged.connect(self._refresh)
        filters_layout.addWidget(self._group_combo, 1)

        self._status_combo = QComboBox()
        for title, _code in self.STATUS_FILTER_OPTIONS:
            self._status_combo.addItem(title)
        self._status_combo.setStyleSheet(get_combobox_style(self._theme))
        self._status_combo.currentIndexChanged.connect(self._refresh)
        filters_layout.addWidget(self._status_combo, 1)

        self._refresh_btn = QPushButton("Обновить")
        self._refresh_btn.setStyleSheet(get_button_style(self._theme))
        self._refresh_btn.clicked.connect(self._refresh)
        filters_layout.addWidget(self._refresh_btn)

        layout.addLayout(filters_layout)

        # --- Debounce для текстового поиска ---
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._refresh)

        # --- Таблица событий ---
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Время", "Узел", "IP", "Группа", "Было", "Стало"]
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)  # сортируем сами при загрузке (по времени)
        self._table.setStyleSheet(get_table_style(self._theme))
        layout.addWidget(self._table, 1)

        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"color: {'#94a3b8' if is_dark else '#888'};")
        layout.addWidget(self._summary_label)

    def _schedule_refresh(self):
        self._search_timer.start()

    def _current_status_filter(self) -> Optional[str]:
        idx = self._status_combo.currentIndex()
        if 0 <= idx < len(self.STATUS_FILTER_OPTIONS):
            return self.STATUS_FILTER_OPTIONS[idx][1]
        return None

    def _refresh(self):
        search_text = self._search_edit.text().strip() or None
        group = self._group_combo.currentText()
        group_filter = None if group == "Все группы" else group
        status_filter = self._current_status_filter()

        events = self._repository.get_history_events(
            limit=1000,
            host_name_filter=search_text,
            group_filter=group_filter,
            status_filter=status_filter,
        )

        self._table.setRowCount(0)
        self._table.setRowCount(len(events))
        for row, ev in enumerate(events):
            time_item = QTableWidgetItem(_format_ts(ev["timestamp"]))
            name_item = QTableWidgetItem(ev.get("host_name") or ev.get("host_id", ""))
            ip_item = QTableWidgetItem(ev.get("ip", ""))
            group_item = QTableWidgetItem(ev.get("group", ""))
            old_item = QTableWidgetItem(_status_title(ev.get("old_status")))
            new_item = QTableWidgetItem(_status_title(ev.get("new_status")))

            new_item.setForeground(QBrush(QColor(_status_color(ev.get("new_status")))))

            for item in (time_item, name_item, ip_item, group_item, old_item, new_item):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self._table.setItem(row, 0, time_item)
            self._table.setItem(row, 1, name_item)
            self._table.setItem(row, 2, ip_item)
            self._table.setItem(row, 3, group_item)
            self._table.setItem(row, 4, old_item)
            self._table.setItem(row, 5, new_item)

        self._summary_label.setText(f"Событий: {len(events)}" + (" (показаны последние 1000)" if len(events) >= 1000 else ""))


# Алиас для обратной совместимости
HistoryPanel = HostHistoryDialog
