import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

def build_lista_compras_pdf(items, business_name, generado_el, path):
    """
    Genera un PDF A4 con la lista de productos faltantes.
    Items: lista de dicts con name, stock, sugerido, agotado.
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    
    def _s(text):
        """Sanitiza para latin-1 (fpdf2 default fonts)."""
        return str(text).encode("latin-1", "replace").decode("latin-1")

    # Titulo
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _s("Lista de compras"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    
    # Negocio
    if business_name:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _s(business_name), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    
    # Fecha
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _s(f"Generado el {generado_el}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(5)

    # Lista
    for item in items:
        # Una linea por producto: Nombre (bold) - quedan X - comprar Y - MARCA
        name = _s(item['name'])
        q = item['stock']
        s = item['sugerido']
        txt_sugerido = f"comprar {s}" if s is not None else "comprar: a criterio"
        marca = "AGOTADO" if item['agotado'] else "QUEDA POCO"
        
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(pdf.get_string_width(name) + 2, 8, name)
        
        pdf.set_font("Helvetica", "", 11)
        detalles = f" - quedan {q} - {txt_sugerido} - "
        pdf.cell(pdf.get_string_width(_s(detalles)), 8, _s(detalles))
        
        # Color segun estado
        if item['agotado']:
            pdf.set_text_color(200, 0, 0)
        else:
            pdf.set_text_color(185, 125, 10) # Ambar #b97d0a
            
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, _s(marca), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0) # Reset

    pdf.output(path)
    return path
