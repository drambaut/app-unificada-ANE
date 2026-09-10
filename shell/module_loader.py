"""Aisla la carga de sub-apps que usan paquetes de primer nivel con el mismo
nombre (por ejemplo, `app` en observatorio-espectro y vigilancia-tecnologica,
o `src` en hoja-ruta y separacion-informacion; y también el módulo suelto
`app.py` de hoja-ruta, que comparte el nombre "app" con esos paquetes).

Antes de importar la sub-app activa se purga `sys.modules` para esos nombres
y se inserta la raíz de esa sub-app en `sys.path`. Como Streamlit re-ejecuta
el script completo en cada interacción, esto fuerza una importación fresca
en cada rerun sin necesidad de tocar el código interno de cada sub-app.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

# Nombres de primer nivel que distintas sub-apps reutilizan y que por lo
# tanto deben purgarse de sys.modules antes de cada carga, sin importar cuál
# de ellos use la app activa.
_COLLIDING_NAMES = ("app", "src")


def _purge(prefix: str) -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            del sys.modules[name]


def _purge_all(extra: Sequence[str] = ()) -> None:
    for prefix in (*_COLLIDING_NAMES, *extra):
        _purge(prefix)


def run_isolated(
    app_root: Path,
    package: str,
    entry_module: str,
    entry_func: Optional[str] = None,
    entry_args: tuple = (),
) -> None:
    """Ejecuta el entrypoint de una sub-app en aislamiento de módulos.

    - app_root: carpeta raíz de la sub-app (se agrega temporalmente a sys.path).
    - package: nombre del paquete de primer nivel de esta sub-app (ej. "app" o "src").
    - entry_module: módulo a importar, ej. "app.main" o "app.dashboard".
    - entry_func: si se indica, se llama explícitamente tras importar
      (necesario cuando la sub-app guarda su lógica detrás de
      `if __name__ == "__main__":`, que no se dispara al importar).
    """
    app_root_str = str(app_root)
    _purge_all(extra=(package,))
    sys.path.insert(0, app_root_str)
    try:
        module = importlib.import_module(entry_module)
        if entry_func is not None:
            func: Callable = getattr(module, entry_func)
            func(*entry_args)
    finally:
        try:
            sys.path.remove(app_root_str)
        except ValueError:
            pass


def run_isolated_from_path(
    script_path: Path,
    module_name: str,
    entry_func: Optional[str] = None,
    entry_args: tuple = (),
) -> None:
    """Como run_isolated, pero para scripts sueltos (sin __init__.py) que se
    cargan por ruta de archivo en vez de por nombre de paquete importable.
    El propio script puede seguir haciendo su propio sys.path.append interno.
    """
    _purge_all(extra=(module_name,))
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if entry_func is not None:
        func: Callable = getattr(module, entry_func)
        func(*entry_args)
