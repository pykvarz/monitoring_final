"""
Константы и стили приложения
"""

# Цвета статусов
COLOR_ONLINE = "#10b981"
COLOR_WAITING = "#f59e0b"
COLOR_OFFLINE = "#ef4444"
COLOR_MAINTENANCE = "#8b5cf6"
COLOR_TOTAL = "#3b82f6"

# Цвета темы (Dark Mode в стиле современного макета)
DARK_BG = "#151820"
DARK_SURFACE = "#181c26"
DARK_BORDER = "#282e3d"
DARK_TEXT = "#f1f5f9"
DARK_TEXT_SECONDARY = "#94a3b8"
DARK_SELECTION = "#2563eb"

# Цвета темы Tactical (NOC Terminal)
TACTICAL_BG = "#090A0F"
TACTICAL_SURFACE = "#0D1117"
TACTICAL_BORDER = "#1F232D"
TACTICAL_TEXT = "#E2E8F0"
TACTICAL_TEXT_SECONDARY = "#64748B"
TACTICAL_SELECTION = "#1F2937"
TACTICAL_ONLINE = "#39FF14"
TACTICAL_WAITING = "#FBBF24"
TACTICAL_OFFLINE = "#EF4444"
TACTICAL_MAINTENANCE = "#A855F7"
TACTICAL_TOTAL = "#00F0FF"

# CSS Стили

def get_table_style(theme="dark"):
    if theme == "tactical":
        return f"""
        QTableView, QTableWidget {{
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 0px;
            background-color: {TACTICAL_BG};
            alternate-background-color: {TACTICAL_SURFACE};
            gridline-color: {TACTICAL_BORDER};
            selection-background-color: {TACTICAL_SELECTION};
            selection-color: {TACTICAL_ONLINE};
            color: {TACTICAL_TEXT};
            show-decoration-selected: 1;
            font-family: Consolas, "Courier New", monospace;
            font-size: 13px;
        }}
        QHeaderView::section {{
            background-color: {TACTICAL_SURFACE};
            padding: 8px 10px;
            border: none;
            border-bottom: 1px solid {TACTICAL_BORDER};
            border-right: 1px solid {TACTICAL_BORDER};
            font-weight: bold;
            color: {TACTICAL_TEXT_SECONDARY};
            text-transform: uppercase;
            font-family: Consolas, "Courier New", monospace;
        }}
        QScrollBar:vertical {{
            background: {TACTICAL_BG};
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {TACTICAL_BORDER};
            min-height: 20px;
            border-radius: 0px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {TACTICAL_TEXT_SECONDARY};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {TACTICAL_BG};
            height: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {TACTICAL_BORDER};
            min-width: 20px;
            border-radius: 0px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {TACTICAL_TEXT_SECONDARY};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        """
    return f"""
        QTableView, QTableWidget {{
            border: 1px solid {DARK_BORDER};
            border-radius: 8px;
            background-color: {DARK_SURFACE};
            alternate-background-color: #1e222e;
            gridline-color: #232938;
            selection-background-color: {DARK_SELECTION};
            selection-color: white;
            color: {DARK_TEXT};
            show-decoration-selected: 1;
        }}
        QHeaderView::section {{
            background-color: #1e2330;
            padding: 8px 10px;
            border: none;
            border-bottom: 2px solid {DARK_BORDER};
            border-right: 1px solid {DARK_BORDER};
            font-weight: bold;
            color: #cbd5e1;
        }}
        QScrollBar:vertical {{
            background: #151820;
            width: 8px;
            margin: 0px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: #282e3d;
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #3b82f6;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: #151820;
            height: 8px;
            margin: 0px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: #282e3d;
            min-width: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #3b82f6;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
    """

def get_dashboard_style(theme="dark"):
    return """
        QFrame {
            background-color: transparent;
            border: none;
            padding: 2px 0px 4px 0px;
        }
    """

