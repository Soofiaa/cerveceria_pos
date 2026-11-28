"""Mi POS - Pagina de inventario para el telefono (Fase E2).

Solo lectura: el telefono pide GET /api/inventory con la clave de inventario
(X-Inventory-Key) y muestra los datos. La pagina se sirve desde
/api/inventario sin autenticacion (no trae datos: los pide con la clave).
"""
from core import product_service as ps

INVENTARIO_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Inventario - Mi POS</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background: #f4f6f8; color: #1c2833; }
  .barra { padding: 14px 16px; background: #1c2833; color: #fff; font-size: 14px; }
  .barra h1 { margin: 0 0 4px 0; font-size: 20px; font-weight: 700; }
  .barra .sub { font-size: 13px; opacity: 0.9; }
  .sinconexion { background: #fff3cd; color: #856404; padding: 8px 16px; font-size: 13px; border-bottom: 1px solid #ffeeba; }
  .controles { display: flex; gap: 10px; padding: 12px 16px; background: #fff; border-bottom: 1px solid #e2e6ea; }
  .buscador { flex: 1; min-width: 0; }
  .buscador input { width: 100%; padding: 12px 14px; font-size: 17px; border: 1px solid #d0d6dd; border-radius: 10px; background: #fafbfc; color: #1c2833; outline: none; }
  .buscador input:focus { border-color: #6c3483; }
  .selector { display: flex; align-items: center; gap: 8px; font-size: 15px; }
  .selector select { padding: 8px 10px; font-size: 15px; border: 1px solid #d0d6dd; border-radius: 8px; background: #fff; }
  .grupo { padding: 0 16px 8px 16px; }
  .grupo h2 { margin: 0 0 8px 0; font-size: 16px; color: #6c3483; font-weight: 700; border-bottom: 2px solid #e2e6ea; padding-bottom: 4px; }
  .grupo.sin-categoria h2 { color: #8a8f98; }
  .tarjeta { background: #fff; border: 1px solid #e2e6ea; border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; cursor: pointer; user-select: none; }
  .tarjeta.tachada { opacity: 0.55; text-decoration: line-through; }
  .tarjeta .nombre { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
  .tarjeta .stock { font-size: 15px; font-weight: 700; color: #c0392b; margin-bottom: 4px; }
  .sello { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-right: 6px; }
  .sello.agotado { background: #c0392b; color: #fff; }
  .sello.poco { background: #e67e22; color: #fff; }
  .comprar { color: #27ae60; font-weight: 700; font-size: 14px; margin-left: 6px; }
  .vacio { padding: 32px 16px; text-align: center; color: #6c757d; font-size: 16px; }
</style>
</head>
<body>
  <div class="barra">
    <h1 id="nombre-negocio">Inventario</h1>
    <div class="sub" id="actualizado">Actualizado --:--</div>
  </div>
  <div class="sinconexion" id="banda" style="display:none">Sin conexion <span id="fecha-copia"></span></div>
  <div class="controles">
    <div class="buscador"><input type="search" id="buscador" placeholder="Buscar producto..."></div>
    <div class="selector">
      <label>Mostrar: </label>
      <select id="modo">
        <option value="faltantes">Solo lo que falta</option>
        <option value="todos">Todo</option>
      </select>
    </div>
  </div>
  <div id="contenedor"></div>
  <div id="vacio" class="vacio" style="display:none">No hay productos para mostrar.</div>
<script>
(function(){
  const STORAGE_KEY = "mipos_inv_data";
  const KEY_STORAGE = "mipos_inv_key";

  function obtenerClave(){
    const url = new URL(window.location.href);
    const desdeUrl = url.searchParams.get("clave");
    if (desdeUrl){
      localStorage.setItem(KEY_STORAGE, desdeUrl);
      return desdeUrl;
    }
    return localStorage.getItem(KEY_STORAGE) || "";
  }

  function fechaHora(iso){
    try { return new Date(iso).toLocaleString("es-ES", { weekday:"short", day:"numeric", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit" }); }
    catch(e){ return iso; }
  }

  function horaAhora(){
    return new Date().toLocaleTimeString("es-ES", { hour:"2-digit", minute:"2-digit" });
  }

  function dibujar(data){
    const nombre = data.business_name || "Mi POS";
    document.getElementById("nombre-negocio").textContent = nombre + " · Inventario";
    document.getElementById("actualizado").textContent = "Actualizado " + (data.generated_at ? fechaHora(data.generated_at) : horaAhora());

    const faltantesIds = new Set((data.faltantes || []).map(function(p){ return p.id; }));
    let productos = data.inventario || [];
    if (!Array.isArray(productos)) productos = [];

    // Agrupar por categoria; sin categoria al final.
    const porCategoria = {};
    productos.forEach(function(p){
      const cat = p.category_name || "Sin categoria";
      if (!porCategoria[cat]) porCategoria[cat] = [];
      porCategoria[cat].push(p);
    });
    const orden = Object.keys(porCategoria).sort(function(a, b){
      const aFinal = (a === "Sin categoria") ? 1 : 0;
      const bFinal = (b === "Sin categoria") ? 1 : 0;
      if (aFinal !== bFinal) return aFinal - bFinal;
      return a.localeCompare(b);
    });

    const modo = document.getElementById("modo").value;
    const filtro = (document.getElementById("buscador").value || "").toLowerCase();

    const contenedor = document.getElementById("contenedor");
    contenedor.innerHTML = "";
    let hay = false;
    orden.forEach(function(cat){
      const items = porCategoria[cat].filter(function(p){
        if (modo === "faltantes" && !faltantesIds.has(p.id)) return false;
        if (filtro && p.name.toLowerCase().indexOf(filtro) === -1) return false;
        return true;
      });
      if (items.length === 0) return;
      hay = true;
      const h2 = document.createElement("h2");
      h2.textContent = cat + " (" + items.length + ")";
      h2.className = cat === "Sin categoria" ? "sin-categoria" : "";
      contenedor.appendChild(h2);
      items.forEach(function(p){
        const card = document.createElement("div");
        card.className = "tarjeta" + (p.marcada ? " tachada" : "");
        const stock = p.stock || 0;
        const falta = faltantesIds.has(p.id);
        const sello = document.createElement("span");
        sello.className = "sello";
        if (stock <= 0){
          sello.className += " agotado";
          sello.textContent = "AGOTADO";
        } else if (falta){
          sello.className += " poco";
          sello.textContent = "QUEDA POCO";
        }
        const comprar = document.createElement("span");
        comprar.className = "comprar";
        comprar.textContent = falta ? "Comprar" : "";
        const nombreEl = document.createElement("div");
        nombreEl.className = "nombre";
        nombreEl.textContent = p.name;
        const stockEl = document.createElement("div");
        stockEl.className = "stock";
        stockEl.textContent = "Quedan " + stock + " (min " + p.min_stock + ")";
        card.appendChild(sello);
        card.appendChild(comprar);
        card.appendChild(nombreEl);
        card.appendChild(stockEl);
        card.onclick = function(){
          p.marcada = !p.marcada;
          card.className = "tarjeta" + (p.marcada ? " tachada" : "");
        };
        contenedor.appendChild(card);
      });
    });
    document.getElementById("vacio").style.display = hay ? "none" : "block";
  }

  function mostrarSinConexion(msg){
    const banda = document.getElementById("banda");
    const fecha = document.getElementById("fecha-copia");
    banda.style.display = "block";
    if (msg) fecha.textContent = "· " + msg;
    else fecha.textContent = "";
  }

  function ocultarSinConexion(){
    document.getElementById("banda").style.display = "none";
  }

  async function cargar(){
    const clave = obtenerClave();
    try {
      const resp = await fetch("/api/inventory", { headers: { "X-Inventory-Key": clave } });
      if (!resp.ok){
        throw new Error("status " + resp.status);
      }
      const data = await resp.json();
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      ocultarSinConexion();
      dibujar(data);
      return;
    } catch (e){
      // fallo de red o 401
    }
    const copia = localStorage.getItem(STORAGE_KEY);
    if (copia){
      try {
        const data = JSON.parse(copia);
        dibujar(data);
        mostrarSinConexion("Datos del " + fechaHora(data.generated_at));
      } catch (e2){
        document.getElementById("vacio").style.display = "block";
      }
    } else {
      document.getElementById("vacio").style.display = "block";
      mostrarSinConexion(null);
    }
  }

  document.getElementById("buscador").addEventListener("input", function(){
    const copia = localStorage.getItem(STORAGE_KEY);
    if (copia){
      try { dibujar(JSON.parse(copia)); } catch(e){}
    }
  });
  document.getElementById("modo").addEventListener("change", function(){
    const copia = localStorage.getItem(STORAGE_KEY);
    if (copia){
      try { dibujar(JSON.parse(copia)); } catch(e){}
    }
  });

  window.addEventListener("load", cargar);
})();
</script>
</body>
</html>
"""

# Expone la funcion del core para que tests la puedan importar sin acoplarse al nombre del modulo.
inventory_snapshot = ps.inventory_snapshot
