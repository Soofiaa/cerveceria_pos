from PySide6.QtWidgets import QFileDialog, QMessageBox

from core import product_backup_service as pbs


class ProductBackupMixin:
    """Operaciones de exportación/importación de productos."""

    def export_products_csv(self):
        """Permite al usuario guardar la lista de productos en un CSV."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar lista de productos",
            "productos.csv",
            "CSV (*.csv)",
        )
        if not path:
            return

        try:
            pbs.export_products_csv(path)
            QMessageBox.information(
                self,
                "Exportar productos",
                "La lista de productos se guardó correctamente.",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Exportar productos",
                f"No se pudo guardar la lista de productos:\n{e}",
            )

    def import_products_csv(self):
        """Permite al usuario cargar/actualizar productos desde un CSV."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Cargar lista de productos",
            "",
            "CSV (*.csv)",
        )
        if not path:
            return

        resp = QMessageBox.question(
            self,
            "Cargar productos",
            (
                "Se van a importar productos desde el archivo seleccionado.\n\n"
                "- Si un producto ya existe (mismo código de barras o nombre), se actualizará.\n"
                "- Si no existe, se creará uno nuevo.\n\n"
                "Esta acción no elimina productos existentes.\n\n"
                "¿Deseas continuar?"
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        try:
            result = pbs.import_products_csv(path)
            msg = (
                f"Productos creados: {result.get('created', 0)}\n"
                f"Productos actualizados: {result.get('updated', 0)}\n"
                f"Filas omitidas por error: {result.get('skipped', 0)}"
            )
            QMessageBox.information(self, "Cargar productos", msg)
            self.reload()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Cargar productos",
                f"No se pudieron importar los productos:\n{e}",
            )