def get_stat_card_style(key_or_color: str, theme="dark"):
    """Создание стиля для карточки статистики"""
    key_map = {
        COLOR_TOTAL: "total",
        COLOR_ONLINE: "online",
        COLOR_WAITING: "waiting",
        COLOR_OFFLINE: "offline",
        COLOR_MAINTENANCE: "maintenance",
        "total": "total",
        "online": "online",
        "waiting": "waiting",
        "offline": "offline",
        "maintenance": "maintenance",
    }
    card_key = key_map.get(key_or_color, "total")

    if theme == "tactical":
        config = {
            "total":       {"border": TACTICAL_TOTAL, "bg": "#0D1117", "hover": "#161B22", "color": TACTICAL_TOTAL},
            "online":      {"border": TACTICAL_ONLINE, "bg": "#0D1117", "hover": "#161B22", "color": TACTICAL_ONLINE},
            "waiting":     {"border": TACTICAL_WAITING, "bg": "#0D1117", "hover": "#161B22", "color": TACTICAL_WAITING},
            "offline":     {"border": TACTICAL_OFFLINE, "bg": "#0D1117", "hover": "#161B22", "color": TACTICAL_OFFLINE},
            "maintenance": {"border": TACTICAL_MAINTENANCE, "bg": "#0D1117", "hover": "#161B22", "color": TACTICAL_MAINTENANCE},
        }.get(card_key, {"border": TACTICAL_BORDER, "bg": TACTICAL_SURFACE, "hover": TACTICAL_SELECTION, "color": TACTICAL_TEXT})
        return f"""
            QLabel {{
                background-color: {config['bg']};
                border: 1px solid {TACTICAL_BORDER};
                border-left: 3px solid {config['border']};
                border-radius: 0px;
                padding: 6px 14px 6px 10px;
                min-width: 130px;
                font-family: Consolas, "Courier New", monospace;
            }}
            QLabel:hover {{
                background-color: {config['hover']};
            }}
        """

    config = {
        "total":       {"border": "#2563eb", "bg": "#141c2c", "hover": "#1a253a"},
        "online":      {"border": "#10b981", "bg": "#12241e", "hover": "#183028"},
        "waiting":     {"border": "#f59e0b", "bg": "#241e14", "hover": "#30281a"},
        "offline":     {"border": "#ef4444", "bg": "#261619", "hover": "#341d22"},
        "maintenance": {"border": "#8b5cf6", "bg": "#20172e", "hover": "#2a1e3d"},
    }.get(card_key, {"border": "#3b82f6", "bg": "#141c2c", "hover": "#1a253a"})

    return f"""
        QLabel {{
            background-color: {config['bg']};
            border: 1.5px solid {config['border']};
            border-radius: 10px;
            padding: 6px 14px 6px 12px;
            min-width: 130px;
        }}
        QLabel:hover {{
            background-color: {config['hover']};
        }}
    """

def get_button_style(theme="dark"):
    if theme == "tactical":
        return f"""
        QPushButton {{
            padding: 6px 12px;
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 0px;
            background-color: {TACTICAL_SURFACE};
            color: {TACTICAL_TEXT};
            font-family: Consolas, "Courier New", monospace;
        }}
        QPushButton:hover {{
            background-color: {TACTICAL_BORDER};
            border-color: {TACTICAL_TEXT_SECONDARY};
        }}
        QPushButton:pressed {{
            background-color: {TACTICAL_SELECTION};
        }}
        """
    return f"""
        QPushButton {{
            padding: 6px 12px;
            border: 1px solid {DARK_BORDER};
            border-radius: 4px;
            background-color: {DARK_SURFACE};
            color: {DARK_TEXT};
        }}
        QPushButton:hover {{
            background-color: {DARK_BORDER};
        }}
        QPushButton:pressed {{
            background-color: #505050;
        }}
    """

