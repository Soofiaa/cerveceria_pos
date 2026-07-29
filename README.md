# Cervecería POS

Sistema de punto de venta (POS) de escritorio para cervecerías artesanales, desarrollado en Python con PySide6 (Qt) y SQLite. Gestiona ventas, tickets abiertos, productos, control de stock y reportes de caja diaria.

---

## Índice

- [Características](#características)
- [Stack técnico](#stack-técnico)
- [Arquitectura](#arquitectura)
- [Instalación y ejecución](#instalación-y-ejecución)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Reglas de negocio relevantes](#reglas-de-negocio-relevantes)
- [Testing](#testing)
- [Cobertura de tests y decisiones de alcance](#cobertura-de-tests-y-decisiones-de-alcance)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Autora](#autora)

---

## Características

- **Punto de venta (POS):** búsqueda rápida de productos, tickets abiertos con múltiples ítems, atajos de teclado para agilizar el cobro.
- **Gestión de productos:** alta, edición y baja lógica (los productos con historial de ventas no se eliminan físicamente, se desactivan — ver [Reglas de negocio](#reglas-de-negocio-relevantes)).
- **Control de stock:** descuento automático de inventario al cerrar una venta, dentro de la misma transacción que registra el cobro. Indicador visual para stock bajo o negativo.
- **Reportes:** resumen de ventas por rango de fechas (ingresos, ganancia, cantidad de tickets, ticket promedio), con respaldo/backup de productos exportable.
- **Persistencia con migraciones idempotentes:** el esquema de la base de datos evoluciona de forma segura entre versiones, sin perder datos existentes.

## Stack técnico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3 |
| Interfaz gráfica | PySide6 (Qt) |
| Base de datos | SQLite |
| Testing | pytest |
| Empaquetado | PyInstaller |

## Arquitectura

El proyecto separa explícitamente la lógica de negocio de la interfaz gráfica:

```
core/   → lógica de negocio y acceso a datos (independiente de Qt)
ui/     → widgets, diálogos y vistas de PySide6
```

Esta separación permite testear la lógica de negocio (`core/`) sin necesidad de un entorno gráfico, y es la razón por la que el proyecto tiene una suite de tests con pytest a pesar de ser una aplicación de escritorio.

Dentro de `ui/`, el módulo del punto de venta (`ui/pos/`) usa el patrón de **mixins** para dividir responsabilidades (búsqueda, acciones, atajos de teclado, manejo de tickets) sin acoplar todo en un único archivo monolítico.

## Instalación y ejecución

```bash
# Clonar el repositorio
git clone https://github.com/Soofiaa/cerveceria_pos.git
cd cerveceria_pos

# Crear y activar un entorno virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
python main.py
```

La base de datos SQLite se crea automáticamente en el primer arranque (ver `core/db_manager.py`, función `bootstrap()`), aplicando todas las migraciones necesarias.

## Estructura del proyecto

```
cerveceria_pos/
├── main.py                        # Punto de entrada de la aplicación
├── core/                          # Lógica de negocio (sin dependencias de Qt)
│   ├── db_manager.py               # Conexión, esquema y migraciones idempotentes
│   ├── product_service.py          # CRUD de productos, baja lógica, stock
│   ├── sales_service.py            # Conversión de ticket a venta, cobro
│   ├── ticket_service.py           # Gestión de tickets abiertos
│   ├── report_service.py           # Reportes y resúmenes de ventas
│   ├── product_backup_service.py   # Exportación de respaldo de productos
│   ├── time_utils.py
│   └── utils_format.py
├── ui/                             # Interfaz gráfica (PySide6)
│   ├── main_window.py
│   ├── charge_dialog.py
│   ├── products_view.py
│   ├── reports_view.py
│   ├── pos/                        # Módulo del punto de venta (mixins)
│   └── products/, reports/         # Submódulos de acciones y diálogos
├── tests/                          # Suite de tests con pytest
│   ├── test_sales_service.py
│   ├── test_product_service.py
│   ├── test_report_service.py
│   └── test_ticket_service.py
├── conftest.py                     # Fixture temp_db compartida por los tests
├── requirements.txt                 # Dependencias de producción
└── requirements-dev.txt             # Dependencias adicionales para testing
```

## Reglas de negocio relevantes

Algunas decisiones de diseño que vale la pena explicitar, porque no son evidentes solo mirando el código:

- **Los productos no se eliminan físicamente si tienen historial de ventas.** En vez de borrarlos (lo que rompería la trazabilidad de ventas ya cerradas), se marcan como inactivos (`is_active = 0`) mediante `desactivar_producto()`. Dejan de aparecer en búsquedas activas pero su historial de ventas se conserva intacto para efectos de reportes.
- **El descuento de stock ocurre dentro de la misma transacción que el cobro.** Si por algún motivo el descuento de stock fallara, la venta tampoco se registra — evita estados inconsistentes entre lo vendido y lo descontado del inventario.
- **Se permite vender con stock negativo, con advertencia visual, en vez de bloquear la venta.** Esto es intencional: en un negocio pequeño, el conteo de stock del sistema no siempre refleja la realidad física en tiempo real (reposición no registrada aún, error de conteo, etc.), y bloquear una venta real por un dato de sistema potencialmente desactualizado es más costoso para la operación que permitirla con aviso.
- **"Producto común"** (el ítem genérico para ventas sin código de barras específico) queda exento del control de stock, ya que no representa una unidad de inventario real.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

Los tests usan una base de datos temporal por ejecución (no `:memory:` — ver nota de diseño abajo) y **nunca tocan la base de datos real del usuario**.

**Nota de diseño:** se descartó `:memory:` para la fixture de tests porque `get_conn()` en `db_manager.py` abre una conexión SQLite nueva en cada llamada. Con `:memory:`, cada conexión nueva sería una base de datos en blanco distinta entre sí, por lo que `bootstrap()` crearía las tablas en una conexión que la siguiente operación no vería. Se usa en cambio un archivo temporal por test, compatible con este patrón de conexión-por-llamada.

## Cobertura de tests y decisiones de alcance

El objetivo de la suite de tests no es cobertura exhaustiva del código, sino cubrir con criterio las rutas de negocio donde un error tiene mayor impacto real (dinero registrado, integridad de datos históricos, reportes). Elegir qué testear es, en sí mismo, una decisión deliberada.

**Áreas testeadas:**

| Área | Por qué |
|---|---|
| `sales_service.cobrar_ticket()` | Es el punto donde un bug afecta directamente el dinero registrado en el sistema. |
| `product_service` (baja lógica, validaciones) | Protege la integridad del historial de ventas frente a borrados. |
| `report_service.summary()` | Reportes con cálculos incorrectos son difíciles de detectar a simple vista sin verificación. |
| `ticket_service` (acumulación de cantidad, eliminación de ítems) | Lógica intermedia usada en todo el flujo de venta; un bug silencioso ahí no se detecta con tests de extremo a extremo. |

**Áreas explícitamente no testeadas:**

| Área | Por qué se dejó fuera |
|---|---|
| Migraciones individuales de `db_manager.py` | Ya son defensivas por diseño (verifican existencia de columnas antes de alterarlas); bajo riesgo. |
| `product_backup_service.py`, `time_utils.py`, `utils_format.py` | Utilidades de bajo riesgo y bajo impacto. |
| Funciones de agregación repetitivas de `report_service` (`top_products`, `daily_totals`, `hourly_totals`, `monthly_totals`) | Mismo patrón ya validado en `summary()`; no aportan una habilidad de testing distinta. |
| `ui/` | Requeriría un arnés de testing distinto (ej. `pytest-qt`), inversión desproporcionada para el alcance de este proyecto. |
| `force_delete_product()` | Función deprecada tras la introducción de la baja lógica; ya no es el camino recomendado. |

## Limitaciones conocidas

- Aplicación mono-usuario (no diseñada para múltiples cajas concurrentes sobre la misma base de datos).
- La exportación de respaldo de productos genera un archivo CSV, no un `.xlsx` nativo.

## Autora

**Sofía Menzel** — Ingeniera en Ejecución Informática (PUCV, 2025)
[LinkedIn](#) · [Portafolio](https://portafolio-web-theta-coral.vercel.app) · [GitHub](https://github.com/Soofiaa)
