"""Mi POS - Pagina de inventario para el telefono (Fase I).

Solo lectura: el telefono pide GET /api/inventory con la clave de inventario
(X-Inventory-Key) y muestra los datos. La pagina se sirve desde
/api/inventario sin autenticacion (no trae datos: los pide con la clave).
Incluye lista de supermercado con marcas persistentes y selector Todo / Faltantes.
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
  .tip-banner { background: #e8f4fd; color: #1d6fa5; padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; font-size: 14px; border-bottom: 1px solid #d0e8fc; }
  .tip-banner button { background: none; border: none; font-size: 18px; cursor: pointer; color: #1d6fa5; font-weight: bold; }
  .barra { padding: 14px 16px; background: #1c2833; color: #fff; font-size: 14px; }
  .barra h1 { margin: 0 0 4px 0; font-size: 20px; font-weight: 700; }
  .barra .sub { font-size: 13px; opacity: 0.9; }
  .sinconexion { background: #fff3cd; color: #856404; padding: 8px 16px; font-size: 13px; border-bottom: 1px solid #ffeeba; }
  .controles { padding: 12px 16px; background: #fff; border-bottom: 1px solid #e2e6ea; }
  .buscador input { width: 100%; padding: 12px 14px; font-size: 17px; border: 1px solid #d0d6dd; border-radius: 10px; background: #fafbfc; color: #1c2833; outline: none; }
  .buscador input:focus { border-color: #6c3483; }
  .selector-botones { display: flex; gap: 8px; padding: 12px 16px; background: #fff; border-bottom: 1px solid #e2e6ea; }
  .btn-modo { flex: 1; padding: 10px; font-size: 15px; font-weight: 700; border: 1px solid #d0d6dd; border-radius: 8px; background: #fff; color: #1c2833; cursor: pointer; text-align: center; }
  .btn-modo.activo { background: #6c3483; color: #fff; border-color: #6c3483; }
  .grupo { padding: 0 16px 8px 16px; }
  .grupo h2 { margin: 12px 0 8px 0; font-size: 16px; color: #6c3483; font-weight: 700; border-bottom: 2px solid #e2e6ea; padding-bottom: 4px; }
  .grupo.sin-categoria h2 { color: #8a8f98; }
  .tarjeta { display: flex; align-items: flex-start; gap: 12px; background: #fff; border: 1px solid #e2e6ea; border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; cursor: pointer; user-select: none; }
  .tarjeta.tachada { opacity: 0.55; }
  .tarjeta.tachada .nombre { text-decoration: line-through; }
  .chk { width: 32px; height: 32px; border: 2px solid #d0d6dd; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 18px; background: #fafbfc; color: #fff; }
  .tarjeta.tachada .chk { background: #27ae60; border-color: #27ae60; }
  .tarjeta .info { flex: 1; min-width: 0; }
  .tarjeta .nombre { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
  .tarjeta .stock { font-size: 15px; font-weight: 700; color: #c0392b; margin-bottom: 4px; }
  .sello { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-right: 6px; }
  .sello.agotado { background: #c0392b; color: #fff; }
  .sello.poco { background: #e67e22; color: #fff; }
  .comprar { color: #27ae60; font-weight: 700; font-size: 14px; margin-left: 6px; }
  .vacio { padding: 32px 16px; text-align: center; color: #6c757d; font-size: 16px; }
  .acciones-comprados { padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; }
  .btn-desmarcar { background: #e74c3c; color: #fff; border: none; padding: 8px 14px; border-radius: 8px; font-weight: 700; cursor: pointer; font-size: 14px; }
</style>
</head>
<body>
  <div class="tip-banner" id="tip-banner" style="display:none">
    <span>Tip: agrega esta página a tu pantalla de inicio para abrirla con un toque.</span>
    <button id="cerrar-tip">×</button>
  </div>
  <div class="barra">
    <h1 id="nombre-negocio">Inventario</h1>
    <div class="sub" id="actualizado">Actualizado --:--</div>
  </div>
  <div class="sinconexion" id="banda" style="display:none">Sin conexion <span id="fecha-copia"></span></div>
  <div class="controles">
    <div class="buscador"><input type="search" id="buscador" placeholder="Buscar producto..."></div>
  </div>
  <div class="selector-botones">
    <button id="btn-todo" class="btn-modo activo">Todo</button>
    <button id="btn-faltantes" class="btn-modo">Solo lo que falta</button>
  </div>
  <div id="contenedor"></div>
  <div id="contenedor-comprados"></div>
  <div id="vacio" class="vacio" style="display:none">No hay productos para mostrar.</div>
<script>
(function(){
  const STORAGE_KEY = "mipos_inv_data";
  const KEY_STORAGE = "mipos_inv_key";
  const CHECKED_KEY = "mipos_inv_checked";
  const TIP_CLOSED_KEY = "mipos_tip_closed";

  let modoActual = "todos"; // por defecto Todo

  // Tip banner
  if (!localStorage.getItem(TIP_CLOSED_KEY)) {
    document.getElementById("tip-banner").style.display = "flex";
  }
  document.getElementById("cerrar-tip").onclick = function(){
    localStorage.setItem(TIP_CLOSED_KEY, "1");
    document.getElementById("tip-banner").style.display = "none";
  };

  function obtenerClave(){
    const url = new URL(window.location.href);
    const desdeUrl = url.searchParams.get("clave");
    if (desdeUrl){
      localStorage.setItem(KEY_STORAGE, desdeUrl);
      return desdeUrl;
    }
    return localStorage.getItem(KEY_STORAGE) || "";
  }

  function obtenerMarcados(){
    try {
      const raw = localStorage.getItem(CHECKED_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch(e){
      return [];
    }
  }

  function guardarMarcados(ids){
    localStorage.setItem(CHECKED_KEY, JSON.stringify(ids));
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

    const marcadosList = obtenerMarcados();
    const marcadosSet = new Set(marcadosList);

    const filtro = (document.getElementById("buscador").value || "").toLowerCase();

    // Separar comprados vs no comprados
    const noComprados = [];
    const comprados = [];

    productos.forEach(function(p){
      if (filtro && p.name.toLowerCase().indexOf(filtro) === -1) return;
      if (modoActual === "faltantes" && !faltantesIds.has(p.id)) return;

      if (marcadosSet.has(p.id)) {
        comprados.push(p);
      } else {
        noComprados.push(p);
      }
    });

    const contenedor = document.getElementById("contenedor");
    contenedor.innerHTML = "";
    let hay = false;

    // Agrupar no comprados por categoria
    const porCategoria = {};
    noComprados.forEach(function(p){
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

    orden.forEach(function(cat){
      const items = porCategoria[cat];
      if (items.length === 0) return;
      hay = true;
      const divGrupo = document.createElement("div");
      divGrupo.className = "grupo" + (cat === "Sin categoria" ? " sin-categoria" : "");
      const h2 = document.createElement("h2");
      h2.textContent = cat + " (" + items.length + ")";
      divGrupo.appendChild(h2);

      items.forEach(function(p){
        const card = document.createElement("div");
        card.className = "tarjeta";

        const chk = document.createElement("div");
        chk.className = "chk";
        chk.textContent = "✓";

        const info = document.createElement("div");
        info.className = "info";

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

        info.appendChild(sello);
        info.appendChild(comprar);
        info.appendChild(nombreEl);
        info.appendChild(stockEl);

        card.appendChild(chk);
        card.appendChild(info);

        card.onclick = function(){
          toggleMarcar(p.id);
        };
        divGrupo.appendChild(card);
      });
      contenedor.appendChild(divGrupo);
    });

    // Contenedor comprados
    const contenedorComprados = document.getElementById("contenedor-comprados");
    contenedorComprados.innerHTML = "";
    if (comprados.length > 0) {
      hay = true;
      const divComprados = document.createElement("div");
      divComprados.className = "grupo";

      const headerRow = document.createElement("div");
      headerRow.className = "acciones-comprados";
      const h2 = document.createElement("h2");
      h2.style.margin = "0";
      h2.style.border = "none";
      h2.textContent = "Comprados (" + comprados.length + ")";
      headerRow.appendChild(h2);

      const btnDesmarcar = document.createElement("button");
      btnDesmarcar.className = "btn-desmarcar";
      btnDesmarcar.textContent = "Desmarcar todos";
      btnDesmarcar.onclick = function(){
        if (confirm("¿Desmarcar todos los productos comprados?")) {
          guardarMarcados([]);
          const copia = localStorage.getItem(STORAGE_KEY);
          if (copia) { try { dibujar(JSON.parse(copia)); } catch(e){} }
        }
      };
      headerRow.appendChild(btnDesmarcar);
      divComprados.appendChild(headerRow);

      comprados.forEach(function(p){
        const card = document.createElement("div");
        card.className = "tarjeta tachada";

        const chk = document.createElement("div");
        chk.className = "chk";
        chk.textContent = "✓";

        const info = document.createElement("div");
        info.className = "info";

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

        info.appendChild(sello);
        info.appendChild(comprar);
        info.appendChild(nombreEl);
        info.appendChild(stockEl);

        card.appendChild(chk);
        card.appendChild(info);

        card.onclick = function(){
          toggleMarcar(p.id);
        };
        divComprados.appendChild(card);
      });
      contenedorComprados.appendChild(divComprados);
    }

    document.getElementById("vacio").style.display = hay ? "none" : "block";
  }

  function toggleMarcar(id){
    const marcados = obtenerMarcados();
    const set = new Set(marcados);
    if (set.has(id)) {
      set.delete(id);
    } else {
      set.add(id);
    }
    guardarMarcados(Array.from(set));
    const copia = localStorage.getItem(STORAGE_KEY);
    if (copia){
      try { dibujar(JSON.parse(copia)); } catch(e){}
    }
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

  document.getElementById("btn-todo").onclick = function(){
    modoActual = "todos";
    document.getElementById("btn-todo").className = "btn-modo activo";
    document.getElementById("btn-faltantes").className = "btn-modo";
    const copia = localStorage.getItem(STORAGE_KEY);
    if (copia){ try { dibujar(JSON.parse(copia)); } catch(e){} }
  };

  document.getElementById("btn-faltantes").onclick = function(){
    modoActual = "faltantes";
    document.getElementById("btn-faltantes").className = "btn-modo activo";
    document.getElementById("btn-todo").className = "btn-modo";
    const copia = localStorage.getItem(STORAGE_KEY);
    if (copia){ try { dibujar(JSON.parse(copia)); } catch(e){} }
  };

  window.addEventListener("load", cargar);
})();
</script>
</body>
</html>
"""

# Expone la funcion del core para que tests la puedan importar sin acoplarse al nombre del modulo.
inventory_snapshot = ps.inventory_snapshot