def get_main_style(theme="dark"):
    if theme == "tactical":
        font_family = 'Consolas, "Courier New", monospace'
        return f"""
        QWidget {{
            font-family: {font_family};
        }}
        QMainWindow, QDialog {{
            background-color: {TACTICAL_BG};
            color: {TACTICAL_TEXT};
        }}
        QLabel {{
            color: {TACTICAL_TEXT};
        }}
        QMenuBar {{
            background-color: {TACTICAL_BG};
            color: {TACTICAL_TEXT};
            border-bottom: 1px solid {TACTICAL_BORDER};
            padding: 2px 4px;
        }}
        QMenuBar::item {{
            background-color: transparent;
            color: {TACTICAL_TEXT};
            padding: 4px 10px;
            border-radius: 0px;
        }}
        QMenuBar::item:selected {{
            background-color: {TACTICAL_SELECTION};
        }}
        QMenu {{
            background-color: {TACTICAL_SURFACE};
            color: {TACTICAL_TEXT};
            border: 1px solid {TACTICAL_BORDER};
        }}
        QMenu::item:selected {{
            background-color: {TACTICAL_SELECTION};
        }}
        QStatusBar {{
            background-color: {TACTICAL_BG};
            color: {TACTICAL_TEXT_SECONDARY};
            border-top: 1px solid {TACTICAL_BORDER};
        }}
        QLineEdit, QSpinBox {{
            background-color: {TACTICAL_SURFACE};
            color: {TACTICAL_TEXT};
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 0px;
            padding: 4px 8px;
            selection-background-color: {TACTICAL_SELECTION};
            font-family: {font_family};
        }}
        QLineEdit:focus, QSpinBox:focus {{
            border-color: {TACTICAL_TEXT_SECONDARY};
        }}
        QGroupBox {{
            font-weight: bold;
            color: {TACTICAL_TEXT};
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 0px;
            margin-top: 12px;
            padding-top: 14px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 4px;
            color: {TACTICAL_TEXT};
        }}
        QCheckBox {{
            color: {TACTICAL_TEXT};
            spacing: 6px;
        }}
        QDialogButtonBox QPushButton, QMessageBox QPushButton {{
            background-color: {TACTICAL_SURFACE};
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 0px;
            padding: 5px 16px;
            color: {TACTICAL_TEXT};
            font-weight: 500;
            min-width: 65px;
            font-family: {font_family};
        }}
        QDialogButtonBox QPushButton:hover, QMessageBox QPushButton:hover {{
            background-color: {TACTICAL_BORDER};
            border-color: {TACTICAL_TEXT_SECONDARY};
        }}
        QDialogButtonBox QPushButton:pressed, QMessageBox QPushButton:pressed {{
            background-color: {TACTICAL_SELECTION};
        }}
        QToolTip {{
            background-color: {TACTICAL_SURFACE};
            color: {TACTICAL_TEXT};
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 0px;
            padding: 4px 8px;
            font-size: 11px;
            font-family: {font_family};
        }}
        QScrollBar:vertical {{
            background-color: {TACTICAL_BG};
            width: 8px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background-color: {TACTICAL_BORDER};
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {TACTICAL_TEXT_SECONDARY};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            background-color: {TACTICAL_BG};
            height: 8px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {TACTICAL_BORDER};
            min-width: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {TACTICAL_TEXT_SECONDARY};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
        {get_combobox_style("tactical")}
        """
    font_family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif'
    return f"""
        QWidget {{
            font-family: {font_family};
        }}
        QMainWindow, QDialog {{
            background-color: {DARK_BG};
            color: {DARK_TEXT};
        }}
        QLabel {{
            color: {DARK_TEXT};
        }}
        QMenuBar {{
            background-color: {DARK_BG};
            color: {DARK_TEXT};
            border-bottom: 1px solid {DARK_BORDER};
            padding: 2px 4px;
        }}
        QMenuBar::item {{
            background-color: transparent;
            color: {DARK_TEXT};
            padding: 4px 10px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background-color: #252b38;
            color: #ffffff;
        }}
        QMenuBar::item:pressed {{
            background-color: #1c202a;
        }}
        QMenu {{
            background-color: {DARK_SURFACE};
            color: {DARK_TEXT};
            border: 1px solid {DARK_BORDER};
            border-radius: 6px;
            padding: 4px 0px;
        }}
        QMenu::item {{
            padding: 6px 28px 6px 24px;
            color: {DARK_TEXT};
            background-color: transparent;
        }}
        QMenu::item:selected {{
            background-color: {DARK_SELECTION};
            color: #ffffff;
        }}
        QMenu::item:disabled {{
            color: {DARK_TEXT_SECONDARY};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {DARK_BORDER};
            margin: 4px 8px;
        }}
        QLineEdit, QSpinBox {{
            background-color: #1c202a;
            color: #f1f5f9;
            border: 1px solid #282e3d;
            border-radius: 6px;
            padding: 4px 8px;
            selection-background-color: #2563eb;
        }}
        QLineEdit:focus, QSpinBox:focus {{
            border-color: #3b82f6;
        }}
        QGroupBox {{
            font-weight: bold;
            color: #f1f5f9;
            border: 1px solid #282e3d;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 14px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 4px;
            color: #f1f5f9;
        }}
        QCheckBox {{
            color: #f1f5f9;
            spacing: 6px;
        }}
        QDialogButtonBox QPushButton, QMessageBox QPushButton {{
            background-color: #1c202a;
            border: 1px solid #282e3d;
            border-radius: 6px;
            padding: 5px 16px;
            color: #f1f5f9;
            font-weight: 500;
            min-width: 65px;
        }}
        QDialogButtonBox QPushButton:hover, QMessageBox QPushButton:hover {{
            background-color: #252b38;
            border-color: #3b82f6;
        }}
        QDialogButtonBox QPushButton:pressed, QMessageBox QPushButton:pressed {{
            background-color: #151820;
        }}
        QScrollBar:vertical {{
            background-color: #151820;
            width: 10px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background-color: #282e3d;
            min-height: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: #3b82f6;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
        }}
        QScrollBar:horizontal {{
            background-color: #151820;
            height: 10px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background-color: #282e3d;
            min-width: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: #3b82f6;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
        }}
        QToolTip {{
            background-color: #1c202a;
            color: #f1f5f9;
            border: 1px solid {DARK_BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        }}
        QSplitter::handle {{
            background-color: transparent;
            width: 3px;
        }}
        QSplitter::handle:hover {{
            background-color: #3b82f6;
        }}
        {get_combobox_style(theme)}
    """

