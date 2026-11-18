THEMES = {
    "neutro": {
        "primary": "#3498db",
        "secondary": "#2c3e50",
        "background": "#ecf0f1",
        "text": "#2c3e50",
        "accent": "#f6c058",
        "danger": "#e74c3c",
        "warning": "#f1c40f",
        "success": "#2ecc71",
        "surface": "#ffffff",
        "input_text": "#2c3e50"
    },
    "cerveceria": {
        "primary": "#f2a72a",
        "secondary": "#c26a00",
        "background": "#fbf7ef",
        "text": "#4a3e2c",
        "accent": "#f6c058",
        "danger": "#c0392b",
        "warning": "#f39c12",
        "success": "#27ae60",
        "surface": "#ffffff",
        "input_text": "#4a3e2c"
    },
    "oscuro": {
        "primary": "#2471a3",
        "secondary": "#bdc3c7",
        "background": "#2c3e50",
        "text": "#ecf0f1",
        "accent": "#f6c058",
        "danger": "#e74c3c",
        "warning": "#f1c40f",
        "success": "#2ecc71",
        "surface": "#34495e",
        "input_text": "#ecf0f1"
    }
}

def get_theme(name="neutro"):
    return THEMES.get(name, THEMES["neutro"])
