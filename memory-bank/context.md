# Memory Bank

## Project Brief
Десктопное Windows-приложение для мониторинга доступности сетевых узлов (хостов) в реальном времени.
Разрабатывается как **внутренний корпоративный инструмент** для системных администраторов и ИТ-специалистов.

### Ключевые сценарии
1. **Мониторинг**: периодический ICMP-пинг списка IP/хостов (IPv4 и IPv6, FQDN и однокомпонентные имена вроде `localhost`, `router`) с визуализацией статуса (Online / Waiting / Offline / Maintenance).
2. **Уведомления**: Desktop Toast-баннеры и системные уведомления Windows Tray при переходе узла в Offline.
3. **Управление хостами**: добавление, редактирование, удаление хостов и пользовательских групп с валидацией дубликатов IP/имен.
4. **Импорт/Экспорт**: массовый импорт и экспорт в Excel (с защитой от Formula Injection CWE-1236).
5. **История**: общий журнал смены статусов (Ctrl+H) и плавающее HUD-окно EventLogPanel («Поверх всех окон»).
6. **Helpdesk-интеграция**: автоматизированное открытие/закрытие инцидентов (playwright).
7. **Темы оформления**: Dark (по умолчанию), Light и Tactical (NOC Terminal с моноширинным шрифтом).

### Целевая платформа
Windows 10/11. Поставка в виде автономного `.exe` (PyInstaller).

---

## System Patterns

### 1. Dependency Injection (DIContainer)
- Самописный легковесный DI-контейнер в `di_container.py`.
- Поддерживает: Singleton, Transient, Factory.
- `setup_container()` регистрирует `DatabaseManager`, `DataManager`, `HostRepository`, `StorageManager`, `PingService`, `NotificationService`.
- Главное окно и сервисы получают зависимости через `container.resolve(Interface)`.

### 2. Repository Pattern
- `HostRepository` (`core/host_repository.py`) — единая точка доступа к данным хостов поверх `DataManager`.
- Используется `MonitorThread`, `ContextMenuManager` и `HostManager`.

### 3. Thread Safety (QThread + сигналы Qt)
- `MonitorThread` изолирован в фоновом потоке.
- Прямая запись в БД из фонового потока запрещена — используется выделенное именованное SQLite-соединение (`monitor_thread_{id}`).
- Изменения статуса передаются в UI через сигналы Qt (`host_status_changed(id, status, offline_since)`).
- DataManager выполняет батч-обновление UI с подавлением дребезга (250 мс debounce через QTimer).

### 4. Domain Logic: Статус-машина
- `_calculate_status()` в `MonitorThread` — чистая функция, не обращающаяся к I/O.
- Переходы: `ONLINE → (нет ответа) → WAITING → (timeout) → OFFLINE`.
- Heartbeat throttling: сохранение `last_seen` в БД выполняется не чаще 1 раза в 60 секунд.
- Расчет времени простоя учитывает реальный `offline_since` с защитой от ложных таймеров.

### 5. Интерфейсы и абстракции
- `IStorageRepository`, `IPingService`, `INotificationService` в `interfaces.py` для полной изоляции и подмены моками в unit-тестах.

### 6. Журнал истории
- Таблица `status_history` в SQLite с версионированными миграциями (`schema_version`).
- Запись событий изменения статуса и автоматическая очистка по сроку хранения (`purge_old_history`).

### 7. Event Bus / Subscribers
- `subscribers/monitor_subscriber.py` реагирует на события DataManager (`host_added`, `host_deleted`, `host_info_updated`) и синхронизирует состояние `MonitorThread`.

---

## Tech Context

### Стек технологий
| Слой | Технология | Версия / примечание |
|------|-----------|---------------------|
| Язык | Python | 3.8+ (протестировано на 3.14) |
| UI Framework | PyQt5 | QWidget, QThread, QSqlDatabase, QSvg |
| БД | SQLite | Режим WAL, внешние ключи, пул соединений |
| Пинг | ping3 / ping.exe | ICMP (raw sockets с фоллбэком на системный ping) |
| Уведомления | PyQt5 Desktop Toast + QSystemTrayIcon | Нативные окна без активации фокуса |
| Экспорт/Импорт | openpyxl | 3.1.5 |
| Helpdesk | playwright | 1.62.0 (опционально) |
| Сборка | PyInstaller | NetworkMonitor.spec / build_exe.py |
| Тесты | pytest | 195 тестов |

### Команды
- Установка зависимостей: `pip install -r requirements.txt`
- Установка dev-зависимостей: `pip install -r requirements-dev.txt`
- Запуск приложения: `python main.py`
- Тесты: `pytest`
- Запуск тестов с подробным выводом: `pytest -v`
- Сборка дистрибутива .exe: `python build_exe.py`

### Файлы данных (runtime, исключены из git)
- `hosts.db` — рабочая база данных SQLite
- `config.json` — конфигурация приложения (`AppConfig`)
- `debug.log` — оперативный журнал работы

---

## Progress

### Статус: Активная разработка / Стабильный релиз

