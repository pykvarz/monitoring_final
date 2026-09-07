#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль всплывающих уведомлений (Toast Notifications) для Network Monitor.
Обеспечивает современный интерфейс уведомлений в приложении с плавной анимацией,
поддержкой темной/светлой темы и автоматическим стекированием.
"""

from typing import List, Optional
from datetime import datetime
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy
)
from PyQt5.QtGui import QColor, QFont, QCursor


class ToastType:
    OFFLINE = "offline"
    RECOVERED = "recovered"
    WARNING = "warning"
    INFO = "info"


class ToastNotification(QFrame):
    """
    Отдельная карточка всплывающего уведомления с современным дизайном:
    - Полупрозрачная карточка с цветным левым акцентом
    - Бейдж со статусной иконкой
    - Список узлов с аккуратными тегами
    - Плавная анимация появления и затухания
    - Остановка таймера авто-закрытия при наведении курсора
    """

    dismissed = pyqtSignal(object)  # Сигнал при закрытии, передает self

    def __init__(
        self,
        parent: QWidget,
        toast_type: str,
        title: str,
        message: str = "",
        hosts: Optional[List[str]] = None,
        duration_ms: int = 6000,
        theme: str = "dark"
    ):
        super().__init__(parent)
        self._toast_type = toast_type
        self._title = title
        self._message = message
        self._hosts = hosts or []
        self._duration_ms = duration_ms
        self._theme = theme
        self._is_closing = False

        self._init_ui()
        self._init_animations()
        self._init_timer()

    def _get_colors(self):
        """Палитра цветов в зависимости от типа и темы"""
        is_dark = self._theme == "dark"

        type_colors = {
            ToastType.OFFLINE: {
                "accent": "#ef4444",
                "accent_bg": "rgba(239, 68, 68, 0.16)",
                "icon": "⚠️",
                "badge_border": "rgba(239, 68, 68, 0.4)",
            },
            ToastType.RECOVERED: {
                "accent": "#10b981",
                "accent_bg": "rgba(16, 185, 129, 0.16)",
                "icon": "✅",
                "badge_border": "rgba(16, 185, 129, 0.4)",
            },
            ToastType.WARNING: {
                "accent": "#f59e0b",
                "accent_bg": "rgba(245, 158, 11, 0.16)",
                "icon": "⏸",
                "badge_border": "rgba(245, 158, 11, 0.4)",
            },
            ToastType.INFO: {
                "accent": "#3b82f6",
                "accent_bg": "rgba(59, 130, 246, 0.16)",
                "icon": "ℹ️",
                "badge_border": "rgba(59, 130, 246, 0.4)",
            }
        }

        cfg = type_colors.get(self._toast_type, type_colors[ToastType.INFO])

        if is_dark:
            cfg.update({
                "bg": "#181d27",
                "border": "#2c3445",
                "title_color": "#f8fafc",
                "text_color": "#cbd5e1",
                "muted_color": "#94a3b8",
                "tag_bg": "#222938",
                "tag_border": "#333e54",
                "tag_color": "#f1f5f9",
                "shadow": QColor(0, 0, 0, 140),
            })
        else:
            cfg.update({
                "bg": "#ffffff",
                "border": "#e2e8f0",
                "title_color": "#0f172a",
                "text_color": "#334155",
                "muted_color": "#64748b",
                "tag_bg": "#f1f5f9",
                "tag_border": "#cbd5e1",
                "tag_color": "#1e293b",
                "shadow": QColor(0, 0, 0, 35),
            })

        return cfg

    def _init_ui(self):
        c = self._get_colors()
        self.setFixedWidth(360)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet(f"""
            ToastNotification {{
                background-color: {c['bg']};
                border: 1px solid {c['border']};
                border-left: 5px solid {c['accent']};
                border-radius: 9px;
            }}
        """)

        # Тень
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(c['shadow'])
        self.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(6)

        # Верхняя строка: Иконка + Заголовок + Время + Кнопка закрытия
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.setContentsMargins(0, 0, 0, 0)

        # Иконка-бейдж
        icon_lbl = QLabel(c['icon'])
        icon_lbl.setFixedSize(26, 26)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {c['accent_bg']};
                border: 1px solid {c['badge_border']};
                border-radius: 13px;
                font-size: 13px;
            }}
        """)
        top_row.addWidget(icon_lbl)

        # Заголовок
        title_lbl = QLabel(self._title)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet(f"color: {c['title_color']}; border: none; background: transparent;")
        top_row.addWidget(title_lbl, 1)

        # Время
        time_str = datetime.now().strftime("%H:%M")
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet(f"color: {c['muted_color']}; font-size: 11px; border: none; background: transparent;")
        top_row.addWidget(time_lbl)

        # Кнопка закрытия
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        btn_close.setStyleSheet(f"""
            QPushButton {{
                color: {c['muted_color']};
                background: transparent;
                border: none;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {c['accent']};
            }}
        """)
        btn_close.clicked.connect(self.close_toast)
        top_row.addWidget(btn_close)

        main_layout.addLayout(top_row)

        # Сообщение или теги узлов
        if self._hosts:
            hosts_layout = QHBoxLayout()
            hosts_layout.setSpacing(6)
            hosts_layout.setContentsMargins(34, 0, 0, 0)

            # Отображаем первые 3 узла как красивые теги
            display_hosts = self._hosts[:3]
            for host_name in display_hosts:
                tag = QLabel(str(host_name))
                tag.setStyleSheet(f"""
                    QLabel {{
                        background-color: {c['tag_bg']};
                        border: 1px solid {c['tag_border']};
                        color: {c['tag_color']};
                        border-radius: 5px;
                        padding: 2px 8px;
                        font-size: 11px;
                        font-weight: 600;
                    }}
                """)
                hosts_layout.addWidget(tag)

            if len(self._hosts) > 3:
                more_tag = QLabel(f"+{len(self._hosts) - 3}")
                more_tag.setStyleSheet(f"""
                    QLabel {{
                        background-color: {c['accent_bg']};
                        border: 1px solid {c['badge_border']};
                        color: {c['accent']};
                        border-radius: 5px;
                        padding: 2px 6px;
                        font-size: 11px;
                        font-weight: bold;
                    }}
                """)
                hosts_layout.addWidget(more_tag)

            hosts_layout.addStretch()
            main_layout.addLayout(hosts_layout)

        elif self._message:
            msg_lbl = QLabel(self._message)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet(f"color: {c['text_color']}; font-size: 11px; margin-left: 34px; border: none; background: transparent;")
            main_layout.addWidget(msg_lbl)

        self.adjustSize()

    def _init_animations(self):
        """Настройка плавного появления"""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(220)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

    def _init_timer(self):
        """Таймер закрытия"""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._duration_ms)
        self._timer.timeout.connect(self.close_toast)

    def show_toast(self):
        """Отобразить с анимацией"""
        self.show()
        self.raise_()
        self._fade_anim.start()
        self._timer.start()

    def close_toast(self):
        """Плавное закрытие карточки"""
        if self._is_closing:
            return
        self._is_closing = True
        self._timer.stop()

        self._close_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._close_anim.setDuration(200)
        self._close_anim.setStartValue(self._opacity_effect.opacity())
        self._close_anim.setEndValue(0.0)
        self._close_anim.setEasingCurve(QEasingCurve.InCubic)
        self._close_anim.finished.connect(self._on_closed)
        self._close_anim.start()

    def _on_closed(self):
        self.dismissed.emit(self)
        self.deleteLater()

    def enterEvent(self, event):
        """При наведении мыши — приостанавливаем таймер закрытия"""
        if self._timer.isActive():
            self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """При уходе мыши — даем еще 2.5 секунды на чтение"""
        if not self._is_closing:
            self._timer.start(2500)
        super().leaveEvent(event)


