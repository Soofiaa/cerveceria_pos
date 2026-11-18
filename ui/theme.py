THEMES = {
    "neutro": {
        "primary": "#3498db",
        "secondary": "#2c3e50",
        "background": "#ecf0f1",
        "text": "#2c3e50",
        "accent": "#f6c058"
    },
    "cerveceria": {
        "primary": "#f2a72a",
        "secondary": "#c26a00",
        "background": "#fbf7ef",
        "text": "#4a3e2c",
        "accent": "#f6c058"
    },
    "oscuro": {
        "primary": "#3498db",
        "secondary": "#bdc3c7",
        "background": "#2c3e50",
        "text": "#ecf0f1",
        "accent": "#f6c058"
    }
}

def get_theme(name="neutro"):
    return THEMES.get(name, THEMES["neutro"])