### Что реализовано
- [x] Высокопроизводительный параллельный мониторинг узлов (`ThreadPoolExecutor`) с фоллбэком на системный ping
- [x] Статус-машина (Online / Waiting / Offline / Maintenance) и учёт времени простоя
- [x] Хранилище SQLite WAL с автоматическими миграциями `schema_version`
- [x] Защита от потери данных и безопасная миграция `StorageManager` (JSON → SQLite)
- [x] Поддержка тем оформления: Dark, Light, Tactical (NOC Terminal)
- [x] Адаптивная таблица хостов без пустых полей справа и с сохранением порядка/ширины колонок
- [x] Плавающее HUD-окно журнала событий (`FloatingEventLogWindow`) с режимом «Поверх всех окон»
- [x] Десктопные всплывающие Toast-уведомления с анимацией и тенью
- [x] Контекстные меню для узлов и пакетных операций с контурными иконками Lucide
- [x] Импорт/экспорт Excel с защитой от Formula Injection (CWE-1236)
- [x] Поддержка адресов IPv6 и однокомпонентных сетевых имен (`localhost`, `router`, `nas`)
- [x] Полный набор тестов (pytest, 195 тестов: 195 passed)
- [x] Сборка .exe (PyInstaller + build_exe.py)

### Последние обновления
- **2026-09-14 — актуализация документации:**
  - Полностью обновлены [README.md](file:///c:/Users/User/Desktop/Шаблон%20—%20копия/README.md) и [SECURITY.md](file:///c:/Users/User/Desktop/Шаблон%20—%20копия/SECURITY.md) под актуальную архитектуру, токены тем, HUD, Toast-уведомления и защитные механизмы (CWE-1236, защита от Command Injection, изоляция БД).
- **2026-09-14 — устранение дефектов Medium и Low (MED-1..3, LOW-1..2):**
  - MED-1: В `models.py` добавлена поддержка IPv6 через `ipaddress.ip_address` и валидация однокомпонентных сетевых имен (`localhost`, `router`, `dc01`).
  - MED-2: В `theme_manager.py` удален мертвый код (`_update_toolbar_buttons`, `_update_filter_buttons`) с необъявленной функцией `get_svg_theme`.
  - MED-3: Из `requirements.txt` удалена неиспользуемая зависимость `plyer==2.1.0`.
  - LOW-1: В `filter_manager.py` удалены устаревшие рудименты `.replace("📁 ", "")`.
  - LOW-2: В `services.py` исправлен расчет таймаута для Linux системного ping (`-W` в секундах, а не миллисекундах).
  - Тестовый набор расширен до 195 тестов (195 passed).
- **2026-09-14 — устранение дефектов High (HIGH-1..3):**
  - HIGH-1: Сохранение настроек HUD и сплиттера в `SettingsDialog.get_config` (`dialogs.py`).
  - HIGH-2: Устранение `NameError: SVG_MAINTENANCE` в `ContextMenuManager.show_bulk_menu` (`context_menu_manager.py`).
  - HIGH-3: Сохранение поля `address` и дескриптора БД в `StorageManager.migrate_to_db` (`storage.py`).
- **2026-09-14 — устранение критических дефектов (CRIT-1..3):**
  - CRIT-1: Защита сортировки таблицы от `AttributeError` при `NULL` в SQLite (`table_model.py`).
  - CRIT-2: Защита от `KeyError: 'UNKNOWN'` при экспорте в Excel и подсказках (`excel_service.py`, `table_model.py`).
  - CRIT-3: Корректный жизненный цикл закрытия плавающего HUD окна (`main_window.py`).

---

## Design System

### 1. Токены
#### Статусы узлов (Semantic Status Colors)
- **ONLINE**: `#10b981` (Изумрудно-зеленый) — узел доступен.
- **WAITING**: `#f59e0b` (Теплый янтарный) — временный сбой, ожидание подтверждения.
- **OFFLINE**: `#ef4444` (Рубиново-красный) — узел недоступен, авария.
- **MAINTENANCE**: `#8b5cf6` (Фиолетовый) — регламентные работы / тех. обслуживание.
- **TOTAL**: `#3b82f6` (Синий) — общее количество узлов.

#### Темы оформления
- **Dark Theme (по умолчанию)**: фон `#151820`, поверхность карточек `#181c26`, границы `#282e3d`, текст `#f1f5f9` / `#94a3b8`, зебра таблицы `#1e222e`.
- **Tactical Theme (NOC Terminal)**: фон `#090A0F`, карточки `#0D1117`, границы `#1F232D`, моноширинный шрифт `Consolas`, неоновые акценты (`#39FF14`, `#00F0FF`).

### 2. Компоненты UI
- **Иконки**: строго плоские векторные контурные SVG-иконки Lucide (`stroke-width="2"`). Системные цветные эмодзи в интерфейсе запрещены.
- **Карточки метрик (Dashboard Cards)**: полупрозрачная подложка, нейтральный бордер, радиус 8-10px, акцентная иконка и крупный показатель.
- **Таблица хостов**: адаптивное растяжение смысловых колонок, мягкая цветовая подсветка строк без тяжелой заливки.
- **HUD-панель (EventLogPanel)**: карточки с левым цветным акцентом статуса, поддержка открепления в плавающее окно с Always on Top.
- **Панель инструментов (Action Toolbar)**: логическая группировка кнопок с тонкими разделителями.
