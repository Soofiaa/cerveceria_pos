# ui/theme.py
# Presets de tema. Todas las claves son obligatorias (ver tests/test_theme.py).
# primary: fondo de botones/pestaña activa; debe dar >= 4.5:1 con texto blanco,
# salvo "cerveceria", que usa texto oscuro sobre dorado.

THEMES = {
    "neutro": {
        "primary": "#2471a3",
        "secondary": "#5d6d7e",
        "background": "#f4f6f8",
        "text": "#1c2833",
        "accent": "#aed6f1",
        "danger": "#c0392b",
        "warning": "#b9770e",
        "success": "#1e8449",
        "surface": "#ffffff",
        "input_text": "#1c2833",
        "primary_text": "#ffffff",
    },
    "cerveceria": {
        "primary": "#f2a72a",
        "secondary": "#c26a00",
        "background": "#fbf7ef",
        "text": "#4a3e2c",
        "accent": "#f6c058",
        "danger": "#c0392b",
        "warning": "#b9770e",
        "success": "#1e8449",
        "surface": "#ffffff",
        "input_text": "#4a3e2c",
        "primary_text": "#2b1d00",
    },
    "oscuro": {
        "primary": "#2471a3",
        "secondary": "#7f8c8d",
        "background": "#1c2833",
        "text": "#ecf0f1",
        "accent": "#5dade2",
        "danger": "#e74c3c",
        "warning": "#f5b041",
        "success": "#2ecc71",
        "surface": "#2c3e50",
        "input_text": "#ecf0f1",
        "primary_text": "#ffffff",
    },
    "menta": {
        "primary": "#1e8449",
        "secondary": "#5f8b77",
        "background": "#eef8f3",
        "text": "#1d3b30",
        "accent": "#a9dfbf",
        "danger": "#c0392b",
        "warning": "#b9770e",
        "success": "#1e8449",
        "surface": "#ffffff",
        "input_text": "#1d3b30",
        "primary_text": "#ffffff",
    },
    "lila": {
        "primary": "#7d3c98",
        "secondary": "#8e6a9f",
        "background": "#f8f2fb",
        "text": "#2e1a3a",
        "accent": "#d7bde2",
        "danger": "#c0392b",
        "warning": "#b9770e",
        "success": "#1e8449",
        "surface": "#ffffff",
        "input_text": "#2e1a3a",
        "primary_text": "#ffffff",
    },
    "grafito": {
        "primary": "#8090a8",
        "secondary": "#718096",
        "background": "#2d3748",
        "text": "#e2e8f0",
        "accent": "#a0aec0",
        "danger": "#fc8181",
        "warning": "#f6ad55",
        "success": "#68d391",
        "surface": "#3a4658",
        "input_text": "#e2e8f0",
        "primary_text": "#1a202c",
    },
}

DEFAULT_THEME = "neutro"