def get_menubar_style(theme="dark"):
    return f"""
        QMenuBar {{
            background-color: {DARK_BG};
            color: {DARK_TEXT};
            border-bottom: 1px solid {DARK_BORDER};
            padding: 2px 4px;
        }}
        QMenuBar::item {{
            background-color: transparent;
            color: {DARK_TEXT};
            padding: 5px 10px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background-color: #252b38;
            color: #ffffff;
        }}
        QMenuBar::item:pressed {{
            background-color: #1c202a;
        }}
    """

def get_combobox_style(theme="dark"):
    if theme == "tactical":
        return f"""
        QComboBox {{
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 2px;
            padding: 4px 24px 4px 10px;
            background-color: {TACTICAL_SURFACE};
            color: {TACTICAL_TEXT};
            font-size: 12px;
            font-family: Consolas, "Courier New", monospace;
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {TACTICAL_TEXT_SECONDARY};
        }}
        QComboBox:focus {{
            border-color: #00F0FF;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 22px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {TACTICAL_TEXT_SECONDARY};
            width: 0px;
            height: 0px;
            margin-right: 6px;
        }}
        QComboBox::down-arrow:hover {{
            border-top-color: #00F0FF;
        }}
        QComboBox QAbstractItemView,
        QComboBox QListView {{
            background-color: {TACTICAL_SURFACE};
            color: {TACTICAL_TEXT};
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 2px;
            selection-background-color: {TACTICAL_SELECTION};
            selection-color: {TACTICAL_ONLINE};
            padding: 2px;
            outline: 0px;
            margin: 0px;
            font-family: Consolas, "Courier New", monospace;
        }}
        QComboBox QAbstractItemView::item,
        QComboBox QListView::item {{
            min-height: 24px;
            padding: 4px 8px;
            color: {TACTICAL_TEXT};
            background-color: transparent;
        }}
        QComboBox QAbstractItemView::item:hover,
        QComboBox QAbstractItemView::item:selected,
        QComboBox QListView::item:hover,
        QComboBox QListView::item:selected {{
            background-color: {TACTICAL_SELECTION};
            color: {TACTICAL_ONLINE};
        }}
        QComboBox QAbstractItemView QScrollBar:vertical,
        QComboBox QListView QScrollBar:vertical {{
            background: {TACTICAL_BG};
            width: 6px;
            margin: 0px;
            border: none;
        }}
        QComboBox QAbstractItemView QScrollBar::handle:vertical,
        QComboBox QListView QScrollBar::handle:vertical {{
            background: {TACTICAL_BORDER};
            min-height: 16px;
            border-radius: 3px;
        }}
        QComboBox QAbstractItemView QScrollBar::add-line:vertical,
        QComboBox QAbstractItemView QScrollBar::sub-line:vertical,
        QComboBox QListView QScrollBar::add-line:vertical,
        QComboBox QListView QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
        }}
        """
    return f"""
        QComboBox {{
            border: 1px solid {DARK_BORDER};
            border-radius: 6px;
            padding: 4px 24px 4px 10px;
            background-color: {DARK_SURFACE};
            color: {DARK_TEXT};
            font-size: 12px;
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: #3b82f6;
        }}
        QComboBox:focus {{
            border-color: #60a5fa;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 22px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {DARK_TEXT_SECONDARY};
            width: 0px;
            height: 0px;
            margin-right: 6px;
        }}
        QComboBox::down-arrow:hover {{
            border-top-color: #3b82f6;
        }}
        QComboBox QAbstractItemView,
        QComboBox QListView {{
            background-color: {DARK_SURFACE};
            color: {DARK_TEXT};
            border: 1px solid {DARK_BORDER};
            border-radius: 6px;
            selection-background-color: {DARK_SELECTION};
            selection-color: #ffffff;
            padding: 2px;
            outline: 0px;
            margin: 0px;
        }}
        QComboBox QAbstractItemView::item,
        QComboBox QListView::item {{
            min-height: 24px;
            padding: 4px 8px;
            border-radius: 4px;
            color: {DARK_TEXT};
            background-color: transparent;
        }}
        QComboBox QAbstractItemView::item:hover,
        QComboBox QAbstractItemView::item:selected,
        QComboBox QListView::item:hover,
        QComboBox QListView::item:selected {{
            background-color: {DARK_SELECTION};
            color: #ffffff;
        }}
        QComboBox QAbstractItemView QScrollBar:vertical,
        QComboBox QListView QScrollBar:vertical {{
            background: {DARK_BG};
            width: 6px;
            margin: 0px;
            border: none;
        }}
        QComboBox QAbstractItemView QScrollBar::handle:vertical,
        QComboBox QListView QScrollBar::handle:vertical {{
            background: {DARK_BORDER};
            min-height: 16px;
            border-radius: 3px;
        }}
        QComboBox QAbstractItemView QScrollBar::add-line:vertical,
        QComboBox QAbstractItemView QScrollBar::sub-line:vertical,
        QComboBox QListView QScrollBar::add-line:vertical,
        QComboBox QListView QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
        }}
    """

