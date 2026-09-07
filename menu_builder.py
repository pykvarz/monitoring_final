#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MenuBuilder - Построение главного меню приложения
Инкапсулирует логику создания меню для MainWindow
"""

from PyQt5.QtWidgets import QMenuBar, QMenu, QAction
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QByteArray

from constants import (
    get_svg_add_host, get_svg_add_group, get_svg_import, get_svg_export,
    get_svg_scan, get_svg_settings, get_svg_theme, get_svg_delete
)


class MenuBuilder:
    """
    Построитель главного меню приложения.
    
    Создает структуру меню и подключает действия к методам главного окна.
    """
    
    @staticmethod
    def _get_qicon(svg_data: str, size: int = 16) -> QIcon:
        """Создание QIcon из SVG строки"""
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    
    @staticmethod
    def create_menu_bar(parent, theme: str = "light") -> QMenuBar:
        """
        Создание главного меню приложения.
        
        Args:
            parent: MainWindow instance с методами-обработчиками
            theme: Текущая тема ('light' или 'dark')
            
        Returns:
            QMenuBar с полной структурой меню
        """
        menubar = parent.menuBar()
        
        # === Меню "Файл" ===
        file_menu = menubar.addMenu("📁 Файл")
        
        action_import = QAction(MenuBuilder._get_qicon(get_svg_import(theme)), "Импорт из Excel", parent)
        action_import.setShortcut("Ctrl+I")
        action_import.triggered.connect(parent._import_from_excel)
        
        action_export = QAction(MenuBuilder._get_qicon(get_svg_export(theme)), "Экспорт в Excel", parent)
        action_export.setShortcut("Ctrl+E")
        action_export.triggered.connect(parent._export_to_excel)
        
        action_exit = QAction("Выход", parent)
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(parent.close)
        
        file_menu.addAction(action_import)
        file_menu.addAction(action_export)
        file_menu.addSeparator()
        file_menu.addAction(action_exit)
        
        # === Меню "Действия" ===
        actions_menu = menubar.addMenu("⚡ Действия")
        
        action_add_host = QAction(MenuBuilder._get_qicon(get_svg_add_host(theme)), "Добавить узел", parent)
        action_add_host.setShortcut("Ctrl+N")
        action_add_host.triggered.connect(parent._add_host)
        
        action_add_group = QAction(MenuBuilder._get_qicon(get_svg_add_group(theme)), "Создать группу", parent)
        action_add_group.setShortcut("Ctrl+G")
        action_add_group.triggered.connect(parent._add_group)
        
        action_delete = QAction(MenuBuilder._get_qicon(get_svg_delete(theme)), "Удалить выбранное", parent)
        action_delete.setShortcut("Delete")
        action_delete.triggered.connect(parent._delete_selected)
        
        action_scan = QAction(MenuBuilder._get_qicon(get_svg_scan(theme)), "Проверить сейчас", parent)
        action_scan.setShortcut("F5")
        action_scan.triggered.connect(parent._force_scan)
        
        actions_menu.addAction(action_add_host)
        actions_menu.addAction(action_add_group)
        actions_menu.addSeparator()
        actions_menu.addAction(action_delete)
        actions_menu.addSeparator()
        actions_menu.addAction(action_scan)
        
        # === Меню "Вид" ===
        view_menu = menubar.addMenu("👁 Вид")
        
        action_history = QAction("📜 Журнал событий (падения/восстановления)", parent)
        action_history.setShortcut("Ctrl+H")
        action_history.triggered.connect(parent._open_history_journal)

        view_menu.addAction(action_history)

        action_theme = QAction(MenuBuilder._get_qicon(get_svg_theme(theme)), "Переключить тему", parent)
        action_theme.setShortcut("Ctrl+T")
        action_theme.triggered.connect(parent._toggle_theme)
        
        view_menu.addAction(action_theme)
        
        # === Меню "Настройки" ===
        settings_menu = menubar.addMenu("⚙ Настройки")
        
        action_settings = QAction(MenuBuilder._get_qicon(get_svg_settings(theme)), "Параметры приложения", parent)
        action_settings.setShortcut("Ctrl+,")
        action_settings.triggered.connect(parent._open_settings)
        
        settings_menu.addAction(action_settings)
        
        # === Меню "Справка" ===
        help_menu = menubar.addMenu("❓ Справка")
        
        action_about = QAction("О программе", parent)
        action_about.triggered.connect(lambda: parent._show_about_dialog())
        
        help_menu.addAction(action_about)
        
        return menubar
    
    @staticmethod
    def update_menu_icons(menubar: QMenuBar, theme: str) -> None:
        """
        Обновление иконок меню при смене темы.
        
        Args:
            menubar: Объект QMenuBar для обновления
            theme: Новая тема ('light' или 'dark')
        """
        # Получаем все действия из всех меню
        for action in menubar.actions():
            menu = action.menu()
            if menu:
                for menu_action in menu.actions():
                    text = menu_action.text()
                    
                    # Обновляем иконки на основе текста действия
                    if "Импорт" in text:
                        menu_action.setIcon(MenuBuilder._get_qicon(get_svg_import(theme)))
                    elif "Экспорт" in text:
                        menu_action.setIcon(MenuBuilder._get_qicon(get_svg_export(theme)))
                    elif "Добавить узел" in text:
                        menu_action.setIcon(MenuBuilder._get_qicon(get_svg_add_host(theme)))
                    elif "Создать группу" in text:
                        menu_action.setIcon(MenuBuilder._get_qicon(get_svg_add_group(theme)))
                    elif "Удалить" in text:
                        menu_action.setIcon(MenuBuilder._get_qicon(get_svg_delete(theme)))
                    elif "Проверить" in text:
                        menu_action.setIcon(MenuBuilder._get_qicon(get_svg_scan(theme)))
                    elif "тему" in text:
                        menu_action.setIcon(MenuBuilder._get_qicon(get_svg_theme(theme)))
                    elif "Настройки" in text or "Параметры" in text:
                        menu_action.setIcon(MenuBuilder._get_qicon(get_svg_settings(theme)))
