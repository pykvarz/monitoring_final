#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Network Monitor - Система мониторинга доступности сетевых узлов
Требования: pip install PyQt5 ping3 plyer openpyxl
Запуск от администратора (для ICMP ping)
"""

import sys
import logging
import traceback

# Настройка логирования для отладки вылетов
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug.log', mode='w', encoding='utf-8')
    ]
)

def exception_hook(exctype, value, tb):
    """Глобальный обработчик исключений"""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    logging.error(f"Необработанное исключение:\n{error_msg}")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

from PyQt5.QtWidgets import QApplication, QMessageBox
from services import PingService
from main_window import MainWindow
from di_container import setup_container

def main():
    """Главная функция"""
    logging.info("Запуск приложения...")
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setApplicationName("Network Monitor")
        logging.debug("QApplication создан")

        # Проверка прав на ICMP
        try:
            PingService.ping_host("127.0.0.1", timeout=1)
            logging.debug("Ping тест пройден")
        except Exception as e:
            logging.warning(f"Ping тест не пройден: {e}")
            QMessageBox.warning(
                None, "Предупреждение",
                f"Для работы ping могут потребоваться права администратора: {e}"
            )

        # Инициализация DI контейнера
        logging.debug("Настройка DI контейнера...")
        container = setup_container()
        logging.debug("DI контейнер настроен")

        # Создание главного окна с DI
        logging.debug("Создание MainWindow...")
        window = MainWindow(container)
        logging.debug("MainWindow создан")
        window.show()
        logging.debug("MainWindow отображен")
        
        exit_code = app.exec_()
        logging.info(f"Приложение завершено с кодом: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logging.error(f"Критическая ошибка при запуске:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == '__main__':
    main()