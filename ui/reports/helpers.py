from PySide6.QtCore import QDate


def fmt_pct(value) -> str:
    """Formatea un porcentaje como '25,0 %'."""
    try:
        v = float(value)
    except Exception:
        return "-"

    if 0 <= v <= 1:
        v = v * 100.0
    return f"{v:,.1f} %".replace(",", ".")


def date_range_to_strings(start: QDate, end: QDate) -> tuple[str, str]:
    """Convierte dos QDate en tuplas de texto dd-MM-yyyy."""
    return start.toString("dd-MM-yyyy"), end.toString("dd-MM-yyyy")


def week_bounds(current: QDate) -> tuple[QDate, QDate]:
    dow = current.dayOfWeek()
    return current.addDays(-(dow - 1)), current


def month_bounds(current: QDate) -> tuple[QDate, QDate]:
    return QDate(current.year(), current.month(), 1), current


def year_bounds(current: QDate) -> tuple[QDate, QDate]:
    return QDate(current.year(), 1, 1), current
