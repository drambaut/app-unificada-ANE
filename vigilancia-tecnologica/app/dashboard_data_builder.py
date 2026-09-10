"""Construye CSV procesados y publicables para el dashboard de demo, sin LLM."""
from __future__ import annotations
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any
import pandas as pd

try:
    from app.config import PROJECT_ROOT, STRUCTURED_DATA_DIR
    from app.topic_taxonomy import infer_regulatory_subtopic, infer_tema_estrategico, infer_tipo_evento_regulatorio, map_tema_to_linea_pmge, normalize_bands, normalize_technologies, parse_list_field, regulatory_profile
except ModuleNotFoundError:  # Ejecución directa: python app/dashboard_data_builder.py
    from config import PROJECT_ROOT, STRUCTURED_DATA_DIR
    from topic_taxonomy import infer_regulatory_subtopic, infer_tema_estrategico, infer_tipo_evento_regulatorio, map_tema_to_linea_pmge, normalize_bands, normalize_technologies, parse_list_field, regulatory_profile

LOGGER = logging.getLogger(__name__)
INPUT_CSV = STRUCTURED_DATA_DIR / "structured_documents.csv"
DEMO_DATA_DIR = PROJECT_ROOT / "demo_data"
REFERENCE_DATA_DIR = PROJECT_ROOT / "data" / "reference"
POLICY_ACTIVITY_COLUMNS = ["activity_id", "policy_name", "instrument_name", "policy_axis", "activity_name", "activity_description", "responsible_area", "execution_period", "keywords"]
PMGE_PROJECT_COLUMNS = ["project_id", "source_document", "pmge_line", "project_name", "project_description", "expected_output", "timeframe", "keywords"]
DOCUMENT_POLICY_ALIGNMENT_COLUMNS = ["alignment_id", "trend_name", "topic_macro", "support_documents", "support_sources", "policy_activity_id", "policy_name", "policy_activity_name", "coverage_status", "documentary_evidence", "recommendation", "opportunity_score", "score_label"]
PMGE_POLICY_ALIGNMENT_COLUMNS = ["alignment_id", "project_id", "source_document", "pmge_line", "project_name", "policy_activity_id", "policy_name", "policy_activity_name", "alignment_level", "observation", "suggested_action", "alignment_score", "score_label"]
OUTPUT_NAMES = ["dashboard_records.csv", "dashboard_signals.csv", "dashboard_temas_counts.csv", "dashboard_relevancia_counts.csv", "dashboard_tipo_insumo_counts.csv", "dashboard_tecnologias_counts.csv", "dashboard_bandas_counts.csv", "dashboard_tema_fuente_matrix.csv", "dashboard_tema_tecnologia_matrix.csv", "dashboard_banda_tecnologia_matrix.csv", "dashboard_tema_tipo_insumo_matrix.csv", "dashboard_tema_relevancia_matrix.csv", "dashboard_regulatory_map.csv", "dashboard_regulatory_trends.csv", "policy_matrix_activities.csv", "pmge_projects.csv", "dashboard_document_policy_alignment.csv", "dashboard_pmge_policy_alignment.csv"]
INTERNATIONAL_SOURCES = ("cullen international", "policytracker", "gsma", "worldbank", "world bank", "reguladores", "uit", "citel", "itu")
ALLOWED_COVERAGE_STATUS = ("Alta relación", "Parcial", "Brecha", "S/E")
ALLOWED_ALIGNMENT_LEVEL = ("Alta", "Parcial", "Débil", "S/E")
SEMANTIC_GROUPS = {
    "6 GHz Wi-Fi uso libre": ("6 ghz", "wi-fi", "wifi", "uso libre", "no licenciado", "unlicensed"),
    "IMT 5G bandas": ("imt", "5g", "5g-advanced", "bandas bajas", "bandas medias", "bandas altas", "3.5 ghz", "700 mhz", "26 ghz"),
    "Satelital NTN D2D": ("satelital", "satélite", "satellite", "d2d", "ntn", "leo", "mss", "ngso"),
    "Compartición flexible": ("sharing", "compartición", "comparticion", "flexible", "mercado secundario", "uso compartido", "dinámico"),
    "Redes privadas": ("redes privadas", "verticales industriales", "industriales", "local 5g", "npn"),
    "Datos IA gobernanza": ("datos", "ia", "analítica", "analitica", "modernización digital", "gobernanza", "digital"),
    "Vigilancia control": ("vigilancia", "control", "supervisión", "supervision", "riesgos", "interferencia"),
    "Internacional": ("uit", "citel", "cmr", "wrc", "internacional", "armonización", "armonizacion"),
}

def _text(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value).strip()

def _is_international_source(value: Any) -> bool:
    source = str(value or "").casefold()
    return any(name in source for name in INTERNATIONAL_SOURCES)

def calculate_relevance_score(row: pd.Series) -> tuple[int, str]:
    """Calcula relevancia 0–10 según las reglas explícitas del MVP."""
    score = {"alta": 4, "media": 2, "baja": 1}.get(_text(row, "relevancia_agenda_ane").casefold(), 0)
    score += 2 if _text(row, "linea_pmge") else 0
    score += 1 if parse_list_field(row.get("tecnologias", [])) else 0
    score += 1 if parse_list_field(row.get("bandas_frecuencia", [])) else 0
    score += 1 if _is_international_source(row.get("source_folder", "")) else 0
    score += 1 if _text(row, "tipo_insumo_agenda") != "No prioritario" else 0
    score = min(score, 10)
    return score, "Baja" if score <= 3 else "Media" if score <= 6 else "Alta"

def calculate_activity_score(row: pd.Series) -> int:
    """Calcula actividad internacional 0–3."""
    return min(3, sum([_is_international_source(row.get("source_folder", "")), bool(parse_list_field(row.get("paises_regiones", []))), bool(parse_list_field(row.get("organizaciones", [])) or parse_list_field(row.get("actores", [])))]))

