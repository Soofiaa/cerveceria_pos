"""Temas de la app Flet (Fase 3). Sin PySide6: diccionarios planos.

Cada tema trae las claves que usa la app. "lila" conserva EXACTAMENTE los
colores de la maqueta aprobada (flet_app/main.py antes de la fase 3), no el
lila de Qt (#7d3c98). Los demas son los presets de Qt (ui/theme.py).

Contraste: primary_text sobre primary >= 4.5:1, salvo "cerveceria" (texto
oscuro sobre dorado, a proposito).
"""

_WARN = {"warn_bg": "#fff4d6", "warn_text": "#6e4500", "warn_badge": "#f1c40f",
         "disabled_bg": "#d6d1db", "disabled_text": "#5f5966"}

THEMES = {
    "neutro": {
        "dark": False,
        "primary": "#2471a3", "primary_text": "#ffffff",
        "secondary": "#5d6d7e", "background": "#f4f6f8", "text": "#1c2833",
        "accent": "#aed6f1", "danger": "#c0392b", "warning": "#b9770e",
        "success": "#1e8449", "surface": "#ffffff", "input_text": "#1c2833",
        "surface2": "#eaf2f8", "border": "#aed6f1", "icon": "#34495e",
        **_WARN,
    },
    "cerveceria": {
        "dark": False,
        "primary": "#f2a72a", "primary_text": "#2b1d00",
        "secondary": "#c26a00", "background": "#fbf7ef", "text": "#4a3e2c",
        "accent": "#f6c058", "danger": "#c0392b", "warning": "#b9770e",
        "success": "#1e8449", "surface": "#ffffff", "input_text": "#4a3e2c",
        "surface2": "#fdf1d6", "border": "#f6c058", "icon": "#4a3e2c",
        **_WARN,
    },
    "oscuro": {
        "dark": True,
        "primary": "#2471a3", "primary_text": "#ffffff",
        "secondary": "#7f8c8d", "background": "#1c2833", "text": "#ecf0f1",
        "accent": "#5dade2", "danger": "#e74c3c", "warning": "#f5b041",
        "success": "#2ecc71", "surface": "#2c3e50", "input_text": "#ecf0f1",
        "surface2": "#34495e", "border": "#5d6d7e", "icon": "#ecf0f1",
        **_WARN,
    },
    "menta": {
        "dark": False,
        "primary": "#1e8449", "primary_text": "#ffffff",
        "secondary": "#5f8b77", "background": "#eef8f3", "text": "#1d3b30",
        "accent": "#a9dfbf", "danger": "#c0392b", "warning": "#b9770e",
        "success": "#1e8449", "surface": "#ffffff", "input_text": "#1d3b30",
        "surface2": "#e3f4ea", "border": "#a9dfbf", "icon": "#1d3b30",
        **_WARN,
    },
    "lila": {
        "dark": False,
        "primary": "#6c3483", "primary_text": "#ffffff",
        "secondary": "#5d6d7e", "background": "#f6eff7", "text": "#1c2833",
        "accent": "#d7bde2", "danger": "#a93226", "warning": "#b9770e",
        "success": "#1e8449", "surface": "#ffffff", "input_text": "#1c2833",
        "surface2": "#efe3f1", "border": "#e2d0e6", "icon": "#34495e",
        **_WARN,
    },
    "grafito": {
        "dark": True,
        "primary": "#8090a8", "primary_text": "#1a202c",
        "secondary": "#718096", "background": "#2d3748", "text": "#e2e8f0",
        "accent": "#a0aec0", "danger": "#fc8181", "warning": "#f6ad55",
        "success": "#68d391", "surface": "#3a4658", "input_text": "#e2e8f0",
        "surface2": "#4a5568", "border": "#4a5568", "icon": "#e2e8f0",
        **_WARN,
    },
}

DEFAULT_THEME = "lila"


def get_theme(name=None):
    """Tema por nombre; si no existe o no viene, lila (el look aprobado)."""
    return THEMES.get(name, THEMES[DEFAULT_THEME])
