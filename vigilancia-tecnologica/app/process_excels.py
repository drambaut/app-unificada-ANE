"""Extracción de texto plano desde libros de Excel."""

from pathlib import Path

import pandas as pd


def _sheet_to_text(dataframe: pd.DataFrame) -> str:
    """Representa una hoja como texto tabulado, conservando sus encabezados."""
    if dataframe.empty and len(dataframe.columns) == 0:
        return ""

    clean_dataframe = dataframe.fillna("")
    return clean_dataframe.to_csv(index=False, sep="\t", lineterminator="\n").strip()


def extract_text_from_excel(excel_path: Path) -> list[dict]:
    """Lee todas las hojas de un Excel y devuelve un resultado por hoja.

    Si el libro no se puede abrir, devuelve un único resultado de error. Esto
    permite registrar el fallo sin detener el resto del procesamiento.
    """
    excel_path = Path(excel_path)

    try:
        sheets = pd.read_excel(excel_path, sheet_name=None)
        results: list[dict] = []

        for sheet_name, dataframe in sheets.items():
            try:
                text = _sheet_to_text(dataframe)
                results.append(
                    {
                        "sheet_name": str(sheet_name),
                        "text": text,
                        "num_chars": len(text),
                        "status": "ok" if text else "empty_text",
                        "error_message": "",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "sheet_name": str(sheet_name),
                        "text": "",
                        "num_chars": 0,
                        "status": "error",
                        "error_message": f"{type(exc).__name__}: {exc}",
                    }
                )

        if results:
            return results

        return [
            {
                "sheet_name": "",
                "text": "",
                "num_chars": 0,
                "status": "empty_text",
                "error_message": "",
            }
        ]
    except Exception as exc:
        return [
            {
                "sheet_name": "",
                "text": "",
                "num_chars": 0,
                "status": "error",
                "error_message": f"{type(exc).__name__}: {exc}",
            }
        ]