def _infer_input_type(relevance: str, topic: str) -> str:
    """Regla simple: baja→no prioritario; media→seguimiento; alta→insumo por tema."""
    relevance = relevance.casefold()
    if relevance == "baja": return "No prioritario"
    if relevance == "media": return "Seguimiento"
    if relevance == "alta":
        if topic == "Spectrum sharing y mecanismos flexibles": return "Nueva iniciativa"
        if topic == "Conectividad satelital, NTN y D2D": return "Nota técnica"
        if topic == "Disponibilidad de espectro para IMT": return "Ajuste a iniciativa existente"
    return "Seguimiento"

def _extract_year(value: Any) -> str:
    """Extrae un anio plausible (2000-2029) de una fecha o texto libre."""
    match = re.search(r"\b(20[0-2][0-9])\b", str(value or ""))
    return match.group(1) if match else ""


def _make_record(row: pd.Series) -> dict[str, Any]:
    technologies = normalize_technologies(row.get("tecnologias", []))
    bands = normalize_bands(row.get("bandas_frecuencia", []))
    main = _text(row, "tema_principal")
    keywords = parse_list_field(row.get("palabras_clave", []))
    signal = main or ", ".join(keywords) or _text(row, "file_name")
    topic = infer_tema_estrategico(technologies, bands, signal, main, _text(row, "resumen"))
    line = map_tema_to_linea_pmge(topic)
    input_type = _infer_input_type(_text(row, "relevancia_agenda_ane"), topic)
    evidence = [topic]
    if technologies: evidence.append("tecnologías: " + ", ".join(technologies[:4]))
    if bands: evidence.append("bandas: " + ", ".join(bands[:4]))
    year = _extract_year(row.get("document_date", "")) or _extract_year(_text(row, "file_name"))
    record: dict[str, Any] = {
        "document_id": _text(row, "document_id"), "file_name": _text(row, "file_name"), "source_folder": _text(row, "source_folder"), "file_type": _text(row, "file_type"),
        "year": year,
        "tema_estrategico": topic, "linea_pmge": line, "senal_regulatoria": signal, "tecnologias": technologies, "bandas_frecuencia": bands,
        "paises_regiones": parse_list_field(row.get("paises", [])), "organizaciones": parse_list_field(row.get("organizaciones", [])), "actores": parse_list_field(row.get("actores", [])),
        "tipo_evento_regulatorio": infer_tipo_evento_regulatorio(" ".join([signal, _text(row, "resumen"), " ".join(keywords)])), "tipo_insumo_agenda": input_type,
        "relevancia_agenda_ane": _text(row, "relevancia_agenda_ane"), "evidencia_breve": "; ".join(evidence) + ".",
    }
    score, label = calculate_relevance_score(pd.Series(record))
    record.update(relevancia_score=score, relevancia_label=label, actividad_internacional_score=calculate_activity_score(pd.Series(record)))
    record["prioridad_score"] = score + record["actividad_internacional_score"]
    record["justificacion_analitica"] = _text(row, "justificacion_relevancia") or f"El tema {topic} aporta a {line} como insumo de {input_type.lower()}."
    record.pop("relevancia_agenda_ane")
    return record

def _compute_counts(records: pd.DataFrame, column: str, label: str, is_list: bool = False) -> pd.DataFrame:
    values = records[column].map(parse_list_field).explode() if is_list else records[column]
    return values.dropna().loc[lambda s: s.astype(str).str.len() > 0].value_counts().rename_axis(label).reset_index(name="count")

def _write_counts(records: pd.DataFrame, column: str, label: str, path: Path, is_list: bool = False) -> None:
    _compute_counts(records, column, label, is_list).to_csv(path, index=False, encoding="utf-8-sig")

def _compute_matrix(records: pd.DataFrame, row_col: str, col_col: str, row_list: bool = False, col_list: bool = False) -> pd.DataFrame:
    pairs = records[[row_col, col_col]].copy()
    if row_list: pairs = pairs.assign(**{row_col: pairs[row_col].map(parse_list_field)}).explode(row_col)
    if col_list: pairs = pairs.assign(**{col_col: pairs[col_col].map(parse_list_field)}).explode(col_col)
    pairs = pairs.dropna().reset_index(drop=True)
    return pd.crosstab(pairs[row_col], pairs[col_col]).reset_index()

def _write_matrix(records: pd.DataFrame, row_col: str, col_col: str, path: Path, row_list: bool = False, col_list: bool = False) -> None:
    _compute_matrix(records, row_col, col_col, row_list, col_list).to_csv(path, index=False, encoding="utf-8-sig")

def _unique_join(series: pd.Series, lists: bool = False) -> str:
    values: list[str] = []
    for value in series:
        candidates = parse_list_field(value) if lists else [str(value).strip()]
        values.extend(item for item in candidates if item and item not in values)
    return ", ".join(values)

def _build_signals(records: pd.DataFrame) -> pd.DataFrame:
    keys = ["senal_regulatoria", "tema_estrategico", "linea_pmge", "tipo_insumo_agenda", "relevancia_label"]
    signals = records.groupby(keys, dropna=False).agg(num_documentos=("document_id", "nunique"), num_fuentes=("source_folder", "nunique"), fuentes=("source_folder", _unique_join), tecnologias=("tecnologias", lambda s: _unique_join(s, True)), bandas_frecuencia=("bandas_frecuencia", lambda s: _unique_join(s, True)), evidencia=("evidencia_breve", _unique_join), relevancia_score_promedio=("relevancia_score", "mean"), actividad_score_promedio=("actividad_internacional_score", "mean")).reset_index()
    signals["prioridad_score"] = (signals["relevancia_score_promedio"] + signals["actividad_score_promedio"]).round(2)
    return signals.sort_values("prioridad_score", ascending=False)


def _score_label(score: float) -> str:
    return "Baja" if score <= 3 else "Media" if score <= 6 else "Alta"


def _principal_value(frame: pd.DataFrame, column: str) -> str:
    if frame.empty or column not in frame.columns:
        return "Sin datos"
    values = frame[column].fillna("").astype(str).str.strip()
    values = values[values.ne("")]
    return str(values.value_counts().index[0]) if not values.empty else "Sin datos"


