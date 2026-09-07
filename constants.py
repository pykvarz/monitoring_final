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

# CSS Стили

def get_table_style(theme="light"):
    if theme == "dark":
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
        """
    return """
        QTableView, QTableWidget {
            border: 1px solid #d0d7de;
            border-radius: 8px;
            background-color: white;
            alternate-background-color: #f8f9fa;
            gridline-color: #e2e8f0;
            selection-background-color: #e3f2fd;
            selection-color: #000;
            show-decoration-selected: 1;
        }
        QHeaderView::section {
            background-color: #f6f8fa;
            padding: 8px 10px;
            border: none;
            border-bottom: 2px solid #d0d7de;
            border-right: 1px solid #d0d7de;
            font-weight: bold;
            color: #24292f;
        }
    """

def get_dashboard_style(theme="light"):
    if theme == "dark":
        return """
            QFrame {
                background-color: transparent;
                border: none;
                padding: 2px 0px 4px 0px;
            }
        """
    return """
        QFrame {
            background-color: transparent;
            border: none;
            padding: 2px 0px 4px 0px;
        }
    """

def get_stat_card_style(key_or_color: str, theme="light"):
    """Создание стиля для карточки статистики в стиле неоновых рамок из макета"""
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

    if theme == "dark":
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
    else:
        config = {
            "total":       {"border": "#3b82f6", "bg": "#eff6ff", "hover": "#dbeafe"},
            "online":      {"border": "#10b981", "bg": "#ecfdf5", "hover": "#d1fae5"},
            "waiting":     {"border": "#f59e0b", "bg": "#fffbeb", "hover": "#fef3c7"},
            "offline":     {"border": "#ef4444", "bg": "#fef2f2", "hover": "#fee2e2"},
            "maintenance": {"border": "#8b5cf6", "bg": "#f5f3ff", "hover": "#ede9fe"},
        }.get(card_key, {"border": "#3b82f6", "bg": "#eff6ff", "hover": "#dbeafe"})

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

def get_button_style(theme="light"):
    if theme == "dark":
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
    return """
        QPushButton {
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: white;
        }
        QPushButton:hover {
            background-color: #f8f9fa;
        }
        QPushButton:pressed {
            background-color: #e9ecef;
        }
    """

def get_main_style(theme="light"):
    if theme == "dark":
        return f"background-color: {DARK_BG}; color: {DARK_TEXT};"
    return ""

def get_menu_style(theme="light"):
    if theme == "dark":
        return f"""
            QMenu {{
                background-color: {DARK_SURFACE};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                padding: 5px;
            }}
            QMenu::item:selected {{
                background-color: {DARK_SELECTION};
            }}
        """
    return """
        QMenu {
            background-color: white;
            border: 1px solid #ddd;
            padding: 5px;
        }
        QMenu::item {
            padding: 8px 25px 8px 20px;
        }
        QMenu::item:selected {
            background-color: #e3f2fd;
        }
    """

SCAN_LABEL_STYLE_ACTIVE = "color: #007bff; font-weight: bold;"
SCAN_LABEL_STYLE_FINISHED = "color: #28a745;"

# SVG Иконки (Paths)
# SVG Иконки (Paths в стиле Lucide)
def _get_svg_wrapper(path_data, theme="light", size=16, stroke_width=2):
    color = "#e1e1e1" if theme == "dark" else "#24292f"
    return f"""
    <svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round">
        {path_data}
    </svg>
    """

def get_svg_add_host(theme="light"):
    return _get_svg_wrapper('<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>', theme)

def get_svg_add_group(theme="light"):
    return _get_svg_wrapper('<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>', theme)

def get_svg_import(theme="light"):
    return _get_svg_wrapper('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>', theme)

def get_svg_export(theme="light"):
    return _get_svg_wrapper('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>', theme)

def get_svg_scan(theme="light"):
    return _get_svg_wrapper('<path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>', theme)

def get_svg_pause(theme="light"):
    return _get_svg_wrapper('<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>', theme)

def get_svg_play(theme="light"):
    return _get_svg_wrapper('<polygon points="6 4 20 12 6 20 6 4"/>', theme)

def get_svg_bulk(theme="light"):
    return _get_svg_wrapper('<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/>', theme)

def get_svg_settings(theme="light"):
    return _get_svg_wrapper('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>', theme)

def get_svg_delete(theme="light"):
    return _get_svg_wrapper('<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>', theme)

def get_svg_edit(theme="light"):
    return _get_svg_wrapper('<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4L18.5 2.5z"/>', theme)

def get_svg_theme(theme="light"):
    if theme == "dark":
        return _get_svg_wrapper('<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>', theme)
    return _get_svg_wrapper('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>', theme)

def get_svg_ping(theme="light"):
    return _get_svg_wrapper('<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>', theme)

def get_svg_total(theme="light"):
    # Icon: Server
    return _get_svg_wrapper('<rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>', theme)

def get_svg_history(theme="light"):
    # Icon: Clock/History
    return _get_svg_wrapper('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>', theme)

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
