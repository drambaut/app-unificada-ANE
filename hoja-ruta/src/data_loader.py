from pathlib import Path
import tempfile

import pandas as pd
import streamlit as st


def file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def show_missing_file_error(path: Path) -> None:
    st.error(f"Archivo no encontrado: {path}")


def load_excel(path: Path) -> pd.DataFrame:
    if not file_exists(path):
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    return pd.read_excel(path)


def load_csv(path: Path) -> pd.DataFrame:
    if not file_exists(path):
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    errors: list[str] = []
    for encoding in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, encoding=encoding, sep=None, engine="python")
        except Exception as exc:
            errors.append(f"{encoding}: {exc}")

    raise ValueError(
        "No fue posible leer el CSV. Intentos realizados: " + " | ".join(errors)
    )


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def save_csv_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)
        df.to_csv(tmp_file, index=False)

    tmp_path.replace(path)
