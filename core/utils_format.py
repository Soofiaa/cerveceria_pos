# core/utils_format.py
def fmt_money(value: int | float | None) -> str:
    """Formatea enteros con separador de miles (punto) y simbolo $.

    Negativos con el signo delante del simbolo (-$1.500). None -> $0.
    """
    if value is None:
        return "$0"
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "$0"
    sign = "-" if n < 0 else ""
    return sign + "$" + f"{abs(n):,}".replace(",", ".")