def build_regulatory_map(records: pd.DataFrame) -> pd.DataFrame:
    """Agrega la lectura regulatoria a partir de registros procesados (sin LLM)."""
    columns = [
        "tema_macro", "subtema", "debate_regulatorio", "implicacion_regulatoria",
        "tipo_insumo_agenda", "relevancia_label", "relevancia_score_promedio",
        "num_documentos", "num_senales",
    ]
    if records.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for _, row in records.iterrows():
        topic = _text(row, "tema_estrategico") or "Otros temas de seguimiento"
        profile = regulatory_profile(topic)
        rows.append({
            "document_id": _text(row, "document_id"),
            "senal_regulatoria": _text(row, "senal_regulatoria"),
            "tema_macro": topic,
            "subtema": infer_regulatory_subtopic(
                topic, row.get("tecnologias", []), row.get("bandas_frecuencia", []),
                _text(row, "senal_regulatoria"),
            ),
            "debate_regulatorio": profile["debate"],
            "implicacion_regulatoria": profile["implicacion"],
            "tipo_insumo_agenda": _text(row, "tipo_insumo_agenda") or "Seguimiento",
            "relevancia_label": _text(row, "relevancia_label") or "Baja",
            "relevancia_score": pd.to_numeric(row.get("relevancia_score", 0), errors="coerce"),
        })
    working = pd.DataFrame(rows)
    keys = [
        "tema_macro", "subtema", "debate_regulatorio", "implicacion_regulatoria",
        "tipo_insumo_agenda", "relevancia_label",
    ]
    result = working.groupby(keys, dropna=False).agg(
        relevancia_score_promedio=("relevancia_score", "mean"),
        num_documentos=("document_id", "nunique"),
        num_senales=("senal_regulatoria", "nunique"),
    ).reset_index()
    result["relevancia_score_promedio"] = result["relevancia_score_promedio"].fillna(0).round(2)
    return result[columns].sort_values(
        ["num_documentos", "relevancia_score_promedio"], ascending=False
    ).reset_index(drop=True)


def build_regulatory_trends(records: pd.DataFrame) -> pd.DataFrame:
    """Produce exactamente una tendencia explicada por cada tema macro presente."""
    columns = [
        "tema_macro", "nombre_tendencia", "tema_asociado", "de_que_trata",
        "que_esta_pasando", "por_que_importa", "implicacion_regulatoria",
        "relevancia_label", "relevancia_score_promedio", "tipo_insumo_principal",
        "num_documentos", "num_senales",
    ]
    if records.empty:
        return pd.DataFrame(columns=columns)
    document_column = "document_id" if "document_id" in records.columns else "tema_estrategico"
    rows: list[dict[str, Any]] = []
    for topic, group in records.groupby("tema_estrategico", dropna=False):
        topic = str(topic).strip() or "Otros temas de seguimiento"
        profile = regulatory_profile(topic)
        scores = pd.to_numeric(group.get("relevancia_score", pd.Series(index=group.index, dtype=float)), errors="coerce")
        average = float(scores.mean()) if scores.notna().any() else 0.0
        rows.append({
            "tema_macro": topic,
            "nombre_tendencia": profile["nombre"],
            "tema_asociado": topic,
            "de_que_trata": profile["trata"],
            "que_esta_pasando": profile["pasando"],
            "por_que_importa": profile["importa"],
            "implicacion_regulatoria": profile["implicacion"],
            "relevancia_label": _score_label(average),
            "relevancia_score_promedio": round(average, 2),
            "tipo_insumo_principal": _principal_value(group, "tipo_insumo_agenda"),
            "num_documentos": int(group[document_column].nunique()),
            "num_senales": int(group.get("senal_regulatoria", pd.Series(index=group.index, dtype=str)).nunique()),
        })
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["relevancia_score_promedio", "num_documentos"], ascending=False
    ).reset_index(drop=True)


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _normalize_column_name(value: Any) -> str:
    text = str(value or "").casefold().strip()
    replacements = str.maketrans("áéíóúüñ", "aeiouun")
    return re.sub(r"[^a-z0-9]+", " ", text.translate(replacements)).strip()


def _find_reference_file(candidates: list[str], extensions: tuple[str, ...]) -> Path | None:
    if not REFERENCE_DATA_DIR.exists():
        return None
    scored: list[tuple[int, Path]] = []
    for path in REFERENCE_DATA_DIR.iterdir():
        if path.suffix.casefold() not in extensions:
            continue
        name = _normalize_column_name(path.stem)
        score = sum(1 for candidate in candidates if candidate in name)
        if score:
            scored.append((score, path))
    return max(scored, key=lambda item: item[0])[1] if scored else None


def _match_column(columns: list[str], aliases: tuple[str, ...]) -> str | None:
    normalized = {column: _normalize_column_name(column) for column in columns}
    for column, name in normalized.items():
        if name in aliases:
            return column
    for column, name in normalized.items():
        if any(alias in name for alias in aliases):
            return column
    return None


def _row_text(row: pd.Series, columns: list[str]) -> str:
    return " ".join(_text(row, column) for column in columns if column in row.index)


def _semantic_keywords(text: str) -> list[str]:
    folded = _normalize_column_name(text)
    found: list[str] = []
    for label, terms in SEMANTIC_GROUPS.items():
        if any(_normalize_column_name(term) in folded for term in terms):
            found.append(label)
    return found


def _keywords_for_text(text: str) -> str:
    keywords = _semantic_keywords(text)
    if keywords:
        return ", ".join(keywords)
    words = re.findall(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ-]{4,}\b", text, flags=re.UNICODE)
    seen: list[str] = []
    for word in words:
        clean = word.strip(".,;:").lower()
        if clean not in seen:
            seen.append(clean)
        if len(seen) >= 8:
            break
    return ", ".join(seen)


