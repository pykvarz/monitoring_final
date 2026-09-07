---
description: "Python + PyQt5 best practices for desktop application development"
globs: "**/*.py, tests/**/*.py"
alwaysApply: false
---
# Python + PyQt5 Desktop App — Stack Rules

## Thread Safety (критично для PyQt5)
- UI-элементы создавать и изменять **только в главном потоке**.
- Из фоновых QThread передавать данные через **сигналы Qt**, никогда не напрямую.
- Для SQLite в QThread — создавать **именованное соединение** (`QSqlDatabase.addDatabase("QSQLITE", connection_name)`), не переиспользовать соединение главного потока.
- `QMutex` / `QMutexLocker` для защиты разделяемых данных между потоками.

## Сигналы и слоты
- Сигналы эмитить через `emit()`, слоты декорировать `@pyqtSlot(...)` с явными типами.
- Не хранить ссылки на лямбды-обработчики сигналов в локальных переменных — они будут удалены GC.
- Отключать сигналы в `closeEvent` или деструкторе, чтобы избежать вызовов после удаления объекта.

## SQLite через PyQt5.QtSql
- `QSqlQuery` — всегда вызывать `query.finish()` после итерации, чтобы освободить ресурсы.
- Параметры передавать через `bindValue`, никогда не форматировать строку запроса напрямую (SQL-инъекция).
- Группировать множество INSERT/UPDATE в одну транзакцию (`db.transaction()` / `db.commit()`).
- Миграции схемы: `ALTER TABLE ... ADD COLUMN` с обработкой ошибки "column already exists" — нормально, но лучше проверять через `PRAGMA table_info`.

## Архитектура компонентов
- Бизнес-логика — в отдельных классах (Repository, Service), не в виджетах.
- Виджеты подписываются на сигналы данных, не тянут данные напрямую из БД.
- Один `QApplication` на процесс; в тестах проверять `QCoreApplication.instance()` перед созданием.
- DI-контейнер: не использовать глобальный singleton в тестах — сбрасывать перед каждым тестом.

## Работа с памятью
- Qt-объекты с `parent` удаляются автоматически. Без `parent` — следить за жизненным циклом.
- `QThread`: перед удалением вызвать `stop()` + `wait()`, иначе краш при выходе.
- `ThreadPoolExecutor`: вызвать `shutdown(wait=True)` при завершении приложения.

## Стиль кода
- PEP 8, snake_case для методов/переменных, PascalCase для классов.
- Type hints для всех публичных методов.
- Максимальная длина строки: 100 символов.
- Абсолютные импорты, без `from . import`.

## Тестирование
- Тесты — `pytest`. Фикстуры в `conftest.py`.
- UI-тесты без реального дисплея: `QApplication([])` или `QCoreApplication([])`.
- Для SQLite в тестах — использовать `":memory:"` вместо файлового пути.
- Мокать `PingService`, `NotificationService` через `unittest.mock.patch`.

## Сборка (.exe)
- PyInstaller + `.spec`-файл под контролем версий.
- Hidden imports для `plyer.platforms.win.notification` прописывать явно в `.spec`.
- `CREATE_NO_WINDOW` (0x08000000) при вызове subprocess на Windows — обязательно.
