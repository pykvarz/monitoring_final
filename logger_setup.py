#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенное логирование для Network Monitor
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logging():
    """Настройка логирования"""
    # Создание директории для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Настройка формата логирования
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Настройка обработчиков логов
    handlers = [
        logging.FileHandler(log_dir / "network_monitor.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
    
    # Настройка уровня логирования
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers,
        force=True
    )
    
    # Создание логгера
    logger = logging.getLogger('NetworkMonitor')
    logger.info("Логирование настроено")

def get_logger():
    """Получение логгера"""
    return logging.getLogger('NetworkMonitor')

if __name__ == '__main__':
    setup_logging()
