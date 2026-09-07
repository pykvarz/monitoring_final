#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диалоговые окна
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QDialogButtonBox, QMessageBox, QGroupBox,
    QSpinBox, QVBoxLayout as QVBox, QLabel
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QByteArray

from models import Host, AppConfig, validate_ip_or_hostname
from constants import get_svg_add_host, get_svg_settings


class HostDialog(QDialog):
    """Диалог добавления/редактирования узла"""

    def __init__(self, parent=None, host: Host = None, groups: list = None):
        super().__init__(parent)
        self._host = host
        self._groups = groups or ["Без группы"]
        self._set_window_icon()
        self._init_ui()

    def _set_window_icon(self):
        """Установка иконки окна из SVG"""
        # Определяем тему из родительского окна, если возможно
        theme = "light"
        if self.parent() and hasattr(self.parent(), '_config'):
            theme = getattr(self.parent()._config, 'theme', 'light')
            
        svg_data = get_svg_add_host(theme)
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self.setWindowIcon(QIcon(pixmap))

    def _init_ui(self) -> None:
        self.setWindowTitle("Редактировать узел" if self._host else "Добавить узел")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Поля ввода
        self._name_edit = QLineEdit(self._host.name if self._host else "")
        self._name_edit.setPlaceholderText("Например: Сервер 1")
        self._name_edit.setMaxLength(50)

        self._ip_edit = QLineEdit(self._host.ip if self._host else "")
        self._ip_edit.setPlaceholderText("Например: 192.168.1.1")
        self._ip_edit.setMaxLength(100) # Лимит для IP/Hostname

        self._address_edit = QLineEdit(self._host.address if self._host else "")
        self._address_edit.setPlaceholderText("Например: Москва, ул. Ленина, д.1")
        self._address_edit.setMaxLength(150)

        self._group_combo = QComboBox()
        self._group_combo.setEditable(True)
        self._group_combo.lineEdit().setMaxLength(50) # Лимит на название группы
        self._group_combo.addItems(self._groups)
        if self._host and self._host.group in self._groups:
            self._group_combo.setCurrentText(self._host.group)

        # Чекбокс уведомлений
        self._notify_check = QCheckBox("Включить уведомления для этого узла")
        self._notify_check.setChecked(self._host.notifications_enabled if self._host else True)

        form_layout.addRow("Название*:", self._name_edit)
        form_layout.addRow("IP адрес*:", self._ip_edit)
        form_layout.addRow("Адрес:", self._address_edit)
        form_layout.addRow("Группа:", self._group_combo)

        layout.addLayout(form_layout)
        layout.addSpacing(10)
        layout.addWidget(self._notify_check)
        layout.addSpacing(10)

        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        self._ok_button = buttons.button(QDialogButtonBox.Ok)
        self._ok_button.setEnabled(False)

        # Валидация в реальном времени
        self._name_edit.textChanged.connect(self._validate_fields)
        self._ip_edit.textChanged.connect(self._validate_fields)
        self._address_edit.textChanged.connect(self._validate_fields)
        self._group_combo.currentTextChanged.connect(self._validate_fields)

        layout.addWidget(buttons)
        self.setLayout(layout)
        
        # Первичная валидация
        self._validate_fields()

    def _validate_fields(self) -> None:
        """Валидация полей"""
        name_valid = bool(self._name_edit.text().strip())
        ip_valid = validate_ip_or_hostname(self._ip_edit.text().strip())
        self._ok_button.setEnabled(name_valid and ip_valid)

        # Подсветка невалидных полей
        if self._ip_edit.text().strip():
            if not validate_ip_or_hostname(self._ip_edit.text().strip()):
                self._ip_edit.setStyleSheet("border: 1px solid #dc3545;")
            else:
                self._ip_edit.setStyleSheet("border: 1px solid #28a745;")
        else:
            self._ip_edit.setStyleSheet("")

    def _validate_and_accept(self) -> None:
        """Валидация и принятие формы"""
        if not validate_ip_or_hostname(self._ip_edit.text().strip()):
            QMessageBox.warning(self, "Ошибка", "Неверный формат IP-адреса или имени узла!")
            return
        self.accept()

    def get_host(self) -> Host:
        """Получение данных узла"""
        if self._host:
            self._host.name = self._name_edit.text().strip()
            self._host.ip = self._ip_edit.text().strip()
            self._host.address = self._address_edit.text().strip()
            self._host.group = self._group_combo.currentText() or "Без группы"
            self._host.notifications_enabled = self._notify_check.isChecked()
            return self._host
        else:
            return Host(
                name=self._name_edit.text().strip(),
                ip=self._ip_edit.text().strip(),
                address=self._address_edit.text().strip(),
                group=self._group_combo.currentText() or "Без группы",
                notifications_enabled=self._notify_check.isChecked()
            )