def get_menu_style(theme="dark"):
    if theme == "tactical":
        return f"""
        QMenu {{
            background-color: {TACTICAL_SURFACE};
            color: {TACTICAL_TEXT};
            border: 1px solid {TACTICAL_BORDER};
            border-radius: 0px;
            padding: 4px 2px;
            font-family: Consolas, "Courier New", monospace;
        }}
        QMenu::item {{
            padding: 7px 24px 7px 12px;
            color: {TACTICAL_TEXT};
            background-color: transparent;
            border-radius: 0px;
            margin: 1px 2px;
        }}
        QMenu::item:selected {{
            background-color: {TACTICAL_SELECTION};
            color: {TACTICAL_ONLINE};
        }}
        QMenu::item:disabled {{
            color: {TACTICAL_TEXT_SECONDARY};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {TACTICAL_BORDER};
            margin: 4px 6px;
        }}
        """
    return f"""
        QMenu {{
            background-color: {DARK_SURFACE};
            color: {DARK_TEXT};
            border: 1px solid {DARK_BORDER};
            border-radius: 8px;
            padding: 5px 3px;
        }}
        QMenu::item {{
            padding: 7px 24px 7px 10px;
            color: {DARK_TEXT};
            background-color: transparent;
            border-radius: 6px;
            margin: 1px 3px;
        }}
        QMenu::item:selected {{
            background-color: rgba(59, 130, 246, 0.22);
            color: #ffffff;
            border: 1px solid rgba(59, 130, 246, 0.35);
        }}
        QMenu::item:disabled {{
            color: {DARK_TEXT_SECONDARY};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {DARK_BORDER};
            margin: 4px 6px;
        }}
    """

SCAN_LABEL_STYLE_ACTIVE = "color: #007bff; font-weight: bold;"
SCAN_LABEL_STYLE_FINISHED = "color: #28a745;"

# SVG Иконки (Paths)
# SVG Иконки (Paths в стиле Lucide)
def _get_svg_wrapper(path_data, theme="dark", size=16, stroke_width=2):
    color = "#e1e1e1"
    return f"""
    <svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round">
        {path_data}
    </svg>
    """

def get_svg_add_host(theme="dark"):
    return _get_svg_wrapper('<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>', theme)

