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
- Exportación de datos a Excel
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
