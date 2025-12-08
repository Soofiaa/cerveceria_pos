# Cervecería POS
Es una aplicación de escritorio diseñada para agilizar ventas, gestionar productos y llevar un control confiable del negocio.
Su arquitectura modular facilita el mantenimiento, mejora la escalabilidad y permite distribuir el sistema como ejecutable para Windows.

## Funciones Principales
### POS / Gestión de Tickets
~ Creación automática de tickets. <br>
~ Agregar productos por búsqueda o código. <br>
~ Cantidades editables con validación numérica. <br>
~ Eliminación de ítems con tecla Suprimir/Delete. <br>
~ Navegación con flechas arriba/abajo. <br>
~ Cálculo automático de totales. <br>
~ Cobro → conversión a venta registrada.

### Productos
~ CRUD completo. <br>
~ Búsqueda inteligente. <br>
~ Gestión de precios. <br>
~ Control de duplicados (código de barras).

### Reportes
~ Reporte diario. <br>
~ Reporte por rango de fechas. <br>
~ Exportación a Excel. <br>
~ Calendario personalizado sin botones de incremento.

### Base de Datos
~ SQLite local generada automáticamente. <br>
~ Integridad referencial activa.

## UI
~ PySide6. <br>
~ Delegates personalizados para cantidades. <br>
~ Mixins que separan control, lógica y vistas. <br>
~ Estilo simple y práctico para uso rápido. <br>

```
cerveceria_pos/
│
├── core/
│   ├── db_manager.py
│   ├── product_service.py
│   ├── ticket_service.py
│   ├── sales_service.py
│   ├── utils_format.py
│   └── time_utils.py
│
├── ui/
│   ├── main_window.py
│   ├── pos/
│   │   ├── pos_view.py
│   │   ├── pos_mixins.py
│   │   └── pos_utils.py
│   ├── reports/
│   │   └── reports_view.py
│   ├── products/
│   │   └── products_view.py
│   └── widgets/
│       └── custom_calendar.py
│
├── assets/
│   ├── icons/
│   └── images/
│
├── main.py
└── requirements.txt
```

## Instalación
```
python -m venv venv <br>
venv\Scripts\activate
pip install -r requirements.txt
python main.py

```
