from collections.abc import Iterable
from pathlib import Path
import re
import unicodedata

import pandas as pd
import streamlit as st


def remove_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def clean_column_name(value: object) -> str:
    text = remove_accents(str(value).strip().lower())
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def clean_column_names(columns: Iterable[object]) -> list[str]:
    return [clean_column_name(column) for column in columns]


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def show_dataframe(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.info("No hay datos para mostrar.")
        return
    st.dataframe(df, use_container_width=True)