def get_theme(name=DEFAULT_THEME):
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def build_stylesheet(theme_name: str) -> str:
    """QSS moderno: esquinas suaves, botones planos, inputs y tablas con superficie del tema."""
    t = get_theme(theme_name)
    return f"""
    /* ===================== BASE ===================== */
    QWidget {{
        background-color: {t["background"]};
        color: {t["text"]};
        font-family: "Inter", "Segoe UI", Arial, sans-serif;
        font-size: 11pt;
    }}

    /* ===================== PESTAÑAS ===================== */
    QTabWidget::pane {{
        border: 1px solid {t["secondary"]};
        border-radius: 10px;
        padding: 12px;
        background-color: {t["surface"]};
    }}
    QTabBar::tab {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        margin-right: 4px;
        color: {t["text"]};
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {t["primary"]};
        color: {t["primary_text"]};
        font-weight: 700;
    }}
    QTabBar::tab:hover:!selected {{
        background: {t["surface"]};
    }}

    /* ===================== SIDEBAR (Tickets abiertos) ===================== */
    QWidget#Sidebar {{
        background: {t["surface"]};
        border: 1px solid {t["secondary"]};
        border-radius: 10px;
        padding: 12px;
    }}

    QLabel#SidebarTitle {{
        color: {t["text"]};
        font-size: 16pt;
        font-weight: 800;
    }}

    QListWidget#TicketList {{
        background-color: transparent;
        border: none;
        color: {t["text"]};
    }}
    QListWidget#TicketList::item {{
        padding: 10px 12px;
        border-radius: 8px;
        margin-bottom: 4px;
    }}
    QListWidget#TicketList::item:selected {{
        background-color: {t["primary"]};
        color: {t["primary_text"]};
    }}

    /* ===================== TITULOS Y TEXTOS ===================== */
    QLabel#SectionTitle {{
        font-size: 18pt;
        font-weight: 800;
        color: {t["text"]};
    }}
    QLabel#HintLabel {{
        color: {t["secondary"]};
    }}
    QLabel#TotalsBadge {{
        background: {t["surface"]};
        border: 1px solid {t["secondary"]};
        padding: 16px 20px;
        border-radius: 10px;
        color: {t["text"]};
        font-size: 22pt;
        font-weight: 800;
    }}

    /* ===================== BOTONES ===================== */
    QPushButton {{
        background-color: {t["surface"]};
        border: 1px solid {t["secondary"]};
        border-radius: 8px;
        padding: 8px 14px;
        font-weight: 600;
        color: {t["text"]};
    }}
    QPushButton:hover {{
        background-color: {t["background"]};
    }}
    QPushButton:pressed {{
        background-color: {t["secondary"]};
        color: {t["primary_text"]};
    }}
    QPushButton:disabled {{
        color: {t["secondary"]};
        border-color: {t["secondary"]};
    }}

    QPushButton[buttonType="primary"] {{
        background-color: {t["primary"]};
        border: 1px solid {t["primary"]};
        color: {t["primary_text"]};
        font-weight: 700;
    }}
    QPushButton[buttonType="primary"]:hover {{
        background-color: {t["primary"]};
        border-color: {t["text"]};
    }}

    QPushButton[buttonType="danger"] {{
        background-color: {t["surface"]};
        border: 1px solid {t["danger"]};
        color: {t["danger"]};
    }}
    QPushButton[buttonType="danger"]:hover {{
        background-color: {t["danger"]};
        color: {t["primary_text"]};
    }}

    QPushButton[buttonType="ghost"] {{
        background-color: transparent;
        border: 1px dashed {t["secondary"]};
        color: {t["text"]};
    }}
    QPushButton[buttonType="ghost"]:hover {{
        border-style: solid;
    }}

    /* Medios de pago en PAGAR: mismo primario del tema, sin amarillo fijo */
    QPushButton#PayMethodButton {{
        border-radius: 8px;
        padding: 6px 12px;
    }}
    QPushButton#PayMethodButton:checked {{
        background-color: {t["primary"]};
        border: 1px solid {t["primary"]};
        color: {t["primary_text"]};
    }}

    /* Filtros de Reportes (Hoy, Semana, Mes, Año) */
    QPushButton#ReportFilter {{
        background-color: {t["surface"]};
        border: 1px solid {t["secondary"]};
        border-radius: 8px;
        color: {t["text"]};
        padding: 6px 12px;
        font-weight: 600;
    }}
    QPushButton#ReportFilter:checked {{
        background-color: {t["primary"]};
        border-color: {t["primary"]};
        color: {t["primary_text"]};
    }}
    QPushButton#ReportFilter:hover {{
        background-color: {t["background"]};
    }}

    /* ===================== INPUTS ===================== */
    QLineEdit, QComboBox, QSpinBox, QDateEdit {{
        background-color: {t["surface"]};
        color: {t["input_text"]};
        border: 1px solid {t["secondary"]};
        border-radius: 8px;
        padding: 6px 10px;
        selection-background-color: {t["primary"]};
        selection-color: {t["primary_text"]};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {{
        border: 1px solid {t["primary"]};
    }}
    QLineEdit::placeholder {{
        color: {t["secondary"]};
    }}

    /* Solo reubicamos el área del botón de fecha, SIN cambiar el icono nativo */
    QDateEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: right center;
        width: 18px;
        border: none;
        background: transparent;
        margin-right: 2px;
    }}

    /* ===================== TABLAS ===================== */
    QTableView, QTableWidget {{
        background-color: {t["surface"]};
        alternate-background-color: {t["background"]};
        color: {t["input_text"]};
        border: 1px solid {t["secondary"]};
        border-radius: 8px;
        gridline-color: transparent;
        selection-background-color: {t["primary"]};
        selection-color: {t["primary_text"]};
    }}

    QHeaderView::section {{
        background: {t["background"]};
        color: {t["text"]};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {t["secondary"]};
        font-weight: 700;
    }}

    /* ===================== GROUPBOX ===================== */
    QGroupBox {{
        border: 1px solid {t["secondary"]};
        border-radius: 10px;
        margin-top: 18px;
        padding-top: 8px;
        background-color: {t["surface"]};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {t["text"]};
        font-weight: 700;
        background-color: {t["background"]};
    }}

    /* ===================== DIALOGOS ===================== */
    QDialog {{
        background-color: {t["surface"]};
        border: 1px solid {t["secondary"]};
        border-radius: 10px;
    }}
    QDialog QLabel#DialogTitle {{
        font-size: 16pt;
        font-weight: 800;
        color: {t["text"]};
    }}

    QMessageBox {{
        background-color: {t["surface"]};
        border-radius: 10px;
    }}
    QMessageBox QLabel {{
        color: {t["text"]};
    }}
    QMessageBox QPushButton {{
        min-width: 90px;
        padding: 7px 12px;
    }}
    """
