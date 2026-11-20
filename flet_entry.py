"""Punto de entrada de la app Flet empaquetada (`flet build windows`).

`flet build` busca <modulo>.py en la raiz de la app, y el main.py de la raiz
es el de la app Qt. Este archivo solo arranca flet_app/main.py: no cambia
ninguna logica.
"""

import flet as ft

from flet_app.main import main

ft.run(main)
