import sys
from pathlib import Path

from shell.module_loader import run_isolated_from_path

APP_ROOT = Path(__file__).resolve().parents[1] / "observatorio-espectro"

# El propio script hace sys.path.append(ROOT_DIR) internamente y nunca lo
# quita, así que lo limpiamos aquí después de ejecutarlo para que no quede
# pegado en sys.path y confunda al paquete "app" de otras sub-apps
# (analisis-comentarios, chatbot-pqrs, vigilancia-tecnologica).
try:
    run_isolated_from_path(
        APP_ROOT / "scripts" / "dashboard.py",
        module_name="observatorio_dashboard",
        entry_func="main",
    )
finally:
    app_root_str = str(APP_ROOT)
    while app_root_str in sys.path:
        sys.path.remove(app_root_str)