def build_policy_matrix_activities() -> pd.DataFrame:
    """Deriva actividades de politica publica desde el Excel de referencia."""
    path = _find_reference_file(["matriz", "politicas"], (".xlsx", ".xls"))
    if path is None:
        return _empty_frame(POLICY_ACTIVITY_COLUMNS)
    frames: list[pd.DataFrame] = []
    try:
        workbook = pd.ExcelFile(path)
        for sheet_name in workbook.sheet_names:
            frame = pd.read_excel(path, sheet_name=sheet_name, dtype=str).fillna("")
            if not frame.empty:
                frames.append(frame)
    except Exception as exc:  # pragma: no cover - defensivo ante Excels malformados
        LOGGER.warning("No fue posible leer la matriz de politicas %s: %s", path, exc)
        return _empty_frame(POLICY_ACTIVITY_COLUMNS)
    rows: list[dict[str, Any]] = []
    for frame in frames:
        columns = frame.columns.astype(str).tolist()
        policy_col = _match_column(columns, ("politica", "documento"))
        instrument_col = _match_column(columns, ("instrumento", "documento"))
        axis_col = _match_column(columns, ("eje", "linea", "objetivo"))
        activity_col = _match_column(columns, ("actividad", "accion", "accion o actividad"))
        description_col = _match_column(columns, ("descripcion", "objetivo", "justificacion", "alcance"))
        responsible_col = _match_column(columns, ("responsable", "area", "dependencia", "grupo"))
        period_col = _match_column(columns, ("plazo", "periodo", "temporalidad", "ejecucion"))
        if not activity_col:
            continue
        for _, row in frame.iterrows():
            activity = _text(row, activity_col)
            if not activity:
                continue
            policy = _text(row, policy_col or "") or "Matriz de politicas publicas"
            axis = _text(row, axis_col or "")
            description = _text(row, description_col or "") or activity
            rows.append({
                "activity_id": f"ACT-{len(rows) + 1:03d}",
                "policy_name": policy,
                "instrument_name": _text(row, instrument_col or "") or policy,
                "policy_axis": axis,
                "activity_name": activity,
                "activity_description": description,
                "responsible_area": _text(row, responsible_col or ""),
                "execution_period": _text(row, period_col or ""),
                "keywords": _keywords_for_text(" ".join([policy, axis, activity, description])),
            })
    return pd.DataFrame(rows, columns=POLICY_ACTIVITY_COLUMNS)


def _pmge_line_for_text(text: str) -> str:
    folded = _normalize_column_name(text)
    if any(term in folded for term in ("satelital", "satellite", "ntn", "d2d")):
        return "Espectro para promover la conectividad satelital"
    if any(term in folded for term in ("imt", "5g", "banda", "espectro")):
        return "Disponibilidad de espectro"
    if any(term in folded for term in ("internacional", "uit", "citel", "cmr", "wrc")):
        return "Gestión internacional del espectro"
    if any(term in folded for term in ("innovacion", "comparticion", "uso eficiente", "datos", "ia", "vigilancia")):
        return "Innovación en la gestión y uso del espectro"
    return "Necesidades transversales para la gestión del espectro"


def build_pmge_projects() -> pd.DataFrame:
    """Deriva proyectos PMGE; prefiere CSV manual y usa PDF solo si hay bloques claros."""
    manual = REFERENCE_DATA_DIR / "pmge_projects_manual.csv"
    if manual.exists():
        frame = pd.read_csv(manual, dtype=str, keep_default_na=False)
        for column in PMGE_PROJECT_COLUMNS:
            if column not in frame.columns:
                frame[column] = ""
        return frame[PMGE_PROJECT_COLUMNS]
    path = _find_reference_file(["pmge"], (".pdf",))
    if path is None:
        LOGGER.warning("No existe PDF PMGE ni data/reference/pmge_projects_manual.csv; se genera CSV vacio.")
        return _empty_frame(PMGE_PROJECT_COLUMNS)
    try:
        import fitz  # type: ignore
        document = fitz.open(path)
        text = "\n".join(page.get_text() for page in document)
    except Exception as exc:  # pragma: no cover - dependiente de backend PDF
        LOGGER.warning("No fue posible procesar %s: %s", path, exc)
        return _empty_frame(PMGE_PROJECT_COLUMNS)
    pattern = re.compile(
        r"(?:\d+\.\d+\.\d+\s+)?Nombre del proyecto:\s*(?P<name>.+?)(?:\n\s*\n|Alcance y justificación:)\s*(?P<body>.*?)(?=(?:\n\s*\d+\.\d+\.\d+\s+Nombre del proyecto:)|(?:\n\s*3\.2\s+Resumen)|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    rows: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        name = " ".join(match.group("name").split())
        body = " ".join(match.group("body").split())
        if len(name) < 8:
            continue
        timeframe_match = re.search(r"(20\d{2}(?:\s*[-–]\s*20\d{2})?)", body)
        rows.append({
            "project_id": f"PMGE-{len(rows) + 1:03d}",
            "source_document": path.name,
            "pmge_line": _pmge_line_for_text(" ".join([name, body])),
            "project_name": name.rstrip("."),
            "project_description": body[:900],
            "expected_output": "",
            "timeframe": timeframe_match.group(1) if timeframe_match else "",
            "keywords": _keywords_for_text(" ".join([name, body])),
        })
    if not rows:
        LOGGER.warning("No se identificaron bloques de proyectos en %s; se genera CSV vacio.", path)
    return pd.DataFrame(rows, columns=PMGE_PROJECT_COLUMNS)


def _keyword_set(*values: Any) -> set[str]:
    text = _normalize_column_name(" ".join(str(value or "") for value in values))
    terms = set(_semantic_keywords(text))
    terms.update(term for term in re.findall(r"\b[a-z0-9]{4,}\b", text) if term not in {"para", "como", "sobre", "esta", "este", "entre", "desde", "publica", "politica"})
    return terms


def _match_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left.intersection(right)) / max(1, min(len(left), len(right)))


def _score_label_100(score: float) -> str:
    if score >= 75:
        return "Alta"
    if score >= 50:
        return "Media"
    return "Baja"


def _coverage_from_match(match: float) -> str:
    if match >= .34:
        return "Alta relación"
    if match >= .14:
        return "Parcial"
    if match > 0:
        return "Brecha"
    return "S/E"