def get_svg_add_group(theme="dark"):
    return _get_svg_wrapper('<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>', theme)

def get_svg_import(theme="dark"):
    return _get_svg_wrapper('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>', theme)

def get_svg_export(theme="dark"):
    return _get_svg_wrapper('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>', theme)

def get_svg_scan(theme="dark"):
    return _get_svg_wrapper('<path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>', theme)

def get_svg_pause(theme="dark"):
    return _get_svg_wrapper('<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>', theme)

def get_svg_play(theme="dark"):
    return _get_svg_wrapper('<polygon points="6 4 20 12 6 20 6 4"/>', theme)

def get_svg_bulk(theme="dark"):
    return _get_svg_wrapper('<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/>', theme)

def get_svg_settings(theme="dark"):
    return _get_svg_wrapper('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>', theme)

def get_svg_delete(theme="dark"):
    return _get_svg_wrapper('<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>', theme)

def get_svg_refresh(theme="dark"):
    return _get_svg_wrapper('<path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>', theme)

def get_svg_edit(theme="dark"):
    return _get_svg_wrapper('<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4L18.5 2.5z"/>', theme)

def get_svg_theme(theme="light"):
    if theme == "dark":
        return _get_svg_wrapper('<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>', theme)
    return _get_svg_wrapper('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>', theme)

def get_svg_ping(theme="dark"):
    return _get_svg_wrapper('<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>', theme)

def get_svg_app_icon(theme="dark"):
    """Брендовая иконка приложения Network Monitor: контрастный темный бейдж, дисплей монитора и неоновый пульс активности сети"""
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="app_bg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0B111E"/>
      <stop offset="100%" stop-color="#162033"/>
    </linearGradient>
    <linearGradient id="app_border" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#2563EB"/>
    </linearGradient>
    <linearGradient id="app_pulse" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00F0FF"/>
      <stop offset="100%" stop-color="#10B981"/>
    </linearGradient>
  </defs>
  <rect x="3" y="3" width="58" height="58" rx="14" fill="url(#app_bg)" stroke="url(#app_border)" stroke-width="2.5"/>
  <rect x="11" y="11" width="42" height="29" rx="4" fill="#050811" stroke="#334155" stroke-width="1.8"/>
  <path d="M32 40 L32 48" stroke="#475569" stroke-width="3" stroke-linecap="round"/>
  <path d="M23 48 L41 48" stroke="#475569" stroke-width="2.5" stroke-linecap="round"/>
  <polyline points="15 25.5, 23 25.5, 27 17, 32 34, 37 20, 41 25.5, 49 25.5" fill="none" stroke="url(#app_pulse)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="37" cy="20" r="2" fill="#00F0FF"/>
  <circle cx="32" cy="37" r="1" fill="#10B981"/>
