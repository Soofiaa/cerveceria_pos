from ui.theme import THEMES, DEFAULT_THEME, get_theme

REQUIRED_KEYS = {
    "primary", "secondary", "background", "text", "accent",
    "danger", "warning", "success", "surface", "input_text", "primary_text",
}


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_every_preset_has_all_keys():
    for name, theme in THEMES.items():
        missing = REQUIRED_KEYS - theme.keys()
        assert not missing, f"{name} sin claves: {missing}"


def test_primary_text_contrast_is_at_least_4_5():
    # Par real que se pinta: texto "primary_text" sobre fondo "primary".
    for name, theme in THEMES.items():
        ratio = _contrast(theme["primary_text"], theme["primary"])
        assert ratio >= 4.5, f"{name}: contraste {ratio:.2f}:1 < 4.5:1"


def test_inputs_text_contrast_is_at_least_4_5():
    for name, theme in THEMES.items():
        ratio = _contrast(theme["input_text"], theme["surface"])
        assert ratio >= 4.5, f"{name}: input {ratio:.2f}:1 < 4.5:1"


def test_default_theme_exists():
    assert DEFAULT_THEME in THEMES
    assert get_theme("no_existe") == THEMES[DEFAULT_THEME]