class ToastManager(QObject):
    """
    Менеджер всплывающих уведомлений для главного окна:
    - Стек уведомлений в правом нижнем углу
    - Автоматический пересчет позиций
    - Поддержка тем оформления
    """

    def __init__(self, parent_widget: QWidget, get_theme_fn=None):
        super().__init__(parent_widget)
        self._parent = parent_widget
        self._get_theme_fn = get_theme_fn or (lambda: "dark")
        self._active_toasts: List[ToastNotification] = []
        self._max_toasts = 4

    def _get_current_theme(self) -> str:
        try:
            return self._get_theme_fn()
        except Exception:
            return "dark"

    def show_offline(self, hosts: List[str]):
        """Показ уведомления об упавших узлах"""
        if not hosts:
            return
        count = len(hosts)
        title = "⚠️ Узел недоступен" if count == 1 else f"⚠️ Недоступно узлов: {count}"
        self._add_toast(ToastType.OFFLINE, title, hosts=hosts)

    def show_recovered(self, hosts: List[str]):
        """Показ уведомления о восстановлении узлов"""
        if not hosts:
            return
        count = len(hosts)
        title = "✅ Узел восстановлен" if count == 1 else f"✅ Восстановлено узлов: {count}"
        self._add_toast(ToastType.RECOVERED, title, hosts=hosts)

    def show_pause(self, is_paused: bool):
        """Показ уведомления о паузе / возобновлении мониторинга"""
        if is_paused:
            self._add_toast(
                ToastType.WARNING,
                "⏸ Мониторинг на паузе",
                message="Проверка узлов приостановлена. Нажмите кнопку паузы для продолжения.",
                duration_ms=4000
            )
        else:
            self._add_toast(
                ToastType.INFO,
                "▶️ Мониторинг возобновлен",
                message="Проверка узлов сети снова активна.",
                duration_ms=3500
            )

    def show_info(self, title: str, message: str = ""):
        """Показ информационного уведомления"""
        self._add_toast(ToastType.INFO, title, message=message)

    def _add_toast(
        self,
        toast_type: str,
        title: str,
        message: str = "",
        hosts: Optional[List[str]] = None,
        duration_ms: int = 6000
    ):
        # Если накопилось больше допустимого — закрываем самое старое
        while len(self._active_toasts) >= self._max_toasts:
            oldest = self._active_toasts.pop(0)
            oldest.close_toast()

        theme = self._get_current_theme()
        toast = ToastNotification(
            parent=self._parent,
            toast_type=toast_type,
            title=title,
            message=message,
            hosts=hosts,
            duration_ms=duration_ms,
            theme=theme
        )
        toast.dismissed.connect(self._on_toast_dismissed)
        self._active_toasts.append(toast)

        self.reposition_toasts()
        toast.show_toast()

    def _on_toast_dismissed(self, toast: ToastNotification):
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)
        self.reposition_toasts()

    def reposition_toasts(self):
        """Пересчет позиций всех активных тостов (снизу вверх)"""
        if not self._parent:
            return

        parent_rect = self._parent.rect()
        margin_right = 24
        margin_bottom = 36  # над статус баром
        spacing = 10

        curr_y = parent_rect.height() - margin_bottom

        for toast in reversed(self._active_toasts):
            toast_h = toast.sizeHint().height() or toast.height()
            toast_w = toast.width()
            target_x = parent_rect.width() - toast_w - margin_right
            target_y = curr_y - toast_h

            toast.move(target_x, target_y)
            curr_y = target_y - spacing
