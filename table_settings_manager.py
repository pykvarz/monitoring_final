#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TableSettingsManager - Управление настройками таблицы
Инкапсулирует логику работы с настройками колонок (ширина, порядок, скрытие)
"""

import logging
from PyQt5.QtWidgets import QTableView, QSplitter
from PyQt5.QtCore import Qt, QObject, pyqtSlot

from models import AppConfig
from interfaces import IStorageRepository


class TableSettingsManager(QObject):
    """
    Менеджер настроек таблицы.
    
    Отвечает за:
    - Восстановление настроек колонок при запуске
    - Сохранение изменений ширины, порядка и видимости колонок
    - Сохранение и восстановление размеров сплиттера (ширины журнала событий)
    - Обработку сигналов от QHeaderView и QSplitter
    """
    
    def __init__(self, table: QTableView, config: AppConfig, storage: IStorageRepository, splitter: QSplitter = None):
        super().__init__()
        self._table = table
        self._config = config
        self._storage = storage
        self._splitter = splitter
        
        # Подключение сигналов
        self._connect_signals()
        
        logging.debug("TableSettingsManager initialized")
    
    def _connect_signals(self) -> None:
        """Подключение сигналов от таблицы и сплиттера"""
        header = self._table.horizontalHeader()
        header.sectionResized.connect(self._on_column_resized)
        header.sectionMoved.connect(self._on_column_moved)
        if self._splitter:
            self._splitter.splitterMoved.connect(self._on_splitter_moved)

    @pyqtSlot(int, int)
    def _on_splitter_moved(self, pos: int, index: int) -> None:
        """Сохранение положения сплиттера при изменении ширины панели"""
        if self._splitter:
            self._config.splitter_sizes = self._splitter.sizes()
            self._storage.save_config(self._config)
    
    def restore_settings(self) -> None:
        """Восстановление настроек таблицы из конфигурации"""
        header = self._table.horizontalHeader()
        
        # 1. Восстановление ширины колонок
        if self._config.column_widths:
            for col_idx_str, width in self._config.column_widths.items():
                try:
                    col_idx = int(col_idx_str)
                    if 0 <= col_idx < header.count():
                        self._table.setColumnWidth(col_idx, width)
                except (ValueError, TypeError):
                    logging.warning(f"Invalid column width config: {col_idx_str}={width}")
        
        # 2. Восстановление порядка колонок
        if getattr(self._config, 'column_order', None):
            if len(self._config.column_order) == header.count():
                try:
                    # Блокируем сигналы во время перестановки
                    header.blockSignals(True)
                    for visual_idx, logical_idx in enumerate(self._config.column_order):
                        if 0 <= logical_idx < header.count():
                            current_visual = header.visualIndex(logical_idx)
                            if current_visual != visual_idx:
                                header.moveSection(current_visual, visual_idx)
                finally:
                    header.blockSignals(False)
                    
                logging.debug(f"Restored column order: {self._config.column_order}")
        
        # 3. Восстановление скрытых колонок
        if self._config.hidden_columns:
            for col_idx in self._config.hidden_columns:
                if 0 <= col_idx < header.count():
                    self._table.setColumnHidden(col_idx, True)
                    
            logging.debug(f"Restored hidden columns: {self._config.hidden_columns}")

        # 4. Восстановление размеров сплиттера (ширины журнала событий)
        if self._splitter and getattr(self._config, 'splitter_sizes', None):
            if len(self._config.splitter_sizes) == self._splitter.count():
                try:
                    self._splitter.setSizes(self._config.splitter_sizes)
                    logging.debug(f"Restored splitter sizes: {self._config.splitter_sizes}")
                except Exception as e:
                    logging.warning(f"Failed to restore splitter sizes: {e}")
    
    @pyqtSlot(int, int, int)
    def _on_column_resized(self, index: int, old_size: int, new_size: int) -> None:
        """Обработка изменения ширины колонки"""
        if not self._config.column_widths:
            self._config.column_widths = {}
        
        self._config.column_widths[str(index)] = new_size
        self._storage.save_config(self._config)
        
        logging.debug(f"Column {index} resized: {old_size} -> {new_size}")
    
    @pyqtSlot(int, int, int)
    def _on_column_moved(self, logical_index: int, old_visual: int, new_visual: int) -> None:
        """Обработка перемещения колонки"""
        header = self._table.horizontalHeader()
        
        # Сохраняем текущий порядок колонок
        new_order = [header.logicalIndex(i) for i in range(header.count())]
        self._config.column_order = new_order
        self._storage.save_config(self._config)
        
        logging.debug(f"Column {logical_index} moved: {old_visual} -> {new_visual}")
        logging.debug(f"New column order: {new_order}")
    
    def update_hidden_columns(self) -> None:
        """
        Обновление списка скрытых колонок в конфигурации.
        Вызывается из контекстного меню после скрытия/показа колонок.
        """
        header = self._table.horizontalHeader()
        hidden = []
        
        for i in range(header.count()):
            if self._table.isColumnHidden(i):
                hidden.append(i)
        
        self._config.hidden_columns = hidden
        self._storage.save_config(self._config)
        
        logging.debug(f"Updated hidden columns: {hidden}")
