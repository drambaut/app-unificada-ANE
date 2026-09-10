"""Preparacion tecnica de libros Excel."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.documents.models import DocumentChunk
from app.preparation.errors import DocumentPreparationError
from app.preparation.text_cleaning import clean_chunk_text


class ExcelDocumentPreparer:
    """Convierte hojas y filas de Excel en chunks estructurados."""

    def prepare(
        self,
        *,
        document_id: str,
        file_name: str,
        content: bytes,
    ) -> list[DocumentChunk]:
        extension = Path(file_name).suffix.lower()
        engine = "xlrd" if extension == ".xls" else "openpyxl"
        try:
            sheets = pd.read_excel(
                BytesIO(content),
                sheet_name=None,
                dtype=object,
                engine=engine,
            )
        except Exception as exc:
            raise DocumentPreparationError(
                f"No se pudo leer el Excel {file_name}: {type(exc).__name__}: {exc}"
            ) from exc

        chunks: list[DocumentChunk] = []
        position = 1
        for sheet_name, dataframe in sheets.items():
            clean_dataframe = dataframe.fillna("")
            columns = [str(column) for column in clean_dataframe.columns]

            if clean_dataframe.empty:
                text = f"sheet={sheet_name}\ncolumns={columns}\nrow="
                chunks.append(
                    self._chunk(
                        document_id=document_id,
                        text=text,
                        sheet_name=str(sheet_name),
                        row_reference="empty",
                        position=position,
                    )
                )
                position += 1
                continue

            for row_index, row in clean_dataframe.iterrows():
                values = [
                    f"{column}={row[column]!s}"
                    for column in clean_dataframe.columns
                ]
                text = (
                    f"sheet={sheet_name}\n"
                    f"columns={columns}\n"
                    f"row={'; '.join(values)}"
                )
                chunks.append(
                    self._chunk(
                        document_id=document_id,
                        text=text,
                        sheet_name=str(sheet_name),
                        row_reference=str(int(row_index) + 2),
                        position=position,
                    )
                )
                position += 1
        return chunks

    def _chunk(
        self,
        *,
        document_id: str,
        text: str,
        sheet_name: str,
        row_reference: str,
        position: int,
    ) -> DocumentChunk:
        cleaned_text = clean_chunk_text(text)
        return DocumentChunk(
            id=str(uuid4()),
            document_id=document_id,
            content=cleaned_text,
            page_number=None,
            section_title=None,
            sheet_name=sheet_name,
            row_reference=row_reference,
            content_hash=hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest(),
            position=position,
        )