</svg>'''

def get_svg_total(theme="dark"):
    # Icon: Server
    return _get_svg_wrapper('<rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>', theme)

def get_svg_history(theme="dark"):
    # Icon: Clock/History
    return _get_svg_wrapper('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>', theme)

def get_svg_wrench(theme="dark"):
    # Icon: Wrench / Maintenance
    return _get_svg_wrapper('<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>', theme)

def get_svg_bell(theme="dark"):
    # Icon: Bell / Notifications active
    return _get_svg_wrapper('<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>', theme)

def get_svg_bell_off(theme="dark"):
    # Icon: Bell off / Notifications muted
    return _get_svg_wrapper('<path d="M13.73 21a2 2 0 0 1-3.46 0"/><path d="M18.63 13A17.89 17.89 0 0 1 18 8"/><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 0 0-9.33-5"/><line x1="1" y1="1" x2="23" y2="23"/>', theme)

def get_svg_ticket(theme="dark"):
    # Icon: Ticket / Helpdesk
    return _get_svg_wrapper('<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2z"/><line x1="13" y1="5" x2="13" y2="19" stroke-dasharray="2 2"/>', theme)

def get_svg_ticket_check(theme="dark"):
    # Icon: Ticket resolved / closed
    return _get_svg_wrapper('<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2z"/><polyline points="9 12 11 14 15 10"/>', theme)

def _get_status_svg(path, color):
    # Увеличиваем размер SVG до 64x64 для четкого рендеринга (HiDPI)
    # Иконка будет смасштабирована вниз в UI, что даст сглаживание
    return f"""
    <svg viewBox="0 0 24 24" width="64" height="64" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        {path}
    </svg>
    """

SVG_ONLINE = _get_status_svg(
    '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    COLOR_ONLINE
)

SVG_OFFLINE = _get_status_svg(
    '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
    COLOR_OFFLINE
)

SVG_WAITING = _get_status_svg(
    '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    COLOR_WAITING
)

SVG_MAINTENANCE = _get_status_svg(
    '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l1.4-1.4a1 1 0 0 0 0-1.4l-1.6-1.6a1 1 0 0 0-1.4 0l-1.4 1.4z"/><path d="M14.5 10.5l-9 9a2.12 2.12 0 0 1-3-3l9-9"/>',
    COLOR_MAINTENANCE
)

# Новые насыщенные SVG иконки для дашборд-карточек (в стиле предоставленного макета)
SVG_CARD_TOTAL = """
<svg viewBox="0 0 36 36" width="36" height="36" fill="none" stroke="#3b82f6" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <rect x="4" y="5" width="28" height="8" rx="2.5" fill="#1e3a5f" fill-opacity="0.3"/>
    <line x1="8" y1="9" x2="15" y2="9"/>
    <circle cx="24" cy="9" r="1.2" fill="#60a5fa"/>
    <circle cx="28" cy="9" r="1.2" fill="#3b82f6"/>
    <rect x="4" y="16" width="28" height="8" rx="2.5" fill="#1e3a5f" fill-opacity="0.3"/>
    <line x1="8" y1="20" x2="15" y2="20"/>
    <circle cx="24" cy="20" r="1.2" fill="#60a5fa"/>
    <circle cx="28" cy="20" r="1.2" fill="#3b82f6"/>
    <line x1="18" y1="24" x2="18" y2="29"/>
    <line x1="10" y1="29" x2="26" y2="29"/>
    <circle cx="10" cy="29" r="1.3" fill="#3b82f6"/>
    <circle cx="26" cy="29" r="1.3" fill="#3b82f6"/>
</svg>
"""

SVG_CARD_ONLINE = """
<svg viewBox="0 0 36 36" width="36" height="36" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18 4L6 9v9.5c0 6.8 5.1 12.8 12 14.3 6.9-1.5 12-7.5 12-14.3V9L18 4z" fill="#064e3b" fill-opacity="0.3"/>
    <polyline points="12 18 16 22 24 14" stroke="#34d399" stroke-width="2.5"/>
</svg>
"""

SVG_CARD_WAITING = """
<svg viewBox="0 0 36 36" width="36" height="36" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="18" cy="18" r="13" fill="#78350f" fill-opacity="0.25"/>
    <polyline points="18 10 18 18 24 18" stroke="#fbbf24" stroke-width="2.2"/>
</svg>
"""

SVG_CARD_OFFLINE = """
<svg viewBox="0 0 36 36" width="36" height="36" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18 4L3 30h30L18 4z" fill="#7f1d1d" fill-opacity="0.25"/>
    <circle cx="25" cy="25" r="5.5" fill="#ef4444" stroke="#181b24" stroke-width="1.5"/>
    <line x1="23" y1="23" x2="27" y2="27" stroke="#ffffff" stroke-width="1.5"/>
    <line x1="27" y1="23" x2="23" y2="27" stroke="#ffffff" stroke-width="1.5"/>
    <line x1="18" y1="12" x2="18" y2="20" stroke="#fca5a5" stroke-width="2"/>
    <circle cx="18" cy="24" r="1" fill="#fca5a5"/>
</svg>
"""

SVG_CARD_MAINTENANCE = """
<svg viewBox="0 0 36 36" width="36" height="36" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M28 8a5 5 0 0 0-6.5-.4L10.5 18.6a2.2 2.2 0 0 0 0 3.1l1.8 1.8a2.2 2.2 0 0 0 3.1 0L26.4 12.5A5 5 0 0 0 28 8z" fill="#4c1d95" fill-opacity="0.3"/>
    <path d="M8 28a5 5 0 0 0 6.5.4l11-11a2.2 2.2 0 0 0 0-3.1l-1.8-1.8a2.2 2.2 0 0 0-3.1 0L9.6 23.5A5 5 0 0 0 8 28z" fill="#4c1d95" fill-opacity="0.3"/>
</svg>
"""
