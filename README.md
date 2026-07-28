# Sistema POS para Cervecería

Aplicación de escritorio tipo Punto de Venta (POS) desarrollada en Python para apoyar la operación diaria de cervecerías artesanales y pequeños negocios.

Este proyecto fue diseñado con foco en arquitectura modular, lógica de negocio real y mantenibilidad, y se presenta como proyecto de portafolio profesional para roles junior en desarrollo de software, QA y análisis técnico–funcional.

---

## Descripción General

El sistema permite gestionar ventas mediante tickets, administrar productos y generar reportes de ventas de forma clara y confiable.  
Su arquitectura modular facilita el mantenimiento, mejora la escalabilidad y permite distribuir la aplicación como ejecutable para Windows.

---

## Tecnologías Utilizadas

- Python 3  
- PySide6 (Qt) – Interfaz gráfica de escritorio  
- SQLite – Base de datos relacional local  
- Git / GitHub – Control de versiones  

---

## Funcionalidades Principales

### Punto de Venta / Gestión de Tickets
- Creación automática de tickets
- Búsqueda de productos por nombre o código de barras
- Edición de cantidades con validación numérica
- Eliminación de ítems mediante tecla Suprimir / Delete
- Navegación por teclado (flechas arriba / abajo)
- Cálculo automático de totales
- Proceso de cobro y conversión a venta registrada

### Gestión de Productos
- Operaciones CRUD completas
- Búsqueda inteligente
- Gestión de precios
- Control de duplicados mediante código de barras

### Reportes
- Reporte diario de ventas
- Reportes por rango de fechas
- Exportación de datos a CSV
- Calendario personalizado sin botones de incremento

### Base de Datos
- Base de datos SQLite local generada automáticamente
- Integridad referencial activa para asegurar consistencia de datos

---

## Arquitectura y Diseño

La aplicación está estructurada bajo una arquitectura modular, separando claramente responsabilidades:

- Capa de interfaz (UI – PySide6): manejo de vistas y experiencia de usuario  
- Capa de lógica de negocio: servicios, validaciones y reglas del sistema  
- Capa de persistencia: gestión de base de datos SQLite  

Se utilizan mixins para desacoplar controladores, lógica y vistas, mejorando la reutilización de código y la mantenibilidad del sistema.

---

## Estructura del Proyecto

```text
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

---

## Cobertura de tests y decisiones de alcance

Los tests (`pytest`, ver `requirements-dev.txt`) se concentraron en la lógica de negocio de `core/` — cobro, integridad de datos y reportes — en vez de perseguir cobertura exhaustiva. En un proyecto de este tamaño la cobertura total no es el objetivo: elegir bien qué merece test, sí lo es. Cada área se evaluó por el costo real de que falle en silencio, no por cuánto código tiene.

### Área testeada y por qué

| Área testeada | Por qué |
|---|---|
| `sales_service.cobrar_ticket()` | Es el punto donde un bug afecta directamente el dinero registrado: convierte un ticket en una venta pagada e irreversible. |
| `product_service` (`delete_product`, `desactivar_producto`, `list_products`) | Es la capa que decide si se puede borrar o dar de baja un producto sin romper el historial de ventas ya cobradas (motivo original de la Fase 3). |
| `report_service.summary()` | Alimenta directamente los reportes que ve el dueño del negocio (ingresos, ganancia, ticket promedio); un error ahí no se nota hasta que ya se tomó una decisión mal informada. |
| `ticket_service` (`add_item`, `update_item_qty`, validaciones) | Es la única capa que nunca se ejercita con asserts propios en los demás archivos de test (se usa solo como *fixture* de apoyo), y tiene comportamiento no obvio: acumula cantidad en vez de duplicar líneas, y trata qty≤0 como "eliminar línea" en vez de rechazarlo. |

### Área no testeada y por qué se dejó fuera

| Área no testeada | Por qué se dejó fuera |
|---|---|
| Migraciones individuales de `db_manager.py` | Son defensivas por diseño (chequean con `_column_exists`/`_table_has_column` antes de aplicar cualquier cambio) y de bajo riesgo: ya se validaron manualmente durante el desarrollo de cada fase contra bases con esquema viejo. |
| `product_backup_service.py`, `time_utils.py`, `utils_format.py` | Utilidades de bajo riesgo (formateo, fechas, import/export de CSV) sin lógica de negocio ni efectos irreversibles sobre datos ya guardados. |
| `report_service.top_products` / `daily_totals` / `hourly_totals` / `monthly_totals` | Repiten el mismo patrón de agregación SQL ya validado en `summary()` (mismo `JOIN`, mismo filtro de fecha, mismo tipo de `GROUP BY`); testearlas no ejercita ninguna lógica nueva. |
| `ui/` | Requeriría un arnés de test distinto (por ejemplo `pytest-qt`) — inversión desproporcionada para el alcance de este proyecto. |

`force_delete_product()` quedó deprecada (ver Fase 3) y a propósito no tiene tests nuevos: ya no es el camino recomendado para eliminar productos con historial, se conserva solo como referencia del problema que motivó el cambio a baja lógica.
