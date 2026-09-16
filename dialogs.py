#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диалоговые окна
"""

from typing import Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QDialogButtonBox, QMessageBox, QGroupBox,
    QSpinBox, QVBoxLayout as QVBox, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout, QPushButton, QInputDialog
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QByteArray

from models import Host, AppConfig, validate_ip_or_hostname
from constants import (
    get_svg_add_host, get_svg_settings, get_main_style, get_combobox_style,
    get_svg_add_group, get_svg_edit, get_svg_delete
)
from theme_manager import set_dark_titlebar
from ui_components import UIComponents


class HostDialog(QDialog):
    """Диалог добавления/редактирования узла"""

    def __init__(self, parent=None, host: Host = None, groups: list = None):
        super().__init__(parent)
        self._host = host
        self._groups = groups or ["Без группы"]
        self._theme = "dark"
        if self.parent() and hasattr(self.parent(), '_config'):
            self._theme = getattr(self.parent()._config, 'theme', 'dark')
        self._set_window_icon()
        self._init_ui()

    def _set_window_icon(self):
        """Установка иконки окна из SVG"""
        theme = self._theme
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
        self.setStyleSheet(get_main_style(self._theme))
        set_dark_titlebar(self, self._theme in ("dark", "tactical"))

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
        UIComponents.setup_combobox(self._group_combo, self._theme)
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
                self._ip_edit.setStyleSheet("border: 1px solid #ef4444;")
            else:
                self._ip_edit.setStyleSheet("border: 1px solid #10b981;")
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

    def __init__(self, parent=None, config: AppConfig = None, repository=None, storage=None):
        super().__init__(parent)
        self._config = config or AppConfig()
        self._repository = repository
        self._storage = storage
        self._theme = getattr(self._config, 'theme', 'dark')
        self._set_window_icon()
        self._init_ui()

    def _set_window_icon(self):
        """Установка иконки окна из SVG"""
        theme = self._theme
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
        self.setStyleSheet(get_main_style(self._theme))
        set_dark_titlebar(self, self._theme in ("dark", "tactical"))

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

        # Таймаут "Waiting"
        self._waiting_spin = QSpinBox()
        self._waiting_spin.setRange(10, 600)
        self._waiting_spin.setSuffix(" сек")
        self._waiting_spin.setValue(self._config.waiting_timeout)
        self._waiting_spin.setToolTip("Через какое время узел переходит в статус 'Waiting'")

        # Таймаут "Offline"
        self._offline_spin = QSpinBox()
        self._offline_spin.setRange(60, 3600)
        self._offline_spin.setSuffix(" сек")
        self._offline_spin.setValue(self._config.offline_timeout)
        self._offline_spin.setToolTip("Через какое время узел переходит в статус 'Offline'")

        timeout_layout.addRow("Интервал опроса:", self._poll_spin)
        timeout_layout.addRow("Время до 'Waiting':", self._waiting_spin)
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

        self._hd_headless = QCheckBox("Скрытый фоновый режим браузера (Headless)")
        self._hd_headless.setChecked(getattr(self._config, 'helpdesk_headless', False))
        self._hd_headless.setToolTip("Включено: браузер работает в фоне без показа окна.\nВыключено: на экране отображается окно браузера.")
        
        self._hd_url = QLineEdit(getattr(self._config, 'helpdesk_url', ''))
        self._hd_url.setPlaceholderText("https://helpdesk.company.com/create")
        
        reasons_list = getattr(self._config, 'helpdesk_reasons', ["без связи", "ошибка пинга", "техническое обслуживание"])
        self._hd_reasons = QLineEdit(", ".join(reasons_list))
        self._hd_reasons.setPlaceholderText("без связи, ошибка пинга, тех. работы")
        self._hd_reasons.setToolTip("Готовые варианты причин открытия заявки (через запятую)")

        reasons_rec_list = getattr(self._config, 'helpdesk_reasons_recovered', ["восстановление связи", "после ремонта"])
        self._hd_reasons_recovered = QLineEdit(", ".join(reasons_rec_list))
        self._hd_reasons_recovered.setPlaceholderText("восстановление связи, после ремонта")
        self._hd_reasons_recovered.setToolTip("Готовые варианты причин закрытия заявки (через запятую)")
        
        helpdesk_layout.addRow("", self._hd_enabled)
        helpdesk_layout.addRow("", self._hd_headless)
        helpdesk_layout.addRow("URL создания заявки:", self._hd_url)
        helpdesk_layout.addRow("Причины открытия:", self._hd_reasons)
        helpdesk_layout.addRow("Причины закрытия:", self._hd_reasons_recovered)
        helpdesk_group.setLayout(helpdesk_layout)

        # Группа: Внешний вид
        appearance_group = QGroupBox("Внешний вид")
        appearance_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        appearance_layout = QFormLayout()
        appearance_layout.setLabelAlignment(Qt.AlignRight)
        
        self._theme_combo = QComboBox()
        UIComponents.setup_combobox(self._theme_combo, self._theme)
        self._theme_combo.addItem("Dark", "dark")
        self._theme_combo.addItem("Tactical NOC", "tactical")
        idx = self._theme_combo.findData(self._theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        
        appearance_layout.addRow("Тема оформления:", self._theme_combo)
        appearance_group.setLayout(appearance_layout)

        # Группа: Группы узлов
        groups_box = QGroupBox("Группы узлов")
        groups_box.setStyleSheet("QGroupBox { font-weight: bold; }")
        groups_layout = QHBoxLayout()
        manage_groups_btn = QPushButton("Управление группами...")
        manage_groups_btn.setIcon(UIComponents._get_qicon(get_svg_edit(self._theme)))
        manage_groups_btn.clicked.connect(self._open_group_manager)
        if self._repository is None:
            manage_groups_btn.setEnabled(False)
        groups_layout.addWidget(manage_groups_btn)
        groups_layout.addStretch()
        groups_box.setLayout(groups_layout)

        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(timeout_group)
        layout.addWidget(perf_group)
        layout.addWidget(notify_group)
        layout.addWidget(history_group)
        layout.addWidget(helpdesk_group)
        layout.addWidget(appearance_group)
        layout.addWidget(groups_box)
        layout.addStretch()
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _open_group_manager(self):
        """Открытие диалога управления группами"""
        if self._repository is not None:
            dlg = GroupManagerDialog(self, repository=self._repository, config=self._config, storage=self._storage)
            dlg.exec_()

    def get_config(self) -> AppConfig:
        """Получение конфигурации.

        Диалог редактирует только часть полей AppConfig (таймауты, потоки,
        уведомления, тему). Остальные поля (порядок/ширина/видимость столбцов,
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
            helpdesk_headless=self._hd_headless.isChecked(),
            helpdesk_reasons=[r.strip() for r in self._hd_reasons.text().split(",") if r.strip()],
            helpdesk_reasons_recovered=[r.strip() for r in self._hd_reasons_recovered.text().split(",") if r.strip()],
            column_widths=dict(self._config.column_widths),
            column_order=list(self._config.column_order),
            hidden_columns=list(self._config.hidden_columns),
            theme=self._theme_combo.currentData(),
            custom_groups=list(self._config.custom_groups),
            splitter_sizes=list(self._config.splitter_sizes),
            event_log_floating=self._config.event_log_floating,
            event_log_on_top=self._config.event_log_on_top,
            event_log_geometry=list(self._config.event_log_geometry),
        )


