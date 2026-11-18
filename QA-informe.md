# QA de Mi POS: informe

Fecha: 2026-11-18 · Rama `fase-3-ui-moderna` · Commit `a238905`

## Preparación
- **Rama y commit:** `fase-3-ui-moderna`, commit `a238905` ("feat: aplica tema en caliente sin reiniciar"). `git status` limpio, al día con origin.
- **Respaldos:** `~/MiPOS/cerveceria.db.qa-bak` y `config.json.qa-bak`, con hash idéntico al original. La config original tenía `theme: "lila"`.
- **pytest:** `39 passed in 19.09s`
- **py_compile main.py:** sin salida, exit 0.
- Ninguna prueba en vivo dejó traceback en la consola.

## Bugs encontrados

### G1 · Grave. El escáner agrega otro producto (POS, tema lila)
1. Crea "QA Test Cerveza" con código `QA777` y "Agua QA" con código `QA7771`.
2. En el buscador escribe `QA777` y pulsa Enter.
- **Esperado:** se agrega QA Test Cerveza.
- **Real:** se agrega **Agua QA**.
- **Causa:** la búsqueda usa `LIKE '%q%'` ordenado por nombre y toma el primero (`ui/pos/pos_search.py`, `add_item_by_search`). Se cobra el precio equivocado y se descuenta el stock de otro producto.

### G2 · Grave. Supr en el buscador borra una línea del ticket (POS)
1. Con 2 líneas en el ticket, escribe algo en el buscador.
2. Pon el cursor dentro del texto y pulsa Supr.
- **Esperado:** se borra un carácter.
- **Real:** se borró la línea "Agua QA ×2" sin confirmar y el texto quedó igual.
- Lo mismo con `+`, `-` y `=`: no se pueden escribir en el buscador.
- **Causa:** `eventFilter` en `ui/pos/pos_view.py` intercepta esas teclas cuando el foco está en `in_search`.

### G3 · Grave. `+`/`-` cambian la línea equivocada (POS, temas lila y menta)
1. Agrega un producto A.
2. Agrega un producto B.
3. Pulsa `+`.
- **Esperado:** sube la cantidad de B.
- **Real:** sube la de A. La selección vuelve a la línea anterior, sobre todo tras cerrar el aviso de stock bajo. En la prueba subió a 4 un producto que ya estaba **desactivado**.
- **Causa:** `_selected_line_id` no se actualiza en `add_item_by_search`, y `load_ticket` restaura la selección vieja.

### G4 · Grave. Se puede vaciar el ticket con un clic
- "Limpiar ticket" borró un ticket de $17.200 sin pedir confirmación (`clear_ticket_items`).
- La ✕ de cada línea tampoco pide confirmación.

### M1 · Medio. Los reportes inflan la ganancia
1. Agrega un producto común de $1.500 con ganancia `0`.
2. Cóbralo.
- **Esperado:** ganancia del día $4.500.
- **Real:** $6.000. Con `gain_per_unit = 0`, `report_service.summary` usa precio − costo, y el costo del producto común es 0.
- El "margen promedio" es un promedio sin ponderar de las líneas: muestra 73,3% cuando el real (ganancia/venta) es 66,7%.

### M2 · Medio. No se guardan los datos del pago
- La referencia (ej. `REF123`), el monto recibido y el vuelto no quedan en la DB: la tabla `sales` no tiene columnas para eso.
- Tras confirmar el cobro no aparece ningún mensaje ni el vuelto.

### M3 · Medio. No se puede escribir una cantidad
- F2 está tomado por el atajo "foco en tabla" (choca con `EditKeyPressed`) y el doble clic no edita.
- Para vender 24 unidades hay que pulsar `+` 23 veces.

### M4 · Medio. Aviso de stock bajo modal en cada escaneo y cada `+`
- Con un lector de códigos, el Enter del escaneo siguiente cierra el popup.
- Enter con el buscador vacío abre otro popup ("Escribe nombre o código").

### M5 · Medio. Reportes vuelve siempre a "Hoy"
1. Elige "Mes actual".
2. Ve a POS y vuelve a Reportes.
- **Real:** el filtro vuelve a Hoy (causa: `showEvent` → `_set_today` en `ui/reports_view.py`).
- Con Desde > Hasta muestra $0 sin ningún aviso.

### M6 · Medio. Textos ilegibles en algunos temas
- **oscuro y grafito:** la fila de stock bajo usa el color fijo `#ffe0b2` (`ui/products/actions.py`), con texto claro encima.
- **oscuro y grafito:** las fechas de Reportes y "Ventas del día" tienen fondo blanco fijo (`ModernDateEdit`, `daily_sales_dialog.py`) con texto blanco.
- **neutro, cerveceria, menta y lila:** el aviso de stock negativo en Cobrar casi no se lee (texto `#7a5b00` sobre ámbar `warning`).
- **grafito:** COBRAR, Nuevo y la fila seleccionada casi no se distinguen del fondo.

### M7 · Medio. Error técnico al repetir un código de barras
- Muestra `UNIQUE constraint failed: products.barcode` en inglés.
- El diálogo se cierra y se pierden los demás cambios de la edición.

### M8 · Medio. Productos desactivados
- No se pueden ver ni reactivar desde la app.
- Al quitar un producto que está en un ticket abierto, el mensaje mezcla "está en tickets abiertos" con "tiene historial".

