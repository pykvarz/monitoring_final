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
        parent: Optional[QWidget] = None,
        toast_type: str = ToastType.INFO,
        title: str = "",
        message: str = "",
        hosts: Optional[List[str]] = None,
        duration_ms: int = 6000,
        theme: str = "dark"
    ):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoFocus
        super().__init__(parent, flags)
        self._toast_type = toast_type
        self._title = title
        self._message = message
        self._hosts = hosts or []
        self._duration_ms = duration_ms
        self._theme = theme
        self._is_closing = False

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._init_ui()
        self._init_animations()
        self._init_timer()

    def _get_colors(self):
        """Палитра цветов в зависимости от типа и темы"""
        is_dark = self._theme in ("dark", "tactical")
        is_tactical = self._theme == "tactical"

        type_colors = {
            ToastType.OFFLINE: {
                "accent": "#ef4444",
                "accent_bg": "rgba(239, 68, 68, 0.16)",
                "icon": "●",
                "badge_border": "rgba(239, 68, 68, 0.4)",
            },
            ToastType.RECOVERED: {
                "accent": "#10b981",
                "accent_bg": "rgba(16, 185, 129, 0.16)",
                "icon": "●",
                "badge_border": "rgba(16, 185, 129, 0.4)",
            },
            ToastType.WARNING: {
                "accent": "#f59e0b",
                "accent_bg": "rgba(245, 158, 11, 0.16)",
                "icon": "●",
                "badge_border": "rgba(245, 158, 11, 0.4)",
            },
            ToastType.INFO: {
                "accent": "#3b82f6",
                "accent_bg": "rgba(59, 130, 246, 0.16)",
                "icon": "●",
                "badge_border": "rgba(59, 130, 246, 0.4)",
            }
        }

        cfg = type_colors.get(self._toast_type, type_colors[ToastType.INFO])

        if is_tactical:
            cfg.update({
                "bg": "#0D1117",
                "border": "#1F232D",
                "title_color": "#E2E8F0",
                "text_color": "#C9D1D9",
                "muted_color": "#6E7681",
                "tag_bg": "#161B22",
                "tag_border": "#30363D",
                "tag_color": "#E2E8F0",
                "shadow": QColor(0, 0, 0, 180),
            })
        elif is_dark:
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
                "title_color": "#1e293b",
                "text_color": "#475569",
                "muted_color": "#64748b",
                "tag_bg": "#f1f5f9",
                "tag_border": "#cbd5e1",
                "tag_color": "#1e293b",
                "shadow": QColor(0, 0, 0, 40),
            })

        return cfg

    def _init_ui(self):
        c = self._get_colors()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("ToastNotification { background: transparent; border: none; }")

        # Внутренняя карточка со стилями, рамкой и скруглениями
        self._card = QFrame(self)
        self._card.setObjectName("toast_card")
        self._card.setFixedWidth(360)
        self._card.setStyleSheet(f"""
            QFrame#toast_card {{
                background-color: {c['bg']};
                border: 1px solid {c['border']};
                border-left: 5px solid {c['accent']};
                border-radius: 9px;
            }}
        """)

        # Тень на карточке (мягко размывается в пределах прозрачных отступов окна)
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(c['shadow'])
        self._card.setGraphicsEffect(shadow)

        # Корневой layout с отступами под размытие тени
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._card)

        # Layout внутри карточки
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

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

        card_layout.addLayout(top_row)

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
            card_layout.addLayout(hosts_layout)

        elif self._message:
            msg_lbl = QLabel(self._message)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet(f"color: {c['text_color']}; font-size: 11px; margin-left: 34px; border: none; background: transparent;")
            card_layout.addWidget(msg_lbl)

        self._card.adjustSize()
        self.adjustSize()

    def _init_animations(self):
        """Настройка плавного появления"""
        self.setWindowOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
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

        self._close_anim = QPropertyAnimation(self, b"windowOpacity")
        self._close_anim.setDuration(200)
        self._close_anim.setStartValue(self.windowOpacity())
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
    Менеджер всплывающих уведомлений на рабочем столе:
    - Стек Desktop-уведомлений в правом нижнем углу над панелью задач
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
        title = "Узел недоступен" if count == 1 else f"Недоступно узлов: {count}"
        self._add_toast(ToastType.OFFLINE, title, hosts=hosts)

    def show_recovered(self, hosts: List[str]):
        """Показ уведомления о восстановлении узлов"""
        if not hosts:
            return
        count = len(hosts)
        title = "Узел восстановлен" if count == 1 else f"Восстановлено узлов: {count}"
        self._add_toast(ToastType.RECOVERED, title, hosts=hosts)

    def show_pause(self, is_paused: bool):
        """Показ уведомления о паузе / возобновлении мониторинга"""
        if is_paused:
            self._add_toast(
                ToastType.WARNING,
                "Мониторинг на паузе",
                message="Проверка узлов приостановлена. Нажмите кнопку паузы для продолжения.",
                duration_ms=4000
            )
        else:
            self._add_toast(
                ToastType.INFO,
                "Мониторинг возобновлен",
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

    def close_all(self):
        """Закрыть все активные уведомления"""
        for toast in list(self._active_toasts):
            toast.close_toast()

    def reposition_toasts(self):
        """Пересчет позиций всех активных тостов на рабочем столе (снизу вверх над панелью задач)"""
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        screen = None
        if self._parent and hasattr(self._parent, "windowHandle") and self._parent.windowHandle():
            screen = self._parent.windowHandle().screen()
        if not screen and app:
            screen = app.primaryScreen()

        if screen:
            geo = screen.availableGeometry()
        elif hasattr(self._parent, "screen") and self._parent and self._parent.screen():
            geo = self._parent.screen().availableGeometry()
        elif self._parent and hasattr(self._parent, "rect"):
            geo = self._parent.rect()
        else:
            from PyQt5.QtWidgets import QDesktopWidget
            geo = QDesktopWidget().availableGeometry()

        margin_right = 16
        margin_bottom = 16
        spacing = 8

        curr_y = geo.bottom() - margin_bottom

        for toast in reversed(self._active_toasts):
            toast_h = toast.sizeHint().height() or toast.height() or 70
            toast_w = toast.width() or 380
            target_x = geo.right() - toast_w - margin_right
            target_y = curr_y - toast_h

            toast.move(target_x, target_y)
            curr_y = target_y - spacing

