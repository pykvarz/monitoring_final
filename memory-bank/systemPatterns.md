# System Patterns — Network Monitor

## Архитектурные паттерны

### 1. Dependency Injection (DIContainer)
- Самописный DI-контейнер в `di_container.py`.
- Поддерживает: Singleton, Transient, Factory.
- Настройка в `setup_container()`: регистрирует DatabaseManager, DataManager, HostRepository, StorageManager, PingService, NotificationService.
- Главное окно получает контейнер и резолвит зависимости через `container.resolve(SomeInterface)`.

### 2. Repository Pattern
- `HostRepository` (`core/host_repository.py`) — единая точка доступа к данным хостов.
- Оборачивает `DataManager`. Используется `MonitorThread`.

### 3. Thread Safety (QThread + сигналы Qt)
- `MonitorThread` работает в отдельном потоке.
- Прямая запись в БД из потока запрещена — используется именованное SQLite-соединение (`monitor_thread_{id}`).
- Изменения статуса передаются через сигнал `host_status_changed(id, status, offline_since)` в главный поток.
- DataManager обновляет UI через батч-сигнал `hosts_updated` с throttle 250 мс (QTimer).

### 4. Domain Logic: статус-машина в MonitorThread
- `_calculate_status()` — чистая функция, не обращается к БД.
- Статусы: `ONLINE → (no ping) → WAITING → (timeout) → OFFLINE`.
- Throttling heartbeat: запись last_seen только раз в 60 сек (избегаем лишних I/O).
- Кеш статусов `_known_statuses` для определения "стал ли offline новым".

### 5. Интерфейсы / Абстракции
- `IStorageRepository`, `IPingService`, `INotificationService` в `interfaces.py`.
- Позволяют подменять реализации в тестах (mock).

### 6. Журнал истории
- Таблица `status_history` в SQLite.
- Запись при каждой смене статуса (через `_add_history_event`).
- Фильтрация по хосту, группе, статусу, дате.
- Очистка по сроку хранения (`purge_old_history`).

### 7. Subscribers (Event Bus)
- `subscribers/monitor_subscriber.py` — подписчик на события DataManager.
- Реагирует на `host_added`, `host_deleted`, `host_info_updated` — управляет MonitorThread (прерывание цикла, удаление из кеша).

## Известные технические решения

### Двойное хранилище (legacy)
- `StorageManager` (JSON) — исторически первый вариант, ныне используется только для хранения `config.json` и миграции.
- Основное хранилище — SQLite через `DataManager`.

### PyInstaller + PyQt5
- Сборка настроена через `NetworkMonitor.spec`.
- Сборочный скрипт: `build_exe.py`.

### Именованные SQLite-соединения
- PyQt5.QtSql требует отдельного соединения на поток.
- MonitorThread открывает своё: `QSqlDatabase.addDatabase("QSQLITE", connection_name)`.