def _alignment_from_match(match: float) -> str:
    if match >= .34:
        return "Alta"
    if match >= .16:
        return "Parcial"
    if match > 0:
        return "Débil"
    return "S/E"


def _to_100(value: Any) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    numeric = float(numeric)
    return max(0.0, min(100.0, numeric * 10 if numeric <= 10 else numeric))


def _document_year_score(records: pd.DataFrame) -> float:
    if records.empty:
        return 40.0
    text = " ".join(records.get("file_name", pd.Series(dtype=str)).fillna("").astype(str).tolist())
    years = [int(year) for year in re.findall(r"\b(20\d{2})\b", text)]
    year = max(years) if years else 2024
    return 100.0 if year >= 2026 else 80.0 if year == 2025 else 60.0 if year == 2024 else 40.0


def _actionability_score(input_type: Any) -> float:
    value = str(input_type or "").casefold()
    if any(term in value for term in ("nota", "nueva", "ajuste")):
        return 90.0
    if "seguimiento" in value:
        return 60.0
    return 45.0


def _recommendation(coverage: str, relevance: float, evidence: float) -> str:
    if evidence < 25:
        return "Seguimiento"
    if coverage in {"Brecha", "S/E"} and relevance >= 70:
        return "Nueva iniciativa / nota técnica"
    if coverage == "Parcial" and relevance >= 70:
        return "Nota técnica / ajuste a actividad existente"
    if coverage == "Alta relación" and evidence >= 50:
        return "Alimentar lineamiento existente"
    return "Seguimiento"


