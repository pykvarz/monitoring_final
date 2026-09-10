#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Host Manager
Управление операциями с хостами (CRUD)
"""

from PyQt5.QtWidgets import QMessageBox, QInputDialog, QDialog
from typing import List

from models import Host
from dialogs import HostDialog
from core.host_repository import HostRepository

class HostManager:
    """Менеджер операций с хостами (via HostRepository)"""
    
    @staticmethod
    def add_host(parent, groups: List[str], repository: HostRepository) -> bool:
        """Добавление нового узла"""
        dialog = HostDialog(parent, groups=groups)
        if dialog.exec_() == QDialog.Accepted:
            new_host = dialog.get_host()
            
            if not new_host.validate():
                QMessageBox.warning(parent, "Ошибка", "Некорректные данные узла")
                return False
            
            if repository.exists_by_ip(new_host.ip):
                QMessageBox.warning(parent, "Ошибка", f"Узел с адресом/IP '{new_host.ip}' уже существует")
                return False

            if repository.add(new_host):
                return True
            else:
                QMessageBox.warning(parent, "Ошибка", "Не удалось добавить узел (возможно дубликат ID)")
        
        return False
    
    @staticmethod
    def delete_selected(parent, table_model, repository: HostRepository) -> None:
        """Удаление выбранных узлов"""
        selected_indexes = parent._table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(parent, "Информация", "Выберите узлы для удаления")
            return
        
        reply = QMessageBox.question(
            parent, "Подтверждение",
            f"Удалить выбранные узлы ({len(selected_indexes)} шт.)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            ids_to_delete = []
            for index in selected_indexes:
                host = table_model.get_host(index.row())
                if host:
                    ids_to_delete.append(host.id)
            
            for hid in ids_to_delete:
                repository.delete(hid)

    @staticmethod
    def delete_host(parent, row: int, table_model, repository: HostRepository) -> None:
        """Удаление одного узла"""
        host = table_model.get_host(row)
        if not host:
            return

        reply = QMessageBox.question(
            parent, "Подтверждение",
            f"Удалить узел {host.name}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            repository.delete(host.id)
    
    @staticmethod
    def edit_host(parent, row: int, table_model, groups: List[str], repository: HostRepository) -> None:
        """Редактирование узла"""
        host = table_model.get_host(row)
        if not host:
            return
        
        dialog = HostDialog(parent, host=host, groups=groups)
        if dialog.exec_() == QDialog.Accepted:
            edited_host = dialog.get_host()
            # ID не меняется
            edited_host.id = host.id 
            
            if not edited_host.validate():
                QMessageBox.warning(parent, "Ошибка", "Некорректные данные узла")
                return

            if repository.exists_by_ip(edited_host.ip, exclude_id=host.id):
                QMessageBox.warning(parent, "Ошибка", f"Узел с адресом/IP '{edited_host.ip}' уже существует")
                return

            if not repository.update(edited_host):
                QMessageBox.warning(parent, "Ошибка", "Не удалось сохранить изменения")

    @staticmethod
    def toggle_maintenance_selected(parent, table_model, repository: HostRepository) -> None:
        """Переключение статуса тех.обслуживания для выбранных узлов"""
        selected_indexes = parent._table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(parent, "Информация", "Выберите узлы")
            return
        
        ids = []
        for index in selected_indexes:
            host = table_model.get_host(index.row())
            if host:
                ids.append(host.id)
        
        hosts = repository.get_hosts_by_ids(ids)
        for host in hosts:
            new_status = "ONLINE" if host.status == "MAINTENANCE" else "MAINTENANCE"
            # offline_since сбрасываем если уходим в MAINTENANCE или выходим в ONLINE
            repository.update_status(host.id, new_status, None)

    @staticmethod
    def toggle_maintenance(parent, row: int, table_model, repository: HostRepository) -> None:
        """Переключение статуса тех.обслуживания"""
        host = table_model.get_host(row)
        if not host:
            return
            
        new_status = "ONLINE" if host.status == "MAINTENANCE" else "MAINTENANCE"
        repository.update_status(host.id, new_status, None)

    @staticmethod
    def change_group_selected(parent, table_model, groups: List[str], repository: HostRepository) -> None:
        """Изменение группы для выбранных узлов"""
        selected_indexes = parent._table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(parent, "Информация", "Выберите узлы")
            return
        
        dialog = QInputDialog(parent)
        dialog.setWindowTitle("Изменение группы")
        dialog.setLabelText("Выберите новую группу:")
        dialog.setComboBoxItems(groups + ["Новая группа..."])
        dialog.setOption(QInputDialog.UseListViewForComboBoxItems, False)
        theme = getattr(parent._config, "theme", "dark") if hasattr(parent, "_config") else "dark"
        from constants import get_main_style
        dialog.setStyleSheet(get_main_style(theme))
        from theme_manager import set_dark_titlebar
        set_dark_titlebar(dialog, theme in ("dark", "tactical"))
        ok = dialog.exec_() == QDialog.Accepted
        new_group = dialog.textValue()
        
        if not ok:
            return
        
        if new_group == "Новая группа...":
            dialog2 = QInputDialog(parent)
            dialog2.setWindowTitle("Новая группа")
            dialog2.setLabelText("Введите название новой группы:")
            dialog2.setStyleSheet(get_main_style(theme))
            set_dark_titlebar(dialog2, theme in ("dark", "tactical"))
            ok2 = dialog2.exec_() == QDialog.Accepted
            new_group = dialog2.textValue()
            if not ok2 or not new_group.strip():
                return
            new_group = new_group.strip()
            
        ids = []
        for index in selected_indexes:
            host = table_model.get_host(index.row())
            if host:
                ids.append(host.id)
                
        hosts = repository.get_hosts_by_ids(ids)
        for host in hosts:
            host.group = new_group
            repository.update(host)

    @staticmethod
    def toggle_notifications_selected(parent, table_model, repository: HostRepository) -> None:
        """Переключение уведомлений для выбранных узлов"""
        selected_indexes = parent._table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(parent, "Информация", "Выберите узлы")
            return
            
        ids = []
        for index in selected_indexes:
            host = table_model.get_host(index.row())
            if host:
                ids.append(host.id)
                
        hosts = repository.get_hosts_by_ids(ids)
        for host in hosts:
            host.notifications_enabled = not host.notifications_enabled
            repository.update(host)

    @staticmethod
    def toggle_notifications(parent, row: int, table_model, repository: HostRepository) -> None:
        """Переключение уведомлений для узла"""
        host = table_model.get_host(row)
        if not host:
            return
            
        # Получаем свежие данные или используем из модели (лучше свежие для тогла)
        hosts = repository.get_hosts_by_ids([host.id])
        if hosts:
            h = hosts[0]
            h.notifications_enabled = not h.notifications_enabled
            repository.update(h)


