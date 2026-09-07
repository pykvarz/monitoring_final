#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExportImportManager - Управление импортом/экспортом данных в Excel
"""

from typing import List, Set, Tuple, Optional
from datetime import datetime
import logging
from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox
from models import Host
from core.host_repository import HostRepository
from excel_service import ExcelService


class ExportImportManager:
    """Менеджер импорта и экспорта данных"""

    def __init__(self, parent: QWidget, repository: HostRepository):
        """
        Инициализация менеджера импорта/экспорта
        
        Args:
            parent: Родительский виджет для диалогов
            repository: Репозиторий хостов
        """
        self._parent = parent
        self._repository = repository

    def import_from_excel(self) -> bool:
        """
        Импорт узлов из Excel файла.
        Использует HostRepository для проверки дубликатов и пакетной вставки.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self._parent, 
            "Выберите Excel файл для импорта", 
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if not file_path:
            return False

        try:
            # 1. Получаем существующие IP для проверки дубликатов (Single Source of Truth)
            all_hosts = self._repository.get_all()
            existing_ips = {h.ip for h in all_hosts}
            
            # 2. Парсим файл
            new_hosts, skipped_count, errors = ExcelService.import_hosts(file_path, existing_ips)
            
            # 3. Сохраняем в БД (Batch Transaction)
            added_count = 0
            db_errors = 0
            
            if new_hosts:
                try:
                    added_count, db_errors = self._repository.add_hosts(new_hosts)
                except Exception as e:
                    logging.error(f"Failed to batch add hosts: {e}")
                    QMessageBox.critical(self._parent, "Ошибка БД", f"Ошибка при сохранении данных:\n{e}")
                    return False

            # 4. Отчет
            message = f"✅ Импортировано: {added_count}\n"
            
            if skipped_count > 0:
                message += f"⚠️ Пропущено (дубликаты IP): {skipped_count}\n"
            
            if db_errors > 0:
                 message += f"❌ Ошибок записи в БД: {db_errors}\n"

            if errors:
                message += "\nОшибки валидации:\n" + "\n".join(errors[:10])
                if len(errors) > 10:
                    message += f"\n... и ещё {len(errors) - 10} ошибок"

            QMessageBox.information(self._parent, "Импорт завершён", message)
            return True

        except Exception as e:
            logging.error(f"Ошибка импорта из {file_path}: {e}", exc_info=True)
            QMessageBox.critical(
                self._parent, 
                "Ошибка импорта", 
                f"Не удалось импортировать файл:\n{str(e)}"
            )
            return False

    def export_to_excel(self, hosts: Optional[List[Host]] = None) -> bool:
        """
        Экспорт узлов в Excel файл
        
        Args:
            hosts: Список хостов для экспорта. Если None, берется из репозитория.
        """
        hosts_to_export = hosts if hosts is not None else self._repository.get_all()

        if not hosts_to_export:
            QMessageBox.information(self._parent, "Информация", "Нет узлов для экспорта")
            return False

        # Формируем имя файла с временной меткой
        default_filename = f"network_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self._parent, 
            "Сохранить как Excel файл",
            default_filename,
            "Excel Files (*.xlsx);;All Files (*)"
        )

        if not file_path:
            return False

        try:
            ExcelService.export_hosts(file_path, hosts_to_export)
            QMessageBox.information(
                self._parent, 
                "Экспорт завершён",
                f"✅ Экспортировано узлов: {len(hosts_to_export)}\n\nФайл сохранён: {file_path}"
            )
            return True
        except Exception as e:
            logging.error(f"Ошибка экспорта в {file_path}: {e}", exc_info=True)
            QMessageBox.critical(
                self._parent, 
                "Ошибка экспорта", 
                f"Не удалось экспортировать файл:\n{str(e)}"
            )
            return False
