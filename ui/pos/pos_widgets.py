# ui/pos/pos_widgets.py

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QStyledItemDelegate, QSpinBox, QLineEdit


class IntSpinDelegate(QStyledItemDelegate):
    """Delegate para editar cantidades con QSpinBox en la tabla del POS."""
    def __init__(self, parent=None, minimum=1, maximum=10**6):
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum

    def createEditor(self, parent, option, index):
        spin = QSpinBox(parent)
        spin.setRange(self.minimum, self.maximum)
        spin.setAccelerated(True)
        spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return spin

    def setEditorData(self, editor, index):
        try:
            val = int(index.data() or 0)
        except Exception:
            val = self.minimum
        editor.setValue(max(self.minimum, min(self.maximum, val)))

    def setModelData(self, editor, model, index):
        model.setData(index, str(editor.value()))


class SearchLine(QLineEdit):
    """QLineEdit que siempre selecciona todo el texto al recibir foco."""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)