def build_document_policy_alignment(trends: pd.DataFrame, records: pd.DataFrame, signals: pd.DataFrame, activities: pd.DataFrame) -> pd.DataFrame:
    if trends.empty or activities.empty:
        return _empty_frame(DOCUMENT_POLICY_ALIGNMENT_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, trend in trends.iterrows():
        topic = _text(trend, "tema_macro") or _text(trend, "tema_asociado")
        trend_name = _text(trend, "nombre_tendencia") or topic
        topic_records = records[records.get("tema_estrategico", pd.Series(dtype=str)).fillna("").astype(str) == topic] if "tema_estrategico" in records.columns else pd.DataFrame()
        support_documents = topic_records.get("file_name", pd.Series(dtype=str)).dropna().astype(str).loc[lambda s: s.str.len() > 0].drop_duplicates().head(8).tolist()
        support_sources = topic_records.get("source_folder", pd.Series(dtype=str)).dropna().astype(str).loc[lambda s: s.str.len() > 0].drop_duplicates().head(6).tolist()
        trend_terms = _keyword_set(trend_name, topic, _text(trend, "de_que_trata"), _text(trend, "que_esta_pasando"), _text(trend, "implicacion_regulatoria"))
        candidates: list[tuple[float, pd.Series]] = []
        for _, activity in activities.iterrows():
            activity_terms = _keyword_set(_text(activity, "policy_name"), _text(activity, "policy_axis"), _text(activity, "activity_name"), _text(activity, "activity_description"), _text(activity, "keywords"))
            candidates.append((_match_ratio(trend_terms, activity_terms), activity))
        for match, activity in sorted(candidates, key=lambda item: item[0], reverse=True)[:3]:
            coverage = _coverage_from_match(match)
            relevance = _to_100(trend.get("relevancia_score_promedio", 0))
            evidence = min(100.0, len(support_documents) * 20.0)
            recency = _document_year_score(topic_records)
            gap = max(0.0, (100.0 - match * 100.0) if relevance >= 60 else 45.0)
            actionability = _actionability_score(trend.get("tipo_insumo_principal", ""))
            opportunity = round(.30 * relevance + .25 * gap + .20 * evidence + .15 * recency + .10 * actionability, 2)
            rows.append({
                "alignment_id": f"DOC-POL-{len(rows) + 1:04d}",
                "trend_name": trend_name,
                "topic_macro": topic,
                "support_documents": " | ".join(support_documents),
                "support_sources": " | ".join(support_sources),
                "policy_activity_id": _text(activity, "activity_id"),
                "policy_name": _text(activity, "policy_name"),
                "policy_activity_name": _text(activity, "activity_name"),
                "coverage_status": coverage,
                "documentary_evidence": _text(trend, "que_esta_pasando") or f"{len(support_documents)} documentos asociados al tema {topic}.",
                "recommendation": _recommendation(coverage, relevance, evidence),
                "opportunity_score": max(0.0, min(100.0, opportunity)),
                "score_label": _score_label_100(opportunity),
            })
    return pd.DataFrame(rows, columns=DOCUMENT_POLICY_ALIGNMENT_COLUMNS)


def build_pmge_policy_alignment(projects: pd.DataFrame, activities: pd.DataFrame) -> pd.DataFrame:
    if projects.empty or activities.empty:
        return _empty_frame(PMGE_POLICY_ALIGNMENT_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, project in projects.iterrows():
        project_terms = _keyword_set(_text(project, "pmge_line"), _text(project, "project_name"), _text(project, "project_description"), _text(project, "expected_output"), _text(project, "keywords"))
        candidates: list[tuple[float, pd.Series]] = []
        for _, activity in activities.iterrows():
            activity_terms = _keyword_set(_text(activity, "policy_name"), _text(activity, "policy_axis"), _text(activity, "activity_name"), _text(activity, "activity_description"), _text(activity, "keywords"))
            candidates.append((_match_ratio(project_terms, activity_terms), activity))
        for match, activity in sorted(candidates, key=lambda item: item[0], reverse=True)[:3]:
            temporal = 80.0 if _text(project, "timeframe") and _text(activity, "execution_period") else 60.0
            thematic = match * 100.0
            objectives = 90.0 if _text(project, "pmge_line") and _text(activity, "policy_axis") and _match_ratio(_keyword_set(project.get("pmge_line")), _keyword_set(activity.get("policy_axis"))) > 0 else max(35.0, thematic * .75)
            relation = max(25.0, thematic)
            implementation = 80.0 if _text(activity, "responsible_area") or _text(project, "expected_output") else 55.0
            score = round(.35 * thematic + .25 * objectives + .20 * relation + .10 * temporal + .10 * implementation, 2)
            level = _alignment_from_match(match)
            rows.append({
                "alignment_id": f"PMGE-POL-{len(rows) + 1:04d}",
                "project_id": _text(project, "project_id"),
                "source_document": _text(project, "source_document"),
                "pmge_line": _text(project, "pmge_line"),
                "project_name": _text(project, "project_name"),
                "policy_activity_id": _text(activity, "activity_id"),
                "policy_name": _text(activity, "policy_name"),
                "policy_activity_name": _text(activity, "activity_name"),
                "alignment_level": level,
                "observation": f"Coincidencia semántica por {', '.join(sorted(project_terms.intersection(_keyword_set(activity.get('activity_name'), activity.get('activity_description'), activity.get('keywords'))))[:4]) or 'temas generales de gestión del espectro'}.",
                "suggested_action": "Articular cronograma y entregables" if level in {"Alta", "Parcial"} else "Revisar alcance o mantener seguimiento",
                "alignment_score": max(0.0, min(100.0, score)),
                "score_label": _score_label_100(score),
            })
    return pd.DataFrame(rows, columns=PMGE_POLICY_ALIGNMENT_COLUMNS)


def build_dashboard_data() -> dict[str, Any]:
    if not INPUT_CSV.exists(): raise FileNotFoundError(f"No existe {INPUT_CSV}. Primero ejecute: python app/llm_extract.py")
    source = pd.read_csv(INPUT_CSV, dtype=str, keep_default_na=False)
    return _build_dashboard_data_from_source(source)


def build_dashboard_data_from_supabase(settings: Any | None = None) -> dict[str, Any]:
    """Igual que build_dashboard_data pero lee documentos ya procesados en Supabase.

    No hace llamadas a Gemini: reutiliza document_analysis/pmge_projects/policies
    ya persistidos para documentos con status=processed. La fuente (source_folder)
    se recupera de outputs/corpus_processing_manifest.csv cuando existe.
    """
    from app.core.settings import load_settings

    resolved_settings = settings or load_settings()
    source = _fetch_supabase_surveillance_source(resolved_settings)
    policy_activities = _fetch_supabase_policy_matrix_activities_source(resolved_settings)
    pmge_projects = _fetch_supabase_pmge_projects_source(resolved_settings)
    return _build_dashboard_data_from_source(
        source, policy_activities=policy_activities, pmge_projects=pmge_projects
    )


def build_live_dashboard_data_from_supabase(settings: Any | None = None) -> dict[str, pd.DataFrame]:
    """Igual que build_dashboard_data_from_supabase pero sin escribir a disco.

    Devuelve las mismas tablas (mismas claves que load_demo_data() en
    app/dashboard.py) calculadas en memoria a partir de Supabase. Pensado para
    usarse con @st.cache_data: cada carga de pagina refleja el estado actual de
    Supabase sin depender de archivos commiteados ni de un paso manual de build.
    """
    from app.core.settings import load_settings

    resolved_settings = settings or load_settings()
    source = _fetch_supabase_surveillance_source(resolved_settings)
    policy_activities = _fetch_supabase_policy_matrix_activities_source(resolved_settings)
    pmge_projects = _fetch_supabase_pmge_projects_source(resolved_settings)

    records = pd.DataFrame([_make_record(row) for _, row in source.iterrows()])
    if records.empty:
        empty_keys = [
            "dashboard_records", "dashboard_signals", "dashboard_temas_counts",
            "dashboard_relevancia_counts", "dashboard_tipo_insumo_counts",
            "dashboard_tecnologias_counts", "dashboard_bandas_counts",
            "dashboard_tema_fuente_matrix", "dashboard_tema_tecnologia_matrix",
            "dashboard_banda_tecnologia_matrix", "dashboard_tema_tipo_insumo_matrix",
            "dashboard_tema_relevancia_matrix", "dashboard_regulatory_map",
            "dashboard_regulatory_trends", "policy_matrix_activities", "pmge_projects",
            "dashboard_document_policy_alignment", "dashboard_pmge_policy_alignment",
        ]
        return {key: pd.DataFrame() for key in empty_keys}
    signals = _build_signals(records)
    regulatory_map = build_regulatory_map(records)
    regulatory_trends = build_regulatory_trends(records)
    document_alignment = build_document_policy_alignment(regulatory_trends, records, signals, policy_activities)
    pmge_alignment = build_pmge_policy_alignment(pmge_projects, policy_activities)

    return {
        "dashboard_records": records,
        "dashboard_signals": signals,
        "dashboard_temas_counts": _compute_counts(records, "tema_estrategico", "tema_estrategico"),
        "dashboard_relevancia_counts": _compute_counts(records, "relevancia_label", "relevancia_label"),
        "dashboard_tipo_insumo_counts": _compute_counts(records, "tipo_insumo_agenda", "tipo_insumo_agenda"),
        "dashboard_tecnologias_counts": _compute_counts(records, "tecnologias", "tecnologia", True),
        "dashboard_bandas_counts": _compute_counts(records, "bandas_frecuencia", "banda_frecuencia", True),
        "dashboard_tema_fuente_matrix": _compute_matrix(records, "tema_estrategico", "source_folder"),
        "dashboard_tema_tecnologia_matrix": _compute_matrix(records, "tema_estrategico", "tecnologias", col_list=True),
        "dashboard_banda_tecnologia_matrix": _compute_matrix(records, "bandas_frecuencia", "tecnologias", row_list=True, col_list=True),
        "dashboard_tema_tipo_insumo_matrix": _compute_matrix(records, "tema_estrategico", "tipo_insumo_agenda"),
        "dashboard_tema_relevancia_matrix": _compute_matrix(records, "tema_estrategico", "relevancia_label"),
        "dashboard_regulatory_map": regulatory_map,
        "dashboard_regulatory_trends": regulatory_trends,
        "policy_matrix_activities": policy_activities,
        "pmge_projects": pmge_projects,
        "dashboard_document_policy_alignment": document_alignment,
        "dashboard_pmge_policy_alignment": pmge_alignment,
    }


SOURCE_COLUMNS = [
    "document_id", "file_name", "source_folder", "file_type", "tema_principal",
    "tecnologias", "bandas_frecuencia", "paises", "organizaciones", "actores",
    "palabras_clave", "relevancia_agenda_ane", "resumen", "justificacion_relevancia",
    "document_date",
]
MANIFEST_CSV = PROJECT_ROOT / "outputs" / "corpus_processing_manifest.csv"


def _load_provider_lookup(manifest_path: Path = MANIFEST_CSV) -> dict[str, str]:
    """Mapa file_name -> provider (fuente) desde el manifiesto de corpus."""
    if not manifest_path.exists():
        return {}
    manifest = pd.read_csv(manifest_path, dtype=str, keep_default_na=False)
    if "path" not in manifest.columns or "provider" not in manifest.columns:
        return {}
    lookup: dict[str, str] = {}
    for _, row in manifest.iterrows():
        name = Path(str(row["path"])).name
        if name and name not in lookup:
            lookup[name] = str(row["provider"]).strip()
    return lookup


def _fetch_supabase_surveillance_source(settings: Any | None = None) -> pd.DataFrame:
    """Reconstruye el CSV fuente legacy a partir de document_analysis en Supabase.

    Un documento = una fila (sin importar cuantas hojas/paginas tenia), porque
    el workflow nuevo genera un unico document_analysis por documento.
    """
    from app.core.settings import load_settings
    from app.documents.models import SourceType
    from app.documents.supabase_repository import SupabaseDocumentRepository
    from app.results.supabase_repository import SupabaseResultRepository

    resolved_settings = settings or load_settings()
    documents = SupabaseDocumentRepository(settings=resolved_settings).list_processed_documents()
    surveillance_documents = [
        document for document in documents if document.source_type == SourceType.SURVEILLANCE
    ]
    provider_lookup = _load_provider_lookup()
    results = SupabaseResultRepository(settings=resolved_settings)

    rows: list[dict[str, Any]] = []
    for document in surveillance_documents:
        bundle = results.get_bundle(document.id)
        if bundle is None or bundle.document_analysis is None:
            continue
        analysis = bundle.document_analysis.data
        topics = analysis.get("preliminary_topics") or []
        rows.append({
            "document_id": document.id,
            "file_name": document.file_name,
            "source_folder": document.provider or provider_lookup.get(document.file_name, ""),
            "file_type": document.file_type,
            "tema_principal": topics[0] if topics else analysis.get("title", ""),
            "tecnologias": analysis.get("technologies", []),
            "bandas_frecuencia": analysis.get("frequency_bands", []),
            "paises": analysis.get("countries_regions", []),
            "organizaciones": analysis.get("organizations", []),
            "actores": analysis.get("actors", []),
            "palabras_clave": analysis.get("keywords", []),
            "relevancia_agenda_ane": bundle.document_analysis.confidence or "",
            "resumen": analysis.get("summary", ""),
            "justificacion_relevancia": "",
            "document_date": analysis.get("document_date") or analysis.get("publication_date") or "",
        })
    return pd.DataFrame(rows, columns=SOURCE_COLUMNS)


def _fetch_supabase_pmge_projects_source(settings: Any | None = None) -> pd.DataFrame:
    """PMGE_PROJECT_COLUMNS a partir de pmge_projects ya persistidos en Supabase.

    Reemplaza build_pmge_projects() (que parsea un PDF local por regex) cuando
    el documento institutional_plan ya fue analizado por Gemini y persistido.
    """
    from app.core.settings import load_settings
    from app.documents.models import SourceType
    from app.documents.supabase_repository import SupabaseDocumentRepository
    from app.results.supabase_repository import SupabaseResultRepository

    resolved_settings = settings or load_settings()
    documents = SupabaseDocumentRepository(settings=resolved_settings).list_processed_documents()
    institutional_documents = [
        document for document in documents if document.source_type == SourceType.INSTITUTIONAL_PLAN
    ]
    results = SupabaseResultRepository(settings=resolved_settings)

    rows: list[dict[str, Any]] = []
    for document in institutional_documents:
        bundle = results.get_bundle(document.id)
        if bundle is None:
            continue
        for index, record in enumerate(bundle.pmge_projects, start=1):
            data = record.data
            objectives = data.get("objectives") or []
            activities = data.get("activities") or []
            expected_outputs = data.get("expected_outputs") or []
            description = data.get("description", "")
            project_text = " ".join(
                [data.get("project_name", ""), description, " ".join(objectives), " ".join(activities)]
            )
            rows.append({
                "project_id": f"PMGE-{document.id[:8]}-{index:03d}",
                "source_document": document.file_name,
                "pmge_line": _pmge_line_for_text(project_text),
                "project_name": data.get("project_name", ""),
                "project_description": description,
                "expected_output": "; ".join(expected_outputs),
                "timeframe": data.get("period") or "",
                "keywords": _keywords_for_text(project_text),
            })
    return pd.DataFrame(rows, columns=PMGE_PROJECT_COLUMNS)


def _fetch_supabase_policy_matrix_activities_source(settings: Any | None = None) -> pd.DataFrame:
    """POLICY_ACTIVITY_COLUMNS a partir de policies/policy_activities en Supabase.

    Reemplaza build_policy_matrix_activities() (que lee un Excel local por
    nombre de archivo) cuando el documento policy_matrix ya fue analizado por
    Gemini y persistido. policy_activities enlaza con su policy mediante
    policy_temporary_id, valido solo dentro del mismo documento/bundle.
    """
    from app.core.settings import load_settings
    from app.documents.models import SourceType
    from app.documents.supabase_repository import SupabaseDocumentRepository
    from app.results.supabase_repository import SupabaseResultRepository

    resolved_settings = settings or load_settings()
    documents = SupabaseDocumentRepository(settings=resolved_settings).list_processed_documents()
    policy_matrix_documents = [
        document for document in documents if document.source_type == SourceType.POLICY_MATRIX
    ]
    results = SupabaseResultRepository(settings=resolved_settings)

    rows: list[dict[str, Any]] = []
    for document in policy_matrix_documents:
        bundle = results.get_bundle(document.id)
        if bundle is None:
            continue
        policies_by_temp_id = {
            policy.data.get("temporary_id"): policy.data for policy in bundle.policies
        }
        for index, activity in enumerate(bundle.policy_activities, start=1):
            data = activity.data
            policy = policies_by_temp_id.get(data.get("policy_temporary_id"), {})
            policy_name = policy.get("policy_name") or "Matriz de politicas publicas"
            keywords_text = " ".join([
                policy_name, policy.get("policy_axis") or "",
                data.get("activity_name", ""), data.get("activity_description", ""),
            ])
            rows.append({
                "activity_id": f"ACT-{document.id[:8]}-{index:03d}",
                "policy_name": policy_name,
                "instrument_name": policy.get("instrument_name") or policy_name,
                "policy_axis": policy.get("policy_axis") or "",
                "activity_name": data.get("activity_name", ""),
                "activity_description": data.get("activity_description", ""),
                "responsible_area": data.get("responsible_area") or "",
                "execution_period": data.get("execution_period") or "",
                "keywords": _keywords_for_text(keywords_text),
            })
    return pd.DataFrame(rows, columns=POLICY_ACTIVITY_COLUMNS)


def _build_dashboard_data_from_source(
    source: pd.DataFrame,
    *,
    policy_activities: pd.DataFrame | None = None,
    pmge_projects: pd.DataFrame | None = None,
) -> dict[str, Any]:
    STRUCTURED_DATA_DIR.mkdir(parents=True, exist_ok=True); DEMO_DATA_DIR.mkdir(parents=True, exist_ok=True); REFERENCE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    records = pd.DataFrame([_make_record(row) for _, row in source.iterrows()])
    serializable = records.copy()
    for column in ["tecnologias", "bandas_frecuencia", "paises_regiones", "organizaciones", "actores", "tipo_evento_regulatorio"]:
        serializable[column] = serializable[column].map(lambda x: json.dumps(parse_list_field(x), ensure_ascii=False))
    serializable.to_csv(STRUCTURED_DATA_DIR / OUTPUT_NAMES[0], index=False, encoding="utf-8-sig")
    _write_counts(records, "tema_estrategico", "tema_estrategico", STRUCTURED_DATA_DIR / OUTPUT_NAMES[2]); _write_counts(records, "relevancia_label", "relevancia_label", STRUCTURED_DATA_DIR / OUTPUT_NAMES[3]); _write_counts(records, "tipo_insumo_agenda", "tipo_insumo_agenda", STRUCTURED_DATA_DIR / OUTPUT_NAMES[4]); _write_counts(records, "tecnologias", "tecnologia", STRUCTURED_DATA_DIR / OUTPUT_NAMES[5], True); _write_counts(records, "bandas_frecuencia", "banda_frecuencia", STRUCTURED_DATA_DIR / OUTPUT_NAMES[6], True)
    matrices = [("tema_estrategico", "source_folder", OUTPUT_NAMES[7], False, False), ("tema_estrategico", "tecnologias", OUTPUT_NAMES[8], False, True), ("bandas_frecuencia", "tecnologias", OUTPUT_NAMES[9], True, True), ("tema_estrategico", "tipo_insumo_agenda", OUTPUT_NAMES[10], False, False), ("tema_estrategico", "relevancia_label", OUTPUT_NAMES[11], False, False)]
    for row_col, col_col, name, row_list, col_list in matrices: _write_matrix(records, row_col, col_col, STRUCTURED_DATA_DIR / name, row_list, col_list)
    signals = _build_signals(records); signals.to_csv(STRUCTURED_DATA_DIR / OUTPUT_NAMES[1], index=False, encoding="utf-8-sig")
    regulatory_map = build_regulatory_map(records)
    regulatory_trends = build_regulatory_trends(records)
    regulatory_map.to_csv(STRUCTURED_DATA_DIR / "dashboard_regulatory_map.csv", index=False, encoding="utf-8-sig")
    regulatory_trends.to_csv(STRUCTURED_DATA_DIR / "dashboard_regulatory_trends.csv", index=False, encoding="utf-8-sig")
    if policy_activities is None:
        policy_activities = build_policy_matrix_activities()
    if pmge_projects is None:
        pmge_projects = build_pmge_projects()
    document_alignment = build_document_policy_alignment(regulatory_trends, records, signals, policy_activities)
    pmge_alignment = build_pmge_policy_alignment(pmge_projects, policy_activities)
    policy_activities.to_csv(STRUCTURED_DATA_DIR / "policy_matrix_activities.csv", index=False, encoding="utf-8-sig")
    pmge_projects.to_csv(STRUCTURED_DATA_DIR / "pmge_projects.csv", index=False, encoding="utf-8-sig")
    document_alignment.to_csv(STRUCTURED_DATA_DIR / "dashboard_document_policy_alignment.csv", index=False, encoding="utf-8-sig")
    pmge_alignment.to_csv(STRUCTURED_DATA_DIR / "dashboard_pmge_policy_alignment.csv", index=False, encoding="utf-8-sig")
    for name in OUTPUT_NAMES: shutil.copy2(STRUCTURED_DATA_DIR / name, DEMO_DATA_DIR / name)
    return {"records_processed": len(records), "strategic_topics": records["tema_estrategico"].nunique(), "signals_generated": len(signals), "policy_activities": len(policy_activities), "pmge_projects": len(pmge_projects), "files_copied": len(OUTPUT_NAMES), "demo_data_dir": DEMO_DATA_DIR}

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = build_dashboard_data()
    print(f"Registros procesados: {result['records_processed']}"); print(f"Temas estratégicos identificados: {result['strategic_topics']}"); print(f"Señales generadas: {result['signals_generated']}"); print(f"Archivos copiados a demo_data: {result['files_copied']}"); print(f"Ruta de demo_data: {result['demo_data_dir']}")

if __name__ == "__main__": main()
