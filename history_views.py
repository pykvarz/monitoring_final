#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI для журнала истории событий (падения/восстановления узлов).

- EventLogPanel  — боковая панель: живой журнал событий с авто-обновлением.
- HistoryDialog  — отдельное окно: общий журнал по ВСЕМ узлам с фильтрами.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QDialog, QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QBrush

from models import HostStatus
from constants import (
    get_table_style, get_svg_delete, get_svg_refresh,
    get_svg_popout, get_svg_dock, get_svg_pin, get_svg_app_icon,
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
    def __init__(self, when_str: str, full_time: str, host_name: str, status_code: str, host_id: str = "", theme="dark"):
        super().__init__()
        self.host_id = host_id
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

    def contextMenuEvent(self, event):
        event.ignore()


class EventLogPanel(QFrame):
    """
    Правая боковая панель: живой журнал событий по ВСЕМ узлам.
    Показывает последние события с авто-обновлением каждые 10 сек.
    """

    host_context_menu_requested = pyqtSignal(str, QPoint)
    dock_toggle_requested = pyqtSignal()
    pin_toggle_requested = pyqtSignal(bool)

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
        self.is_floating = False
        self.is_pinned = True
        self._btn_clear = None
        self._btn_refresh = None
        self._btn_pin = None
        self._btn_dock = None
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
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(6)

        # Заголовок + Фильтр + кнопки
        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        title = QLabel("Журнал событий")
        title.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {'#f1f5f9' if is_dark else '#1e293b'}; border: none; background: transparent;")
        header_row.addWidget(title)
        header_row.addStretch()

        self._status_combo = QComboBox()
        UIComponents.setup_combobox(self._status_combo, self._theme)
        for label, _ in self.STATUS_FILTER_OPTIONS:
            self._status_combo.addItem(label)
        self._status_combo.currentIndexChanged.connect(self.refresh)
        self._status_combo.setMinimumWidth(110)
        self._status_combo.setFixedHeight(26)
        header_row.addWidget(self._status_combo)

        btn_style_clear = f"""
            QPushButton {{
                background-color: {'#1e222b' if is_dark else '#f8fafc'};
                border: 1px solid {'#2a2f3d' if is_dark else '#d0d7de'};
                border-radius: 5px;
                padding: 3px;
                min-width: 0px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
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
                min-width: 0px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
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

        self._btn_pin = QPushButton()
        self._btn_pin.setFixedSize(26, 26)
        self._btn_pin.clicked.connect(self._on_pin_clicked)
        self._btn_pin.setVisible(False)
        header_row.addWidget(self._btn_pin)

        self._btn_dock = QPushButton()
        self._btn_dock.setFixedSize(26, 26)
        self._btn_dock.clicked.connect(self.dock_toggle_requested.emit)
        header_row.addWidget(self._btn_dock)

        self._update_dock_buttons()

        layout.addLayout(header_row)

        # Лента карточек событий
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.NoSelection)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_list_context_menu)
        self._list.setStyleSheet(self._get_list_style(self._theme))
        layout.addWidget(self._list, 1)

        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet("color: #94a3b8; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(self._summary_label)

    def _on_list_context_menu(self, pos: QPoint):
        """Обработка нажатия ПКМ по элементу журнала событий"""
        item = self._list.itemAt(pos)
        host_id = None
        if item:
            host_id = item.data(Qt.UserRole)
        if not host_id:
            w = self._list.childAt(pos)
            while w and not isinstance(w, EventCardWidget) and w != self._list:
                w = w.parentWidget()
            if isinstance(w, EventCardWidget) and hasattr(w, "host_id"):
                host_id = w.host_id

        if host_id:
            global_pos = self._list.viewport().mapToGlobal(pos)
            self.host_context_menu_requested.emit(host_id, global_pos)

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
            limit=30,  # Оптимизация UI: до 30 актуальных событий вместо 200 тяжелых виджетов
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
                host_id = ev.get("host_id", "")

                item_widget = EventCardWidget(when_str, full_time, host_name, status_code, host_id=host_id, theme=self._theme)
                list_item = QListWidgetItem()
                list_item.setData(Qt.UserRole, host_id)
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
                    min-width: 0px;
                    max-width: 26px;
                    min-height: 26px;
                    max-height: 26px;
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
                    min-width: 0px;
                    max-width: 26px;
                    min-height: 26px;
                    max-height: 26px;
                }}
                QPushButton:hover {{
                    background-color: {'#172554' if is_dark else '#eff6ff'};
                    border-color: #3b82f6;
                }}
            """)
        if hasattr(self, '_status_combo') and self._status_combo:
            self._status_combo.setStyleSheet(get_combobox_style(theme))
        if hasattr(self, '_list') and self._list:
            self._list.setStyleSheet(self._get_list_style(theme))
        self._update_dock_buttons()
        self.refresh()

    def set_floating_mode(self, is_floating: bool, is_pinned: bool = True):
        """Переключение между встроенным режимом (в сплиттере) и плавающим HUD"""
        self.is_floating = is_floating
        self.is_pinned = is_pinned
        if hasattr(self, '_btn_pin') and self._btn_pin:
            self._btn_pin.setVisible(is_floating)
        self._update_dock_buttons()

    def _on_pin_clicked(self):
        """Клик по булавке 'Поверх всех окон'"""
        self.is_pinned = not self.is_pinned
        self._update_dock_buttons()
        self.pin_toggle_requested.emit(self.is_pinned)

    def _update_dock_buttons(self):
        """Обновление стилей и иконок кнопок открепления и булавки"""
        is_dark = self._theme in ("dark", "tactical")
        btn_base = f"""
            QPushButton {{
                background-color: {'#1e222b' if is_dark else '#f8fafc'};
                border: 1px solid {'#2a2f3d' if is_dark else '#d0d7de'};
                border-radius: 5px;
                padding: 3px;
                min-width: 0px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
            }}
            QPushButton:hover {{
                background-color: {'#172554' if is_dark else '#eff6ff'};
                border-color: #3b82f6;
            }}
        """

        if hasattr(self, '_btn_dock') and self._btn_dock:
            self._btn_dock.setStyleSheet(btn_base)
            if self.is_floating:
                self._btn_dock.setToolTip("Прикрепить обратно к главному окну")
                self._btn_dock.setIcon(UIComponents._get_qicon(get_svg_dock(self._theme), 14))
            else:
                self._btn_dock.setToolTip("Открепить в плавающее окно (HUD)")
                self._btn_dock.setIcon(UIComponents._get_qicon(get_svg_popout(self._theme), 14))

        if hasattr(self, '_btn_pin') and self._btn_pin:
            pin_border = '#39FF14' if self._theme == 'tactical' else '#3b82f6'
            if self.is_pinned:
                self._btn_pin.setToolTip("Отключить 'Поверх всех окон'")
                self._btn_pin.setIcon(UIComponents._get_qicon(get_svg_pin(self._theme, True), 14))
                self._btn_pin.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {'#172554' if is_dark else '#eff6ff'};
                        border: 1px solid {pin_border};
                        border-radius: 5px;
                        padding: 3px;
                        min-width: 0px;
                        max-width: 26px;
                        min-height: 26px;
                        max-height: 26px;
                    }}
                    QPushButton:hover {{
                        background-color: {'#1e3a8a' if is_dark else '#dbeafe'};
                        border-color: {pin_border};
                    }}
                """)
            else:
                self._btn_pin.setToolTip("Включить 'Поверх всех окон'")
                self._btn_pin.setIcon(UIComponents._get_qicon(get_svg_pin(self._theme, False), 14))
                self._btn_pin.setStyleSheet(btn_base)

    @staticmethod
    def _get_list_style(theme: str) -> str:
        is_dark = theme in ("dark", "tactical")
        if theme == "tactical":
            bg = "#090A0F"
            handle = "#1F232D"
            hover = "#64748B"
        elif is_dark:
            bg = "#181c26"
            handle = "#282e3d"
            hover = "#3b82f6"
        else:
            bg = "#f8fafc"
            handle = "#cbd5e1"
            hover = "#94a3b8"

        return f"""
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background-color: transparent;
                border: none;
                padding: 4px 0px;
            }}
            QScrollBar:vertical {{
                background-color: {bg};
                width: 8px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {handle};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """


class FloatingEventLogWindow(QWidget):
    """
    Плавающее верхнеуровневое HUD-окно журнала событий с режимом 'Поверх всех окон'.
    Позволяет операторам непрерывно наблюдать за потоком сбоев/восстановлений узлов
    поверх любых приложений, даже когда главное окно свернуто.
    """

    dock_requested = pyqtSignal()

    def __init__(self, parent=None, theme: str = "dark"):
        super().__init__(parent, Qt.Window)
        self._theme = theme
        self._panel: Optional[EventLogPanel] = None
        self._on_top = True

        self.setWindowTitle("Журнал событий — Live Feed")
        self.resize(360, 520)
        self.setMinimumSize(280, 300)

        self._set_window_icon()
        set_dark_titlebar(self, self._theme in ("dark", "tactical"))

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.setWindowFlag(Qt.WindowStaysOnTopHint, self._on_top)

    def _set_window_icon(self):
        """Установка иконки окна из фирменного SVG"""
        from PyQt5.QtGui import QIcon, QPixmap, QPainter
        from PyQt5.QtSvg import QSvgRenderer
        from PyQt5.QtCore import QByteArray
        svg_data = get_svg_app_icon(self._theme)
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self.setWindowIcon(QIcon(pixmap))

    def set_panel(self, panel: EventLogPanel):
        """Перенос панели журнала внутрь плавающего окна"""
        if self._panel and self._panel != panel:
            self.take_panel()
        self._panel = panel
        panel.setParent(self)
        self._layout.addWidget(panel)
        panel.show()

    def take_panel(self) -> Optional[EventLogPanel]:
        """Извлечение панели для возврата в главное окно"""
        if self._panel:
            panel = self._panel
            self._layout.removeWidget(panel)
            panel.setParent(None)
            self._panel = None
            return panel
        return None

    def current_panel(self) -> Optional[EventLogPanel]:
        return self._panel

    def set_on_top(self, on_top: bool):
        """Включение/выключение флага 'Поверх всех окон'"""
        self._on_top = on_top
        geom = self.geometry()
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on_top)
        self.setGeometry(geom)
        if was_visible:
            self.show()
            self.raise_()

    def is_on_top(self) -> bool:
        return self._on_top

    def set_theme(self, theme: str):
        self._theme = theme
        self._set_window_icon()
        set_dark_titlebar(self, theme in ("dark", "tactical"))
        if self._panel:
            self._panel.set_theme(theme)

    def closeEvent(self, event):
        """При закрытии плавающего окна возвращаем панель в главное окно"""
        self.dock_requested.emit()
        event.accept()


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
        UIComponents.setup_combobox(self._group_combo, self._theme)
        self._group_combo.addItem("Все группы")
        self._group_combo.addItems(self._groups)
        self._group_combo.currentIndexChanged.connect(self._refresh)
        filters_layout.addWidget(self._group_combo, 1)

        self._status_combo = QComboBox()
        UIComponents.setup_combobox(self._status_combo, self._theme)
        for title, _code in self.STATUS_FILTER_OPTIONS:
            self._status_combo.addItem(title)
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
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
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
            host_id = ev.get("host_id", "")
            time_item = QTableWidgetItem(_format_ts(ev["timestamp"]))
            time_item.setData(Qt.UserRole, host_id)
            name_item = QTableWidgetItem(ev.get("host_name") or ev.get("host_id", ""))
            name_item.setData(Qt.UserRole, host_id)
            ip_item = QTableWidgetItem(ev.get("ip", ""))
            ip_item.setData(Qt.UserRole, host_id)
            group_item = QTableWidgetItem(ev.get("group", ""))
            group_item.setData(Qt.UserRole, host_id)
            old_item = QTableWidgetItem(_status_title(ev.get("old_status")))
            old_item.setData(Qt.UserRole, host_id)
            new_item = QTableWidgetItem(_status_title(ev.get("new_status")))
            new_item.setData(Qt.UserRole, host_id)

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

    def _on_table_context_menu(self, pos: QPoint):
        """Контекстное меню таблицы общего журнала событий"""
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        item = self._table.item(row, 0)
        host_id = item.data(Qt.UserRole) if item else None
        if host_id:
            global_pos = self._table.viewport().mapToGlobal(pos)
            parent = self.parent()
            if parent and hasattr(parent, "_context_menu_manager") and parent._context_menu_manager:
                parent._context_menu_manager.show_context_menu_for_host_id(host_id, global_pos)
