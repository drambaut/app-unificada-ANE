from pathlib import Path

from shell.module_loader import run_isolated

APP_ROOT = Path(__file__).resolve().parents[1] / "separacion-informacion"

run_isolated(APP_ROOT, package="src", entry_module="app", entry_func="main")
