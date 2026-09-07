# Tech Context — Network Monitor

## Стек технологий

| Слой | Технология | Версия/примечание |
|------|-----------|-------------------|
| Язык | Python | 3.8+ |
| UI Framework | PyQt5 | QWidget, QThread, QSqlDatabase |
| БД | SQLite | через PyQt5.QtSql (WAL-mode) |
| Ping | ping3 | ICMP |
| Уведомления | plyer | системные push |
| Excel | openpyxl | импорт/экспорт |
| Helpdesk | playwright | 1.62.0, автоматизация браузера |
| Сборка | PyInstaller | NetworkMonitor.spec |
| Тесты | pytest | |

## Архитектура (кратко)
- **DI Container** (`di_container.py`) — регистрация и резолв сервисов
- **DatabaseManager** (`database.py`) — SQLite соединение, WAL, создание таблиц
- **DataManager** (`data_manager.py`) — CRUD хостов, батч-обновления UI (250 мс throttle), журнал истории
- **HostRepository** (`core/host_repository.py`) — Repository pattern поверх DataManager
- **MonitorThread** (`monitor_thread.py`) — QThread, параллельный ping (ThreadPoolExecutor), сигналы Qt
- **StorageManager** (`storage.py`) — JSON-хранилище конфига, миграция в SQLite (legacy)
- **MainWindow** (`main_window.py`) — главное окно

## Команды

```bash
# Установка зависимостей
pip install -r requirements.txt

# Установка dev-зависимостей
pip install -r requirements-dev.txt

# Запуск приложения (требует прав администратора для ICMP)
python main.py

# Запуск тестов
pytest tests/

# Запуск с verbose
pytest tests/ -v

# Сборка .exe
python build_exe.py
```

## Файлы данных (runtime, не в git)
- `hosts.db` — SQLite БД с хостами и историей
- `config.json` — конфигурация приложения
- `debug.log` — лог запуска
