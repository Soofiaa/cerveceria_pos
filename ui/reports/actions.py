from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from core.report_service import summary, top_products
from core.utils_format import fmt_money
from .helpers import fmt_pct, week_bounds, month_bounds, year_bounds, date_range_to_strings


class ReportActionsMixin:
    def _set_today(self):
        today = QDate.currentDate()
        self.in_from.setDate(today)
        self.in_to.setDate(today)
        self.load_data()

    def _set_week_current(self):
        fr, to = week_bounds(QDate.currentDate())
        self.in_from.setDate(fr)
        self.in_to.setDate(to)
        self.load_data()

    def _set_month_current(self):
        fr, to = month_bounds(QDate.currentDate())
        self.in_from.setDate(fr)
        self.in_to.setDate(to)
        self.load_data()

    def _set_year_current(self):
        fr, to = year_bounds(QDate.currentDate())
        self.in_from.setDate(fr)
        self.in_to.setDate(to)
        self.load_data()

    def load_data(self):
        d1, d2 = self.in_from.date(), self.in_to.date()
        s = summary(d1, d2)

        total = s.get("total", 0)
        tickets = s.get("tickets", 0)
        avg = s.get("avg_ticket", 0)
        profit = s.get("profit", 0)
        avg_mgn = s.get("avg_margin", 0.0)

        self.lbl_total.setText(fmt_money(total))
        self.lbl_profit.setText(fmt_money(profit))
        self.lbl_count.setText(str(tickets))
        self.lbl_avg.setText(fmt_money(avg))
        self.lbl_avg_margin.setText(fmt_pct(avg_mgn))

        tops = top_products(d1, d2, limit=10)
        self.tbl_top.setRowCount(0)
        for tp in tops:
            i = self.tbl_top.rowCount()
            self.tbl_top.insertRow(i)

            name_item = QTableWidgetItem(tp["name"])
            qty_item = QTableWidgetItem(str(tp["qty"]))
            rv = QTableWidgetItem(fmt_money(tp["revenue"]))

            qty_item.setTextAlignment(Qt.AlignCenter)
            rv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.tbl_top.setItem(i, 0, name_item)
            self.tbl_top.setItem(i, 1, qty_item)
            self.tbl_top.setItem(i, 2, rv)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar CSV",
            "resumen_ventas.csv",
            "CSV (*.csv)",
        )
        if not path:
            return

        try:
            d1, d2 = self.in_from.date(), self.in_to.date()
            s = summary(d1, d2)

            total = s.get("total", 0)
            tickets = s.get("tickets", 0)
            avg = s.get("avg_ticket", 0)
            profit = s.get("profit", 0)
            avg_mgn = s.get("avg_margin", 0.0)

            desde_str, hasta_str = date_range_to_strings(d1, d2)

            with open(path, "w", newline="", encoding="latin-1") as f:
                import csv

                w = csv.writer(f, delimiter=";")
                w.writerow(["Métrica", "Valor"])
                w.writerow(["Desde", desde_str])
                w.writerow(["Hasta", hasta_str])
                w.writerow(["Total vendido", fmt_money(total)])
                w.writerow(["Ganancia total", fmt_money(profit)])
                w.writerow(["Número de ventas", tickets])
                w.writerow(["Venta promedio", fmt_money(avg)])
                w.writerow(["Margen de utilidad promedio", fmt_pct(avg_mgn)])

            QMessageBox.information(self, "Exportar", "CSV de resumen exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Exportar", f"No se pudo exportar:\n{e}")