### Leves (cosméticos)
- "Quitar producto" deshabilitado se ve igual que habilitado.
- La ✕ conserva el rojo del tema anterior hasta que se recarga la tabla.
- Algunas etiquetas tienen una franja de color dentro de las tarjetas: "Tickets abiertos", formularios, Cobrar.
- Los botones de confirmación dicen "Yes/No" en inglés.
- Las celdas de "Ventas del día" se pueden editar (solo en pantalla).
- El diálogo "Editar producto" dice "para agregar el producto".
- La vista previa recorta "Cerveza ..." y el placeholder de "Producto común" sale cortado.
- F12 sin ticket no hace nada y no avisa.
- Al agregar desde una sugerencia, el texto queda en el buscador.
- El foco del teclado casi no se ve en los botones.
- El tema "cerveceria" va sin tilde.
- Enter en Configuración no guarda.

### Lo que funcionó bien
- Cobro con Enter, Esc para cancelar y aviso de monto insuficiente.
- Totales y stock correctos (10 − 3 = 7).
- Ventas `pagada` en la DB.
- Stock en Productos se refresca solo después de vender.
- Los 6 temas se aplican en caliente; la vista previa cambia sin guardar.
- F12 y Supr no se disparan desde otras pestañas.
- Sin ventanas fuera de pantalla ni textos importantes cortados en 1100x720.

## Atajos de teclado

| Atajo | Dónde | ¿Funciona? | ¿Se indica en pantalla? |
|---|---|---|---|
| F12 cobrar | POS | Sí | Sí, en el botón |
| Enter agregar / confirmar | Buscador, Cobrar, diálogos | Sí | Solo en el buscador |
| Esc cerrar | Diálogos | Sí | No |
| F2 foco en tabla / F3 foco en buscador | POS | Sí | No |
| `+` / `-` cantidad | Tabla y buscador | Sí, pero sobre la fila equivocada (G3) | No |
| ↑ / ↓ desde el buscador | POS | Sí | No |
| Supr borrar línea | POS | Peligroso desde el buscador (G2) | No |
| Tab | Formularios | Sí, orden lógico | — |

`main.py` y `ui/charge_dialog.py` no definen atajos propios.

**Faltan:** elegir el medio de pago con teclado, nuevo ticket, limpiar ticket, escribir una cantidad, cambiar de pestaña y buscar en Productos.

## Tabla resumen

| Bug | Severidad | Reproducción | ¿Quién? |
|---|---|---|---|
| G1 Código no busca coincidencia exacta | Grave | Escanear `QA777` con `QA7771` existente | Arreglo directo |
| G2 Supr en el buscador borra una línea | Grave | Supr con el cursor en el buscador | Arreglo directo |
| G3 `+`/`-` sobre la línea equivocada | Grave | Agregar A, agregar B, pulsar `+` | Arreglo directo |
| G4 Limpiar y ✕ sin confirmación | Grave | Clic en "Limpiar ticket" | Arreglo directo |
| M1 Ganancia del producto común | Medio | Producto común con ganancia 0 y ver Reportes | Fase aparte (lógica de reportes) |
| M2 Referencia y vuelto no se guardan | Medio | Cobrar con referencia y revisar `sales` | Fase aparte (migración de DB) |
| M3 No se puede escribir la cantidad | Medio | F2 o doble clic en Cant | Arreglo directo |
| M4 Popups modales al escanear | Medio | Producto con stock bajo y escanear | Fase de UX |
| M5 Filtro de Reportes se resetea / Desde > Hasta | Medio | Mes actual, cambiar de pestaña y volver | Arreglo directo |
| M6 Colores fijos ilegibles en temas | Medio | Temas oscuro y grafito, Productos y Reportes | Arreglo directo (pasar a tokens del tema) |
| M7 Error UNIQUE técnico | Medio | Repetir un código de barras al editar | Arreglo directo |
| M8 Sin reactivar productos | Medio | Desactivar un producto | Fase aparte |
| Leves | Leve | Ver la lista de leves | Fase de pulido |

## 5 mejoras para caja, por impacto
1. **Escaneo confiable:** coincidencia exacta de código primero y avisos de stock en un banner que no interrumpa la venta.
2. **Cantidad rápida:** escribir `3*` antes del código, o una tecla para editar la cantidad. La selección debe quedar siempre en el último producto agregado.
3. **Cobro sin mouse:** teclas para Efectivo, Débito, Crédito y Transferencia, y el vuelto en grande después de confirmar.
4. **Atajos de ticket visibles:** nuevo, limpiar con confirmación, cambiar de pestaña, y una barra inferior que liste los atajos.
5. **Teclas seguras:** Supr, `+` y `-` solo con el foco en la tabla, y confirmación al borrar líneas o vaciar el ticket.

## Restauración
- `cerveceria.db` restaurada desde `.qa-bak`, con hash idéntico. Queda solo "Producto común": 0 ventas, 0 tickets abiertos, ningún producto de prueba.
- `config.json` restaurado y ajustado a `"business_name": "Mi POS"` y `"theme": "neutro"`.
- Los `.qa-bak` siguen en `~/MiPOS`. La verificación final creó `cerveceria.db-wal` (vacío) y `cerveceria.db-shm`; son inofensivos.
- Repositorio sin commits, push ni PR.
