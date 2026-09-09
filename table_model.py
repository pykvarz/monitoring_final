#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель таблицы хостов (QAbstractTableModel)
"""

from typing import List, Any, Optional
from PyQt5.QtGui import QColor, QBrush, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex, QVariant, QTimer, QByteArray, QRect, QSize
from models import Host, HostStatus, format_offline_time
from datetime import datetime, timezone

class CenteredIconDelegate(QStyledItemDelegate):
    """Делегат для центрирования иконки в ячейке"""
    def paint(self, painter, option, index):
        # Инициализируем стиль
        self.initStyleOption(option, index)
        
        # Отрисовка стандартного фона (выделение, фокус и т.д.)
        style = option.widget.style() if option.widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)
        else:
            super().paint(painter, option, index)
            
        if index.column() == 0:
            # Получаем иконку
            icon = index.data(Qt.UserRole + 1)
            if isinstance(icon, QIcon) and not icon.isNull():
                size = 20
                rect = option.rect
                x = rect.x() + (rect.width() - size) // 2
                y = rect.y() + (rect.height() - size) // 2
                
                # Рисуем иконку
                icon.paint(painter, x, y, size, size)

class HostTableModel(QAbstractTableModel):
    """
    Высокопроизномительная модель таблицы данных
    """
    COLUMNS = ["Статус", "Название", "IP адрес", "Адрес", "Группа", "Время offline"]

    def __init__(self, parent=None, theme="light"):
        super().__init__(parent)
        self._hosts: List[Host] = []
        self._host_map = {}
        self._icon_cache = {}
        self._theme = theme
        self._sort_column: Optional[int] = None
        self._sort_order: Qt.SortOrder = Qt.AscendingOrder
        # id узла -> момент восстановления (UTC), для временной подсветки строки
        self._recently_recovered: dict = {}
        self._recovery_highlight_seconds = 60

    def set_theme(self, theme: str):
        """Обновление темы и сброс кэша иконок при необходимости"""
        if self._theme != theme:
            self._theme = theme
            self._icon_cache = {} # Сбрасываем кэш, так как иконки могут зависеть от темы
            self.layoutChanged.emit()

    def _get_icon(self, status: str) -> QIcon:
        """Получение иконки из кэша или создание новой"""
        if status in self._icon_cache:
            return self._icon_cache[status]
        
        svg_data = HostStatus[status].svg
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        icon = QIcon(pixmap)
        self._icon_cache[status] = icon
        return icon
    
    def set_hosts(self, hosts: List[Host]):
        """Установка нового списка хостов"""
        self.beginResetModel()
        self._hosts = list(hosts)
        if self._sort_column is not None:
            self._apply_sort()
        # Создаем мапу для быстрого поиска индекса по ID
        self._host_map = {h.id: i for i, h in enumerate(self._hosts)}
        self.endResetModel()

    def update_hosts(self, updated_hosts: List[Host]):
        """Точечное обновление узлов без перерисовки всей таблицы"""
        if not updated_hosts:
            return

        status_changed = False

        for host in updated_hosts:
            if host.status == "ONLINE":
                host.offline_since = None

            if host.id in self._host_map:
                idx = self._host_map[host.id]
                old_status = self._hosts[idx].status
                self._hosts[idx] = host

                # Если узел только что вернулся в ONLINE после реального падения —
                # запоминаем момент, чтобы временно подсветить строку в таблице
                if old_status == "OFFLINE" and host.status == "ONLINE":
                    self._recently_recovered[host.id] = datetime.now(timezone.utc)

                if old_status != host.status:
                    status_changed = True

        # Если активна сортировка по колонке статуса (0) и хотя бы один
        # узел сменил статус — переупорядочиваем строки, чтобы offline-узлы
        # сразу перемещались на своё место в таблице.
        if status_changed and self._sort_column is not None:
            self.layoutAboutToBeChanged.emit()
            self._apply_sort()
            self._host_map = {h.id: i for i, h in enumerate(self._hosts)}
            self.layoutChanged.emit()
        else:
            # Статус не менялся — достаточно перерисовать изменённые ячейки
            for host in updated_hosts:
                if host.id in self._host_map:
                    idx = self._host_map[host.id]
                    start_index = self.index(idx, 0)
                    end_index = self.index(idx, self.columnCount() - 1)
                    self.dataChanged.emit(start_index, end_index)


    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._hosts)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return QVariant()

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._hosts)):
            return QVariant()

        host = self._hosts[index.row()]
        col = index.column()

        # DecorationRole (Иконка) - НЕ ВОЗВРАЩАЕМ стандартно, чтобы не рисовалась слева
        if role == Qt.DecorationRole:
            return QVariant()

        # Кастомная роль для нашего делегата
        if role == Qt.UserRole + 1:
            if col == 0:
                return self._get_icon(host.status)
            return QVariant()

        if role == Qt.DisplayRole:
            if col == 0:
                return ""
            elif col == 1:
                return host.name
            elif col == 2:
                return host.ip
            elif col == 3:
                return host.address
            elif col == 4:
                return host.group
            elif col == 5:
                if host.status in ("OFFLINE", "WAITING") and host.offline_since:
                    try:
                        utc_now = datetime.now(timezone.utc)
                        offline_since = datetime.fromisoformat(host.offline_since)
                        if offline_since.tzinfo is None:
                            offline_since = offline_since.replace(tzinfo=timezone.utc)
                        duration = utc_now - offline_since
                        return format_offline_time(duration)
                    except ValueError:
                        pass
                return ""

        elif role == Qt.BackgroundRole:
            # Узел, недавно вернувшийся в онлайн, подсвечиваем мягким зелёным
            recovered_at = self._recently_recovered.get(host.id)
            if recovered_at and host.status == "ONLINE":
                age = (datetime.now(timezone.utc) - recovered_at).total_seconds()
                if age < self._recovery_highlight_seconds:
                    color = QColor("#0d3829")
                    return QBrush(color)
                else:
                    del self._recently_recovered[host.id]

            if host.status == "OFFLINE":
                return QBrush(QColor("#24161a"))  # Деликатный винный оттенок для читаемости
            elif host.status == "WAITING":
                return QBrush(QColor("#241d14"))  # Деликатный янтарный
            elif host.status == "MAINTENANCE":
                return QBrush(QColor("#1e1728"))  # Деликатный фиолетовый
            return QVariant()  # Для ONLINE стандартный фон чередования строк

        elif role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.ForegroundRole:
            return QBrush(QColor("#f1f5f9"))

        elif role == Qt.ToolTipRole:
            if col == 0:
                return HostStatus[host.status].title
            elif col == 1:
                return "Уведомления включены" if host.notifications_enabled else "Уведомления отключены"

        return QVariant()

    def get_host(self, row: int) -> Optional[Host]:
        """Получение хоста по индексу строки"""
        if 0 <= row < len(self._hosts):
            return self._hosts[row]
        return None
    
    def sort(self, column: int, order: Qt.SortOrder):
        """Сортировка данных в таблице (вызывается кликом по заголовку)"""
        self.layoutAboutToBeChanged.emit()

        self._sort_column = column
        self._sort_order = order
        self._apply_sort()

        # Пересчитываем карту id->строка: без этого точечные обновления
        # статусов (update_hosts) попадали бы в неверные строки после сортировки
        self._host_map = {h.id: i for i, h in enumerate(self._hosts)}

        self.layoutChanged.emit()

    def _apply_sort(self):
        """Применяет текущий (запомненный) столбец/порядок сортировки к self._hosts"""
        column = self._sort_column

        def get_sort_key(host: Host):
            if column == 0:
                order_priority = {"ONLINE": 0, "WAITING": 1, "OFFLINE": 2, "MAINTENANCE": 3}
                return order_priority.get(host.status, 9)
            elif column == 1: return host.name.lower()
            elif column == 2:
                try:
                    return [int(part) for part in host.ip.split('.')]
                except Exception:
                    return host.ip
            elif column == 3: return host.address.lower()
            elif column == 4: return host.group.lower()
            elif column == 5:
                if host.offline_since:
                    return host.offline_since
                return ""
            return ""

        reverse = (self._sort_order == Qt.DescendingOrder)
        self._hosts.sort(key=get_sort_key, reverse=reverse)

    def refresh_live_columns(self):
        """
        Периодическое обновление 'живых' данных, вычисляемых на лету:
        - время простоя в колонке 'Время offline'
        - угасание подсветки недавно восстановленных узлов
        Не трогает _host_map, порядок строк не меняется.
        """
        if not self._hosts:
            return
        top_left = self.index(0, 5)
        bottom_right = self.index(len(self._hosts) - 1, 5)
        self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])

        if self._recently_recovered:
            now = datetime.now(timezone.utc)
            expired = [
                host_id for host_id, ts in self._recently_recovered.items()
                if (now - ts).total_seconds() >= self._recovery_highlight_seconds
            ]
            for host_id in expired:
                del self._recently_recovered[host_id]

            for host_id in self._recently_recovered:
                row = self._host_map.get(host_id)
                if row is not None:
                    start_index = self.index(row, 0)
                    end_index = self.index(row, self.columnCount() - 1)
                    self.dataChanged.emit(start_index, end_index, [Qt.BackgroundRole])
            # Отдельно перерисовываем только что истёкшие строки, чтобы снять подсветку
            for host_id in expired:
                row = self._host_map.get(host_id)
                if row is not None:
                    start_index = self.index(row, 0)
                    end_index = self.index(row, self.columnCount() - 1)
                    self.dataChanged.emit(start_index, end_index, [Qt.BackgroundRole])
    
    def update_host_status(self, host_id: str, status: str, offline_since: str, offline_time: str) -> bool:
        """Обновление статуса хоста в модели"""
        for row, host in enumerate(self._hosts):
            if host.id == host_id:
                host.status = status
                host.offline_since = offline_since if status != "ONLINE" else None
                
                start_index = self.index(row, 0)
                end_index = self.index(row, self.columnCount() - 1)
                self.dataChanged.emit(start_index, end_index)
                return True
        return False
    
    def get_selected_rows(self) -> List[int]:
        """Получить список выбранных строк"""
        if not hasattr(self, '_parent_table') or not self._parent_table:
            return []
        
        selection_model = self._parent_table.selectionModel()
        if not selection_model:
            return []
        
        selected_indexes = selection_model.selectedRows()
        return [index.row() for index in selected_indexes]
    
    def set_parent_table(self, table) -> None:
        """Установить родительскую таблицу для получения выделения"""
        self._parent_table = table