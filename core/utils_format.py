# core/utils_format.py
def fmt_money(value: int | float | None) -> str:
    """Formatea enteros con separadores de miles y símbolo $."""
    if value is None:
        value = 0
    try:
        return f"${int(value):,}".replace(",", ".")
    except Exception:
        return "$0"
