"""
streamlit_app.py — Interfaz Streamlit para Web Searcher
========================================================
Misma funcionalidad que static/index.html, pero usando directamente
src/search_jobs.py (sin llamadas HTTP a /api/*). El scraping sigue corriendo
en el hilo que lanza start_job(); esta página solo muestra el estado del Job.

Ejecutar aislado:   streamlit run streamlit_app.py
Desde la app unificada se importa y se llama a main().

Estado en st.session_state (claves con prefijo ws_ para no chocar con las
demás apps de la app unificada):
  - ws_job_id:   id del Job activo en JOBS.
  - ws_job_meta: datos de la solicitud que el Job no guarda (query, sitios,
                 traducciones), necesarios para pintar el progreso y el resumen.
  - ws_query, ws_site_ids, ws_translate, ws_format: widgets del formulario.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
SRC_DIR     = BASE_DIR / "src"
CONFIG_PATH = BASE_DIR / "config" / "sites.json"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from search_jobs import JOBS, JobInputError, start_job

MAX_LINKS = 50  # mismo valor fijo que envía static/index.html
FORMATS = {"xlsx": "Excel (.xlsx)", "csv": "CSV (.csv)"}
LANG_FLAGS = {"en": "🇬🇧", "es": "🇪🇸", "ko": "🇰🇷", "pt": "🇧🇷"}
RUNNING = ("pending", "running")


# ── Utilidades ────────────────────────────────────────────────────────────────
def _load_sites() -> list:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _short_name(site: dict) -> str:
    """Nombre corto del organismo (equivale a sn() en index.html)."""
    return site["name"].split("(")[0].split(" - ")[0].strip()


def _clear_job():
    st.session_state.pop("ws_job_id", None)
    st.session_state.pop("ws_job_meta", None)


def _select_all_sites(site_ids: list):
    st.session_state.ws_site_ids = list(site_ids)


def _select_no_sites():
    st.session_state.ws_site_ids = []


def _render_log(job, expanded: bool = False):
    logs = list(job.logs)  # copia: el hilo sigue agregando líneas
    with st.expander("Log en tiempo real", expanded=expanded, key="ws_log_expander"):
        st.code("\n".join(logs) or "(sin mensajes todavía)", language=None, height=300)


# ── Vista 1: formulario de búsqueda ───────────────────────────────────────────
def _render_search_form(all_sites: list):
    site_ids = [s["id"] for s in all_sites]
    names = {s["id"]: _short_name(s) for s in all_sites}
    if "ws_site_ids" not in st.session_state:
        st.session_state.ws_site_ids = list(site_ids)

    st.markdown(
        "Búsqueda automática en los principales organismos reguladores de "
        "telecomunicaciones, con traducción al idioma de cada sitio y "
        "exportación a Excel o CSV."
    )

    query = st.text_input(
        "Tema a buscar",
        key="ws_query",
        placeholder="Ej: gestión del espectro radioeléctrico, 5G spectrum policy…",
    )

    with st.expander("Opciones de búsqueda", expanded=True):
        st.pills(
            "Organismos a consultar",
            options=site_ids,
            selection_mode="multi",
            format_func=lambda sid: f"{sid.upper()} · {names[sid]}",
            key="ws_site_ids",
        )
        c1, c2, _ = st.columns([1, 1, 4])
        c1.button("Todos", on_click=_select_all_sites, args=(site_ids,),
                  key="ws_btn_all", width="stretch")
        c2.button("Ninguno", on_click=_select_no_sites,
                  key="ws_btn_none", width="stretch")

        o1, o2 = st.columns(2)
        with o1:
            st.radio(
                "Formato de descarga",
                options=list(FORMATS),
                format_func=FORMATS.get,
                horizontal=True,
                key="ws_format",
            )
        with o2:
            st.toggle("Traducir al idioma de cada sitio", value=True, key="ws_translate")

    if not st.button("Buscar", type="primary", icon="🔍", key="ws_btn_search"):
        return

    selected = list(st.session_state.ws_site_ids or [])
    if not query.strip():
        st.warning("Escribe un tema para buscar.")
        return
    if not selected:
        st.warning("Selecciona al menos un organismo.")
        return

    no_translate = not st.session_state.ws_translate
    try:
        with st.spinner("Traduciendo la consulta e iniciando el navegador…"):
            started = start_job(
                query=query,
                site_ids=selected,
                no_translate=no_translate,
                fmt=st.session_state.ws_format,
                max_links=MAX_LINKS,
                all_sites=all_sites,
            )
    except JobInputError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"No fue posible iniciar la búsqueda: {e}")
        return

    st.session_state.ws_job_id = started.job.id
    st.session_state.ws_job_meta = {
        "query": started.translations["original"],
        "site_ids": [s["id"] for s in started.sites],
        "translations": (
            {} if no_translate
            else {k: v for k, v in started.translations.items() if k != "original"}
        ),
    }
    st.rerun()


# ── Vista 2: progreso (se refresca solo cada segundo) ─────────────────────────
@st.fragment(run_every="1s")
def _render_progress(job_id: str, meta: dict, names: dict):
    job = JOBS.get(job_id)
    if job is None or job.status not in RUNNING:
        st.rerun()  # rerun completo: main() pasa a la vista de resultados/error

    site_ids = meta["site_ids"]
    done_counts = dict(job.site_results)  # copia: el hilo sigue escribiendo
    total = job.total or len(site_ids)
    pct = int(job.current / total * 100) if total else 0
    links = sum(done_counts.values())

    st.subheader(f'Buscando: "{meta["query"]}"')
    st.caption(job.current_site_name or "Iniciando navegador Chromium…")
    st.progress(
        pct / 100,
        text=f"{pct}% · {job.current} / {total} organismos · {links} links encontrados",
    )

    if meta["translations"]:
        st.caption("Traducciones: " + "  ·  ".join(
            f"{LANG_FLAGS.get(lang, lang.upper())} {lang.upper()}: {text}"
            for lang, text in meta["translations"].items()
        ))

    cols = st.columns(5)
    for i, sid in enumerate(site_ids):
        if sid in done_counts:
            n = done_counts[sid]
            status = f"✅ {n} links" if n > 0 else "— Sin resultados"
        elif sid == job.current_site_id:
            status = "⏳ Buscando…"
        else:
            status = "⬜ Esperando…"
        with cols[i % 5].container(border=True):
            st.markdown(f"**{sid.upper()}**")
            st.caption(names.get(sid, sid))
            st.markdown(status)

    _render_log(job)


# ── Vista 3: resultados / error ───────────────────────────────────────────────
def _render_results(job, meta: dict, names: dict):
    counts = dict(job.site_results)
    site_ids = meta["site_ids"]
    total = len(job.results)

    st.success(f'Búsqueda completada — resultados para "{meta["query"]}"')

    k1, k2, k3 = st.columns(3)
    k1.metric("Links encontrados", total, border=True)
    k2.metric("Con resultados", sum(1 for sid in site_ids if counts.get(sid, 0) > 0), border=True)
    k3.metric("Consultados", len(site_ids), border=True)

    st.dataframe(
        pd.DataFrame([
            {
                "ID": sid.upper(),
                "Organismo": names.get(sid, sid),
                "Links": counts.get(sid, 0),
                "OK": "✅" if counts.get(sid, 0) > 0 else "—",
            }
            for sid in site_ids
        ]),
        hide_index=True,
        width="stretch",
    )

    if job.file_bytes:
        st.download_button(
            f"Descargar resultados ({total} links)",
            data=job.file_bytes,
            file_name=job.file_name,
            mime=job.file_mime,
            type="primary",
            icon="⬇️",
            on_click="ignore",
            key="ws_btn_download",
        )
    else:
        st.info("La búsqueda no encontró links, así que no se generó archivo de descarga.")

    if job.results:
        with st.expander("Ver links encontrados"):
            st.dataframe(pd.DataFrame(job.results), hide_index=True, width="stretch")

    _render_log(job)
    st.button("← Nueva búsqueda", on_click=_clear_job, key="ws_btn_new")


def _render_error(job, meta: dict):
    st.error(
        f'La búsqueda de "{meta["query"]}" terminó con error: '
        f"{job.error_msg or 'Error desconocido'}"
    )
    _render_log(job, expanded=True)
    st.button("← Nueva búsqueda", on_click=_clear_job, key="ws_btn_new")


# ── Punto de entrada ──────────────────────────────────────────────────────────
def main():
    st.title("🌐 Web Searcher — Reguladores internacionales")

    try:
        all_sites = _load_sites()
    except FileNotFoundError:
        st.error(f"No se encontró la configuración de sitios: {CONFIG_PATH}")
        return
    names = {s["id"]: _short_name(s) for s in all_sites}

    job_id = st.session_state.get("ws_job_id")
    meta = st.session_state.get("ws_job_meta")
    job = JOBS.get(job_id) if job_id else None

    if job_id and (job is None or meta is None):
        # El Job ya no existe (limpieza tras 1 h o reinicio del servidor).
        _clear_job()
        st.warning(
            "La búsqueda anterior ya no está disponible (los resultados se "
            "conservan 1 hora). Inicia una nueva búsqueda."
        )
        job = None

    if job is None:
        _render_search_form(all_sites)
    elif job.status in RUNNING:
        _render_progress(job_id, meta, names)
    elif job.status == "done":
        _render_results(job, meta, names)
    else:
        _render_error(job, meta)


if __name__ == "__main__":
    st.set_page_config(page_title="Web Searcher — ANE", page_icon="🌐", layout="wide")
    main()