class SettingsDialog(QDialog):
    """Диалог настроек приложения"""

    def __init__(self, parent=None, config: AppConfig = None):
        super().__init__(parent)
        self._config = config or AppConfig()
        self._set_window_icon()
        self._init_ui()

    def _set_window_icon(self):
        """Установка иконки окна из SVG"""
        # Определяем тему из родительского окна, если возможно
        theme = "light"
        if self.parent() and hasattr(self.parent(), '_config'):
            theme = getattr(self.parent()._config, 'theme', 'light')
            
        svg_data = get_svg_settings(theme)
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self.setWindowIcon(QIcon(pixmap))

    def _init_ui(self):
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout()

        # Группа: Таймауты
        timeout_group = QGroupBox("Интервалы опроса")
        timeout_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        timeout_layout = QFormLayout()
        timeout_layout.setLabelAlignment(Qt.AlignRight)

        # Интервал опроса
        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(5, 300)
        self._poll_spin.setSuffix(" сек")
        self._poll_spin.setValue(self._config.poll_interval)
        self._poll_spin.setToolTip("Как часто проверять доступность узлов")

        # Таймаут "Ожидание"
        self._waiting_spin = QSpinBox()
        self._waiting_spin.setRange(10, 600)
        self._waiting_spin.setSuffix(" сек")
        self._waiting_spin.setValue(self._config.waiting_timeout)
        self._waiting_spin.setToolTip("Через какое время узел переходит в статус 'Ожидание'")

        # Таймаут "Offline"
        self._offline_spin = QSpinBox()
        self._offline_spin.setRange(60, 3600)
        self._offline_spin.setSuffix(" сек")
        self._offline_spin.setValue(self._config.offline_timeout)
        self._poll_spin.setToolTip("Через какое время узел переходит в статус 'Offline'")

        timeout_layout.addRow("Интервал опроса:", self._poll_spin)
        timeout_layout.addRow("Время до 'Ожидание':", self._waiting_spin)
        timeout_layout.addRow("Время до 'Offline':", self._offline_spin)
        timeout_group.setLayout(timeout_layout)

        # Группа: Производительность
        perf_group = QGroupBox("Производительность")
        perf_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        perf_layout = QFormLayout()
        perf_layout.setLabelAlignment(Qt.AlignRight)

        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(5, 100)
        self._workers_spin.setSuffix(" потоков")
        self._workers_spin.setValue(self._config.max_workers)
        self._workers_spin.setToolTip("Количество одновременных ping запросов")

        perf_layout.addRow("Макс. потоков:", self._workers_spin)
        perf_group.setLayout(perf_layout)

        # Группа: Уведомления
        notify_group = QGroupBox("Уведомления")
        notify_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        notify_layout = QVBox()
        notify_layout.setContentsMargins(10, 20, 10, 10)

        self._notify_enabled = QCheckBox("Включить уведомления")
        self._notify_enabled.setChecked(self._config.notifications_enabled)
        self._notify_enabled.setToolTip("Глобальное включение/отключение всех уведомлений")

        self._sound_enabled = QCheckBox("Звуковые уведомления")
        self._sound_enabled.setChecked(self._config.sound_enabled)
        self._sound_enabled.setToolTip("Проигрывать системный звук при уведомлениях")

        notify_layout.addWidget(self._notify_enabled)
        notify_layout.addWidget(self._sound_enabled)
        notify_group.setLayout(notify_layout)

        # Группа: Журнал истории
        history_group = QGroupBox("Журнал событий")
        history_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        history_layout = QFormLayout()
        history_layout.setLabelAlignment(Qt.AlignRight)

        self._retention_spin = QSpinBox()
        self._retention_spin.setRange(0, 3650)
        self._retention_spin.setSuffix(" дней")
        self._retention_spin.setSpecialValueText("Бессрочно")
        self._retention_spin.setValue(getattr(self._config, 'history_retention_days', 90))
        self._retention_spin.setToolTip(
            "Сколько дней хранить историю падений/восстановлений узлов.\n"
            "0 = хранить бессрочно, ничего не удалять."
        )

        history_layout.addRow("Хранить историю:", self._retention_spin)
        history_group.setLayout(history_layout)

        # Группа: Интеграция с Helpdesk
        helpdesk_group = QGroupBox("Интеграция с Helpdesk")
        helpdesk_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        helpdesk_layout = QFormLayout()
        helpdesk_layout.setLabelAlignment(Qt.AlignRight)
        
        self._hd_enabled = QCheckBox("Включить интеграцию (Playwright)")
        self._hd_enabled.setChecked(getattr(self._config, 'helpdesk_enabled', False))
        
        self._hd_url = QLineEdit(getattr(self._config, 'helpdesk_url', ''))
        self._hd_url.setPlaceholderText("https://helpdesk.company.com/create")
        
        helpdesk_layout.addRow("", self._hd_enabled)
        helpdesk_layout.addRow("URL создания заявки:", self._hd_url)
        helpdesk_group.setLayout(helpdesk_layout)

        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(timeout_group)
        layout.addWidget(perf_group)
        layout.addWidget(notify_group)
        layout.addWidget(history_group)
        layout.addWidget(helpdesk_group)
        layout.addStretch()
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_config(self) -> AppConfig:
        """Получение конфигурации.

        Диалог редактирует только часть полей AppConfig (таймауты, потоки,
        уведомления). Остальные поля (тема, порядок/ширина/видимость столбцов,
        пользовательские группы) не показаны в этом окне и должны сохраняться
        такими, какими они были — иначе каждое нажатие OK тут будет незаметно
        сбрасывать их на значения по умолчанию.
        """
        return AppConfig(
            poll_interval=self._poll_spin.value(),
            waiting_timeout=self._waiting_spin.value(),
            offline_timeout=self._offline_spin.value(),
            notifications_enabled=self._notify_enabled.isChecked(),
            sound_enabled=self._sound_enabled.isChecked(),
            max_workers=self._workers_spin.value(),
            history_retention_days=self._retention_spin.value(),
            helpdesk_enabled=self._hd_enabled.isChecked(),
            helpdesk_url=self._hd_url.text().strip(),
            column_widths=dict(self._config.column_widths),
            column_order=list(self._config.column_order),
            hidden_columns=list(self._config.hidden_columns),
            theme=self._config.theme,
            custom_groups=list(self._config.custom_groups),
        )