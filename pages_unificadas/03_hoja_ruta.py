from pathlib import Path
import sys

from shell.module_loader import run_isolated_from_path

APP_ROOT = Path(__file__).resolve().parents[1] / "hoja-ruta"

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
try:
    run_isolated_from_path(APP_ROOT / "app.py", module_name="app", entry_func="main")
finally:
    try:
        sys.path.remove(str(APP_ROOT))
    except ValueError:
        pass