class GroupManagerDialog(QDialog):
    """Диалог управления группами узлов (добавление, переименование, удаление)"""

    def __init__(self, parent=None, repository=None, config: AppConfig = None, storage=None):
        super().__init__(parent)
        self._repository = repository
        self._config = config or AppConfig()
        self._storage = storage
        self._theme = getattr(self._config, 'theme', 'dark')
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        self.setWindowTitle("Управление группами")
        self.setModal(True)
        self.setMinimumSize(420, 360)
        self.setStyleSheet(get_main_style(self._theme))
        set_dark_titlebar(self, self._theme in ("dark", "tactical"))

        layout = QVBoxLayout(self)

        header_lbl = QLabel("Список групп и количество узлов:")
        header_lbl.setStyleSheet("font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(header_lbl)

        content_layout = QHBoxLayout()

        self._list_widget = QListWidget()
        self._list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        content_layout.addWidget(self._list_widget)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_add = QPushButton("Добавить...")
        self._btn_add.setIcon(UIComponents._get_qicon(get_svg_add_group(self._theme)))
        self._btn_add.clicked.connect(self._on_add_group)

        self._btn_edit = QPushButton("Переименовать...")
        self._btn_edit.setIcon(UIComponents._get_qicon(get_svg_edit(self._theme)))
        self._btn_edit.clicked.connect(self._on_edit_group)
        self._btn_edit.setEnabled(False)

        self._btn_delete = QPushButton("Удалить")
        self._btn_delete.setIcon(UIComponents._get_qicon(get_svg_delete(self._theme)))
        self._btn_delete.clicked.connect(self._on_delete_group)
        self._btn_delete.setEnabled(False)

        btn_layout.addWidget(self._btn_add)
        btn_layout.addWidget(self._btn_edit)
        btn_layout.addWidget(self._btn_delete)
        btn_layout.addStretch()

        content_layout.addLayout(btn_layout)
        layout.addLayout(content_layout)

        # Нижняя кнопка закрытия
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.accept)
        layout.addWidget(btn_box)

    def _refresh_list(self):
        current_sel = self._get_selected_group()
        self._list_widget.clear()

        counts_map = {}
        if self._repository:
            counts_map = dict(self._repository.get_groups_with_counts())

        # Множество всех групп: группы из конфига и из БД
        all_groups = set(self._config.custom_groups)
        all_groups.update(counts_map.keys())
        all_groups.discard("Без группы")
        sorted_groups = ["Без группы"] + sorted(all_groups, key=lambda s: s.lower())

        for grp in sorted_groups:
            cnt = counts_map.get(grp, 0)
            item = QListWidgetItem(f"{grp} ({cnt})")
            item.setData(Qt.UserRole, grp)
            self._list_widget.addItem(item)
            if current_sel and grp == current_sel:
                self._list_widget.setCurrentItem(item)

        self._on_selection_changed()

    def _get_selected_group(self) -> Optional[str]:
        item = self._list_widget.currentItem()
        if not item:
            return None
        data = item.data(Qt.UserRole)
        if data:
            return data
        txt = item.text()
        return txt.rsplit(" (", 1)[0] if " (" in txt else txt

    def _select_group(self, group_name: str):
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            grp = item.data(Qt.UserRole) or (item.text().rsplit(" (", 1)[0] if " (" in item.text() else item.text())
            if grp == group_name:
                self._list_widget.setCurrentItem(item)
                break

    def _on_selection_changed(self):
        selected = self._get_selected_group()
        can_modify = bool(selected and selected != "Без группы")
        self._btn_edit.setEnabled(can_modify)
        self._btn_delete.setEnabled(can_modify)

    def _on_add_group(self):
        name, ok = QInputDialog.getText(self, "Добавить группу", "Название новой группы:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if name in self._config.custom_groups or name == "Без группы":
            QMessageBox.warning(self, "Внимание", f"Группа '{name}' уже существует.")
            return

        self._config.custom_groups.append(name)
        if self._storage:
            self._storage.save_config(self._config)
        self._refresh_list()
        self._select_group(name)

    def _on_edit_group(self):
        selected = self._get_selected_group()
        if not selected:
            return
        if selected == "Без группы":
            QMessageBox.warning(self, "Внимание", "Нельзя переименовать системную группу 'Без группы'.")
            return

        new_name, ok = QInputDialog.getText(self, "Переименовать группу", "Новое название группы:", text=selected)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == selected:
            return
        if new_name in self._config.custom_groups or new_name == "Без группы":
            QMessageBox.warning(self, "Внимание", f"Группа '{new_name}' уже существует.")
            return

        # Обновляем узлы в БД
        if self._repository:
            self._repository.rename_group(selected, new_name)

        # Обновляем в конфиге
        if selected in self._config.custom_groups:
            idx = self._config.custom_groups.index(selected)
            self._config.custom_groups[idx] = new_name
        else:
            self._config.custom_groups.append(new_name)

        if self._storage:
            self._storage.save_config(self._config)

        self._refresh_list()
        self._select_group(new_name)

    def _on_delete_group(self):
        selected = self._get_selected_group()
        if not selected:
            return
        if selected == "Без группы":
            QMessageBox.warning(self, "Внимание", "Нельзя удалить системную группу 'Без группы'.")
            return

        count = 0
        if self._repository:
            counts = dict(self._repository.get_groups_with_counts())
            count = counts.get(selected, 0)

        msg = (
            f"Вы уверены, что хотите удалить группу '{selected}'?\n"
            f"Все узлы ({count}) будут перемещены в группу 'Без группы'."
            if count > 0 else
            f"Удалить группу '{selected}'?"
        )
        reply = QMessageBox.question(
            self,
            "Удаление группы",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Удаляем узлы из группы в БД и переносим в 'Без группы'
        if self._repository:
            self._repository.delete_group(selected, fallback_group="Без группы")

        # Удаляем из конфига
        if selected in self._config.custom_groups:
            self._config.custom_groups.remove(selected)

        if self._storage:
            self._storage.save_config(self._config)

        self._refresh_list()