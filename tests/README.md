# Network Monitor - Test Suite

## Overview

Comprehensive test suite for the Network Monitor application covering:
- Core models and validation
- Data layer (Database, DataManager, Repository)
- Services (Ping, Notification, Excel)
- Business logic (MonitorThread, Filters, Theme)
- UI components (Toolbar, Menu, Table settings)
- Subscribers and event handling
- Integration workflows

## Running Tests

### Run All Tests
```bash
cd c:\Users\zykva\Desktop\projects\mon
python -m unittest discover tests
```

### Run Specific Test Module
```bash
python -m unittest tests.test_models
python -m unittest tests.test_data_manager
python -m unittest tests.test_ping_service
```

### Run Single Test Class
```bash
python -m unittest tests.test_models.TestHostModel
```

### Run Single Test Method
```bash
python -m unittest tests.test_models.TestHostModel.test_valid_ip
```

## Test Coverage

### Core Models (models.py)
- ✅ `test_models.py` - Host and AppConfig validation, helper functions

### Data Layer
- ✅ `test_host_repository.py` - Repository CRUD operations
- ✅ `test_data_manager.py` - DataManager with signals
- ✅ `test_database.py` - Database connection and tables
- ✅ `test_storage.py` - JSON storage and migration

### Services
- ✅ `test_ping_service.py` - Ping with mocks and fallback
- ✅ `test_notification_service.py` - System notifications
- ✅ `test_excel_service.py` - Excel import/export

### Business Logic
- ✅ `test_monitor_logic.py` - Monitor thread status transitions
- ✅ `test_filter_manager.py` - Filtering and search
- ✅ `test_theme_manager.py` - Theme switching

### UI Components
- ✅ `test_toolbar_builder.py` - Toolbar creation
- ✅ `test_menu_builder.py` - Menu creation
- ✅ `test_table_settings_manager.py` - Column settings

### Subscribers
- ✅ `test_monitor_subscriber.py` - Monitor event handling
- ✅ `test_table_subscriber.py` - Table updates
- ✅ `test_dashboard_subscriber.py` - Dashboard updates

### Integration
- ✅ `test_integration.py` - End-to-end workflows

## Test Structure

```
tests/
├── __init__.py              # Package marker
├── conftest.py              # Shared fixtures
├── README.md                # This file
├── test_models.py           # Model tests
├── test_host_repository.py  # Repository tests (existing)
├── test_data_manager.py     # DataManager tests
├── ...                      # Other test files
```

## Writing Tests

### Using Shared Fixtures

```python
from tests.conftest import TestFixtures

class MyTestCase(unittest.TestCase):
    def setUp(self):
        # Setup Qt application
        TestFixtures.setup_qapp()
        
        # Create in-memory database
        self.db_manager = TestFixtures.create_in_memory_db()
        
        # Create sample data
        self.host = TestFixtures.create_sample_host()
        self.hosts = TestFixtures.create_sample_hosts(10)
    
    def tearDown(self):
        # Cleanup
        TestFixtures.cleanup_db(self.db_manager)
```

### Testing with Mocks

```python
from unittest.mock import MagicMock, patch

@patch('services.ping')
def test_ping_success(self, mock_ping):
    mock_ping.return_value = 0.123
    result = PingService.ping_host("127.0.0.1")
    self.assertTrue(result)
```

## Coverage Goals

- **Core Logic**: >80% coverage
- **Services**: >75% coverage
- **UI Components**: >60% coverage
- **Integration**: Key workflows covered

## Dependencies

Tests use only standard library and existing project dependencies:
- `unittest` (Python standard library)
- `PyQt5` (already required)
- `unittest.mock` (Python standard library)

No additional test dependencies required.

## Continuous Integration

To set up CI (optional):
1. Add `.github/workflows/tests.yml`
2. Run tests on push/PR
3. Generate coverage reports

## Troubleshooting

### Qt Platform Plugin Error
If you see "Could not find the Qt platform plugin", make sure PyQt5 is properly installed:
```bash
pip install PyQt5
```

### Import Errors
Make sure you're running tests from the project root:
```bash
cd c:\Users\zykva\Desktop\projects\mon
python -m unittest discover tests
```

### Database Lock Errors
Tests use in-memory databases to avoid conflicts. If you see lock errors, ensure previous test cleanup completed properly.
