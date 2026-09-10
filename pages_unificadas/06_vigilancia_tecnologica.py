from pathlib import Path

from shell.module_loader import run_isolated

APP_ROOT = Path(__file__).resolve().parents[1] / "vigilancia-tecnologica"

run_isolated(APP_ROOT, package="app", entry_module="app.dashboard", entry_func="main")
