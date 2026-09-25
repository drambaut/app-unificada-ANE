"""
streamlit_app.py — Interfaz Streamlit de Banda 900
===================================================
Formulario de solicitud de la comunidad, reporte de una solicitud y panel
administrativo (login Supabase, alta manual, carga masiva, listado), usando
directamente backend/app (services, schemas, supabase_auth) sin FastAPI.

Ejecutar aislado:   streamlit run formulario-banda-900/streamlit_app.py
Desde la app unificada se importa y se llama a main().

Configuración (entorno o .env de Banda), solo con prefijo B900_ porque dentro
de app-unificada DATABASE_URL / SUPABASE_* pueden pertenecer a otras apps:
  - B900_DATABASE_URL: formulario, reporte y administración.
  - B900_SUPABASE_URL, B900_SUPABASE_ANON_KEY, B900_SUPABASE_SERVICE_ROLE_KEY:
    administración (login y Storage).

Estado en st.session_state (prefijo b900_):
  - b900_estaciones / b900_admin_estacion: estructura estaciones → sectores →
    antenas (solo ids) del formulario público y del alta manual.
  - b900_sol_*, b900_est_<id>_*, b900_ant_<id>_*: valores de los widgets.
  - b900_confirmacion: {id, estado} de la última solicitud enviada.
  - b900_vista, b900_reporte_id, b900_reporte_input, b900_qp: navegación/reporte.
  - b900_auth: tokens y usuario de la sesión administrativa.
  - b900_admin_pestana, b900_admin_mensaje, b900_admin_error,
    b900_carga_resultado: estado del panel administrativo.
"""
import html
import json
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
BACKEND_DIR = BASE_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import database, services, settings, supabase_auth, supabase_client
from app.campos_antena import CAMPOS_ANTENA, validar_campo
from app.schemas import EstacionIn, EstacionOut, SolicitudIn

DIVIPOLA = json.loads((BACKEND_DIR / "app" / "divipola.json").read_text(encoding="utf-8"))
DEPARTAMENTOS = list(DIVIPOLA)
CAMPOS_ORDEN = ["acimut", "tilt", "ganancia", "angulo_apertura", "altura_suelo"]
CAMPOS_SOLICITUD = [
    ("razon_social", "Comunidad (Razón social)"),
    ("nit", "NIT"),
    ("representante_legal", "Representante legal"),
    ("telefono", "Teléfono"),
    ("direccion", "Dirección"),
    ("correo_electronico", "Correo electrónico"),
    ("radicado_mintic", "Radicado de solicitud MinTIC"),
]
OBLIGATORIOS_SOLICITUD = CAMPOS_SOLICITUD[:6]  # radicado_mintic es opcional
BOGOTA = (4.6097, -74.0817)
TZ_COLOMBIA = timezone(timedelta(hours=-5))  # Colombia no tiene horario de verano
VISTA_FORMULARIO = "Formulario de solicitud"
VISTA_REPORTE = "Consultar reporte"
VISTA_ADMIN = "Administración"
PESTANAS_ADMIN = ["Nueva estación (manual)", "Carga masiva", "Estaciones cargadas"]
TIPOS_ESTACION = {"nueva": "Nueva", "repetidora": "Repetidora"}
VARIABLES_SUPABASE = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")


# ── Lógica portada del frontend React (sin cambios de fórmula) ───────────────
def _numero_js(valor) -> float:
    """Number(valor) de JavaScript para los valores del formulario (vacío → 0)."""
    if valor is None or valor == "":
        return 0.0
    return float(valor)


def gms_a_decimal(grados, minutos, segundos, negativo: bool) -> float:
    """gmsADecimal de CoordenadasInput.jsx: Number(x) || 0 para cada parte."""
    g = _numero_js(grados)
    m = _numero_js(minutos)
    s = _numero_js(segundos)
    decimal = g + m / 60 + s / 3600
    return -decimal if negativo else decimal


def correo_valido(correo: str) -> bool:
    """REGEX_CORREO de FormularioComunidad.jsx."""
    return re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", correo or "") is not None


def preparar_estacion_para_envio(estacion: dict) -> dict:
    """prepararEstacionParaEnvio de utils.js."""
    return {
        "latitud": _numero_js(estacion["latitud"]),
        "longitud": _numero_js(estacion["longitud"]),
        "formato_coordenadas": estacion["formato_coordenadas"],
        "direccion_estacion": estacion["direccion_estacion"] or None,
        "departamento": estacion["departamento"] or None,
        "municipio": estacion["municipio"] or None,
        "tipo_estacion": estacion["tipo_estacion"] or None,
        "cantidad_sectores": len(estacion["sectores"]),
        "sectores": [
            {
                "numero_sector": s["numero_sector"],
                "antenas": [{c: _numero_js(a[c]) for c in CAMPOS_ORDEN} for a in s["antenas"]],
            }
            for s in estacion["sectores"]
        ],
    }


def construir_payload(solicitud: dict, estaciones: list) -> dict:
    """Payload de manejarEnvio (FormularioComunidad.jsx)."""
    return {
        **solicitud,
        "radicado_mintic": solicitud["radicado_mintic"] or None,
        "estaciones": [preparar_estacion_para_envio(e) for e in estaciones],
    }


def estacion_campos_faltantes(est: dict) -> list:
    """Atributos `required` de EstacionForm.jsx (coordenadas decimales, ubicación, antenas)."""
    faltan = []
    if est["formato_coordenadas"] == "decimal":
        faltan += [n for n, v in (("Latitud", est["latitud"]), ("Longitud", est["longitud"])) if v is None]
    faltan += [n for n in ("Departamento", "Municipio") if not est[n.lower()]]
    for sec in est["sectores"]:
        for k, ant in enumerate(sec["antenas"], 1):
            vacios = [CAMPOS_ANTENA[c]["label"] for c in CAMPOS_ORDEN if ant[c] is None]
            if vacios:
                faltan.append(f"Sector {sec['numero_sector']} · Antena {k}: {', '.join(vacios)}")
    return faltan


def campos_obligatorios_faltantes(solicitud: dict, estaciones: list) -> list:
    """Equivale a los atributos `required` del formulario HTML de React."""
    faltan = [
        etiqueta for campo, etiqueta in OBLIGATORIOS_SOLICITUD
        if not (solicitud[campo].replace("+57", "", 1) if campo == "telefono" else solicitud[campo])
    ]
    for i, est in enumerate(estaciones, 1):
        faltan += [f"Estación {i}: {f}" for f in estacion_campos_faltantes(est)]
    return faltan


# ── Reporte imprimible (ReporteSolicitud.jsx) ─────────────────────────────────
def _num_texto(valor) -> str:
    """Muestra números como JavaScript (120, no 120.0)."""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return repr(valor) if isinstance(valor, float) else str(valor)


def fecha_es_co(valor) -> str:
    """new Date(...).toLocaleString('es-CO'), en hora de Colombia."""
    if not valor:
        return ""
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    d = valor.astimezone(TZ_COLOMBIA)
    hora = d.hour % 12 or 12
    return f"{d.day}/{d.month}/{d.year}, {hora}:{d.minute:02d}:{d.second:02d} {'a. m.' if d.hour < 12 else 'p. m.'}"


def reporte_html(rep: dict) -> str:
    e = lambda v: html.escape(str(v))
    fila = lambda th, td: f"<tr><th>{e(th)}</th><td>{e(td)}</td></tr>"
    contacto = "".join([
        fila("Comunidad (Razón social)", rep["razon_social"]),
        fila("NIT", rep["nit"]),
        fila("Representante legal", rep["representante_legal"]),
        fila("Teléfono", rep["telefono"]),
        fila("Dirección", rep["direccion"]),
        fila("Correo electrónico", rep["correo_electronico"]),
        fila("Radicado MinTIC", rep["radicado_mintic"] or "—"),
        fila("Estado", rep["estado"]),
        fila("Fecha de envío", fecha_es_co(rep["created_at"])),
    ])
    estaciones = ""
    for idx, est in enumerate(rep["estaciones"], 1):
        sectores = ""
        for sec in est["sectores"]:
            antenas = "".join(
                "<tr>" + "".join(f"<td>{e(_num_texto(a[c]))}</td>" for c in CAMPOS_ORDEN) + "</tr>"
                for a in sec["antenas"]
            )
            sectores += (
                f'<h3>Sector {e(sec["numero_sector"])}</h3><table><thead><tr><th>ACIMUT</th><th>TILT</th>'
                f"<th>Ganancia</th><th>Ángulo de apertura</th><th>Altura al suelo</th></tr></thead>"
                f"<tbody>{antenas}</tbody></table>"
            )
        estaciones += (
            f'<div class="tarjeta"><h2>Estación {idx}</h2><table><tbody>'
            + fila("Coordenadas", f"{_num_texto(est['latitud'])}, {_num_texto(est['longitud'])}")
            + fila("Dirección", est["direccion_estacion"] or "—")
            + fila("Departamento", est["departamento"] or "—")
            + fila("Municipio", est["municipio"] or "—")
            + f"</tbody></table>{sectores}</div>"
        )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>ANE — Reporte de solicitud #{e(rep["id"])}</title>
<style>
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #1f2937; margin: 0; }}
  .encabezado {{ background: #103783; color: #fff; padding: 14px 24px; }}
  .encabezado h1 {{ margin: 0; font-size: 1.3rem; }}
  .contenedor {{ padding: 16px 24px; }}
  .tarjeta {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; }}
  h2 {{ font-size: 1.05rem; color: #103783; margin: 4px 0 10px; }}
  h3 {{ font-size: 0.95rem; color: #103783; margin: 12px 0 6px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 12px; }}
  th, td {{ border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; font-size: 0.9rem; }}
  th {{ background: #f3f4f6; width: 32%; }}
  thead th {{ width: auto; }}
  button {{ background: #103783; color: #fff; border: 0; border-radius: 6px; padding: 8px 14px; cursor: pointer; }}
  @media print {{ .no-imprimir {{ display: none; }} }}
</style></head>
<body>
<header class="encabezado"><h1>ANE — Reporte de solicitud</h1></header>
<div class="contenedor">
  <div class="no-imprimir" style="margin-bottom:16px"><button onclick="window.print()">Imprimir / Guardar como PDF</button></div>
  <div class="tarjeta"><h2>Información de contacto</h2><table><tbody>{contacto}</tbody></table></div>
  {estaciones}
</div>
</body></html>"""


# ── Estado del formulario ─────────────────────────────────────────────────────
def _nuevo_id() -> str:
    return uuid.uuid4().hex[:8]


def _sector_vacio() -> dict:
    return {"id": _nuevo_id(), "antenas": [_nuevo_id()]}


def _estacion_vacia() -> dict:
    return {"id": _nuevo_id(), "sectores": [_sector_vacio()]}


def _k_sol(campo: str) -> str:
    return f"b900_sol_{campo}"


def _k_est(eid: str, campo: str) -> str:
    return f"b900_est_{eid}_{campo}"


def _k_ant(aid: str, campo: str) -> str:
    return f"b900_ant_{aid}_{campo}"


def _estacion(eid: str) -> dict:
    ss = st.session_state
    candidatas = list(ss.get("b900_estaciones", []))
    if "b900_admin_estacion" in ss:
        candidatas.append(ss.b900_admin_estacion)
    return next(e for e in candidatas if e["id"] == eid)


def _sector(eid: str, sid: str) -> dict:
    return next(s for s in _estacion(eid)["sectores"] if s["id"] == sid)


# Callbacks (se ejecutan antes del rerun, por eso pueden modificar el estado)
def _agregar_estacion():
    st.session_state.b900_estaciones.append(_estacion_vacia())


def _quitar_estacion(eid):
    st.session_state.b900_estaciones = [e for e in st.session_state.b900_estaciones if e["id"] != eid]


def _agregar_sector(eid):
    _estacion(eid)["sectores"].append(_sector_vacio())


def _quitar_sector(eid, sid):
    est = _estacion(eid)
    est["sectores"] = [s for s in est["sectores"] if s["id"] != sid]  # la numeración es la posición


def _agregar_antena(eid, sid):
    _sector(eid, sid)["antenas"].append(_nuevo_id())


def _quitar_antena(eid, sid, aid):
    sec = _sector(eid, sid)
    sec["antenas"] = [a for a in sec["antenas"] if a != aid]


def _solo_digitos(key, maximo):
    """Igual que React: el NIT y el teléfono solo aceptan dígitos."""
    st.session_state[key] = re.sub(r"\D", "", st.session_state.get(key) or "")[:maximo]


def _limpiar_municipio(key_municipio):
    """Al cambiar de departamento se limpia el municipio (UbicacionSelect.jsx)."""
    st.session_state[key_municipio] = None


def _ver_reporte(solicitud_id):
    st.session_state.b900_vista = VISTA_REPORTE
    st.session_state.b900_reporte_id = solicitud_id
    st.session_state.b900_reporte_input = solicitud_id


def _nueva_solicitud():
    st.session_state.pop("b900_confirmacion", None)


def _consultar_reporte():
    valor = st.session_state.get("b900_reporte_input")
    st.session_state.b900_reporte_id = int(valor) if valor else None


def _leer_solicitud() -> dict:
    ss = st.session_state
    datos = {campo: ss.get(_k_sol(campo)) or "" for campo, _ in CAMPOS_SOLICITUD}
    datos["telefono"] = f"+57{datos['telefono']}"
    return datos


def _coordenadas(eid: str):
    ss = st.session_state
    if ss.get(_k_est(eid, "formato"), "decimal") == "gms":
        lat = gms_a_decimal(ss.get(_k_est(eid, "lat_g")), ss.get(_k_est(eid, "lat_m")),
                            ss.get(_k_est(eid, "lat_s")), ss.get(_k_est(eid, "lat_hem"), "N") == "S")
        lon = gms_a_decimal(ss.get(_k_est(eid, "lon_g")), ss.get(_k_est(eid, "lon_m")),
                            ss.get(_k_est(eid, "lon_s")), ss.get(_k_est(eid, "lon_hem"), "E") == "O")
        return lat, lon
    return ss.get(_k_est(eid, "lat")), ss.get(_k_est(eid, "lon"))


def _leer_estacion(est: dict) -> dict:
    """Estación con la forma que usa React (entrada de prepararEstacionParaEnvio)."""
    ss, eid = st.session_state, est["id"]
    lat, lon = _coordenadas(eid)
    return {
        "latitud": lat,
        "longitud": lon,
        "formato_coordenadas": ss.get(_k_est(eid, "formato"), "decimal"),
        "direccion_estacion": ss.get(_k_est(eid, "direccion")) or "",
        "departamento": ss.get(_k_est(eid, "departamento")) or "",
        "municipio": ss.get(_k_est(eid, "municipio")) or "",
        "tipo_estacion": ss.get(_k_est(eid, "tipo")) or "",  # solo en el panel administrativo
        "sectores": [
            {
                "numero_sector": j,
                "antenas": [{c: ss.get(_k_ant(aid, c)) for c in CAMPOS_ORDEN} for aid in sec["antenas"]],
            }
            for j, sec in enumerate(est["sectores"], 1)
        ],
    }


# ── Recursos ──────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _session_factory(database_url: str):
    """Un engine por URL para todo el proceso (no se recrea en cada rerun)."""
    return sessionmaker(bind=database.crear_engine(database_url), autoflush=False, autocommit=False)


# ── Vistas ────────────────────────────────────────────────────────────────────
def _render_estacion(est: dict, mostrar_tipo_estacion: bool = False):
    eid = est["id"]
    formato = st.radio(
        "Formato de coordenadas",
        options=["decimal", "gms"],
        format_func={"decimal": "Decimal", "gms": "GMS (grados, minutos, segundos)"}.get,
        horizontal=True,
        key=_k_est(eid, "formato"),
    )
    if formato == "gms":
        for eje, hemisferios, titulo in (("lat", ["N", "S"], "Latitud"), ("lon", ["E", "O"], "Longitud")):
            st.markdown(f"**{titulo}**")
            c = st.columns(4)
            c[0].selectbox(f"{hemisferios[0]}/{hemisferios[1]}", hemisferios, key=_k_est(eid, f"{eje}_hem"))
            c[1].number_input("Grados °", value=None, step=1.0, format="%g", key=_k_est(eid, f"{eje}_g"))
            c[2].number_input("Minutos '", value=None, step=1.0, format="%g", key=_k_est(eid, f"{eje}_m"))
            c[3].number_input('Segundos "', value=None, step=1.0, format="%g", key=_k_est(eid, f"{eje}_s"))
        lat, lon = _coordenadas(eid)
        st.caption(f"Equivalente decimal: {lat:.6f}, {lon:.6f}")
    else:
        c1, c2 = st.columns(2)
        c1.number_input("Latitud", value=None, step=0.000001, format="%.6f", key=_k_est(eid, "lat"))
        c2.number_input("Longitud", value=None, step=0.000001, format="%.6f", key=_k_est(eid, "lon"))
        lat, lon = _coordenadas(eid)

    # MapaUbicacion.jsx: marcador solo con coordenadas válidas; si no, Bogotá sin marcador
    valida = lat is not None and lon is not None and (lat != 0 or lon != 0)
    centro = (lat, lon) if valida else BOGOTA
    st.map(pd.DataFrame({"lat": [centro[0]], "lon": [centro[1]]}), zoom=13 if valida else 5,
           color="#E53935" if valida else "#00000000", height=260)

    c1, c2, c3 = st.columns(3)
    c1.text_input("Dirección de la estación", key=_k_est(eid, "direccion"))
    k_mun = _k_est(eid, "municipio")
    departamento = c2.selectbox("Departamento", DEPARTAMENTOS, index=None, placeholder="Seleccione...",
                                key=_k_est(eid, "departamento"), on_change=_limpiar_municipio, args=(k_mun,))
    c3.selectbox("Municipio", DIVIPOLA.get(departamento, []), index=None,
                 placeholder="Seleccione..." if departamento else "Primero elige el departamento",
                 disabled=not departamento, key=k_mun)

    if mostrar_tipo_estacion:
        st.selectbox("Tipo de estación", list(TIPOS_ESTACION), format_func=TIPOS_ESTACION.get,
                     index=None, placeholder="Seleccione...", key=_k_est(eid, "tipo"))

    st.markdown("**Sectores y antenas**")
    for j, sec in enumerate(est["sectores"], 1):
        sid = sec["id"]
        with st.container(border=True):
            st.markdown(f"**Sector {j}**")
            for aid in sec["antenas"]:
                cols = st.columns(len(CAMPOS_ORDEN))
                for col, campo in zip(cols, CAMPOS_ORDEN):
                    cfg = CAMPOS_ANTENA[campo]
                    valor = col.number_input(cfg["label"], value=None, step=1.0, format="%g",
                                             help=cfg["tooltip"], key=_k_ant(aid, campo))
                    error = validar_campo(campo, valor) if valor is not None else None
                    if error:
                        col.caption(f":red[{error}]")
                if len(sec["antenas"]) > 1:
                    st.button("Quitar antena", key=f"b900_btn_quitar_ant_{aid}",
                              on_click=_quitar_antena, args=(eid, sid, aid))
            b1, b2, _ = st.columns([1, 1, 2])
            b1.button("+ Agregar antena a este sector", key=f"b900_btn_agregar_ant_{sid}",
                      on_click=_agregar_antena, args=(eid, sid))
            if len(est["sectores"]) > 1:
                b2.button("Quitar sector", key=f"b900_btn_quitar_sec_{sid}",
                          on_click=_quitar_sector, args=(eid, sid))
    st.button("+ Agregar sector", key=f"b900_btn_agregar_sec_{eid}", on_click=_agregar_sector, args=(eid,))


def _enviar(Session):
    solicitud = _leer_solicitud()
    estaciones = [_leer_estacion(e) for e in st.session_state.b900_estaciones]

    faltan = campos_obligatorios_faltantes(solicitud, estaciones)
    if faltan:
        st.error("Completa los campos obligatorios:\n\n" + "\n".join(f"- {f}" for f in faltan))
        return
    if not correo_valido(solicitud["correo_electronico"]):
        st.error("El correo electrónico no tiene un formato válido (ej: nombre@dominio.com)")
        return
    if len(solicitud["telefono"].replace("+57", "", 1)) < 7:
        st.error("El teléfono debe tener entre 7 y 10 dígitos")
        return

    try:
        payload = SolicitudIn.model_validate(construir_payload(solicitud, estaciones))
    except ValidationError as exc:
        st.error("La solicitud no es válida:\n\n" + "\n".join(
            f"- {' → '.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        ))
        return

    try:
        with st.spinner("Enviando..."):
            with Session() as db:
                creada = services.crear_solicitud(db, payload)
                confirmacion = {"id": creada.id, "estado": creada.estado}
    except Exception as exc:  # noqa: BLE001
        st.error(f"No fue posible enviar la solicitud: {exc}")
        return

    st.session_state.b900_confirmacion = confirmacion
    st.session_state.b900_estaciones = [_estacion_vacia()]
    st.rerun()


def _render_formulario(Session):
    conf = st.session_state.get("b900_confirmacion")
    if conf:
        st.success(f"Solicitud #{conf['id']} enviada correctamente. Estado: {conf['estado']}.")
        c1, c2, _ = st.columns([1, 1, 2])
        c1.button("Ver reporte de la solicitud", type="primary", key="b900_btn_ver_reporte",
                  on_click=_ver_reporte, args=(conf["id"],))
        c2.link_button("Abrir reporte en pestaña nueva", f"?b900_reporte={conf['id']}")
        st.button("Nueva solicitud", key="b900_btn_nueva", on_click=_nueva_solicitud)
        return

    with st.container(border=True):
        st.subheader("Información de contacto")
        c1, c2 = st.columns(2)
        c1.text_input("Comunidad (Razón social)", key=_k_sol("razon_social"))
        c2.text_input("NIT", key=_k_sol("nit"), max_chars=15, placeholder="Solo números",
                      on_change=_solo_digitos, args=(_k_sol("nit"), 15))
        c1, c2 = st.columns(2)
        c1.text_input("Representante legal", key=_k_sol("representante_legal"))
        telefono = c2.text_input("Teléfono (+57)", key=_k_sol("telefono"), max_chars=10, placeholder="3001234567",
                                 on_change=_solo_digitos, args=(_k_sol("telefono"), 10))
        if 0 < len(telefono) < 7:
            c2.caption(":red[Debe tener al menos 7 dígitos]")
        st.text_input("Dirección", key=_k_sol("direccion"), max_chars=43)
        c1, c2 = st.columns(2)
        correo = c1.text_input("Correo electrónico", key=_k_sol("correo_electronico"))
        if correo and not correo_valido(correo):
            c1.caption(":red[Formato inválido, debe ser como nombre@dominio.com]")
        c2.text_input("Radicado de solicitud MinTIC", key=_k_sol("radicado_mintic"))

    st.subheader("Estaciones")
    estaciones = st.session_state.b900_estaciones
    for i, est in enumerate(estaciones, 1):
        with st.expander(f"Estación {i}", expanded=True):
            _render_estacion(est)
            if len(estaciones) > 1:
                st.button("Quitar esta estación", key=f"b900_btn_quitar_est_{est['id']}",
                          on_click=_quitar_estacion, args=(est["id"],))
    st.button("+ Agregar otra estación", key="b900_btn_agregar_est", on_click=_agregar_estacion)

    if st.button("Enviar solicitud", type="primary", key="b900_btn_enviar"):
        _enviar(Session)

    st.caption(
        "Al enviar este formulario aceptas nuestra política de tratamiento de datos "
        "personales. [Enlace pendiente de definir por la entidad]"
    )


def _render_reporte(Session):
    c1, c2, _ = st.columns([1, 1, 2], vertical_alignment="bottom")
    c1.number_input("Número de solicitud", min_value=1, step=1, value=None, format="%d",
                    key="b900_reporte_input")
    c2.button("Consultar", key="b900_btn_consultar", on_click=_consultar_reporte)

    solicitud_id = st.session_state.get("b900_reporte_id")
    if not solicitud_id:
        st.info("Ingresa el número de la solicitud para ver su reporte.")
        return
    try:
        with Session() as db:
            rep = services.obtener_reporte(db, solicitud_id)
    except services.SolicitudNoEncontrada:
        st.error("Solicitud no encontrada")
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"No fue posible consultar el reporte: {exc}")
        return

    contenido = reporte_html(rep)
    st.download_button(
        "Descargar reporte (HTML imprimible)",
        data=contenido.encode("utf-8"),
        file_name=f"reporte_solicitud_{rep['id']}.html",
        mime="text/html",
        icon="⬇️",
        on_click="ignore",
        key="b900_btn_descargar_reporte",
    )
    st.iframe(contenido, height="content")


# ── Administración (AdminLogin.jsx / AdminPanel.jsx) ──────────────────────────
def _supabase_faltante() -> list:
    """Variables B900_SUPABASE_* ausentes: sin ellas no hay administración (no se
    usa el SUPABASE_* de otras apps del shell como respaldo)."""
    return [f"B900_{nombre}" for nombre in VARIABLES_SUPABASE if not settings.valor_b900(nombre)]


@st.cache_resource(show_spinner=False)
def _asegurar_bucket(supabase_url: str) -> bool:
    """Lo que hacía el evento startup de FastAPI: crear el bucket si no existe (nunca falla)."""
    supabase_client.ensure_bucket_cargas()
    return True


def _refrescar_sesion(auth: dict) -> dict:
    nueva = supabase_auth.refrescar_sesion(auth["refresh_token"])
    st.session_state.b900_auth = nueva
    return nueva


def _usuario_admin():
    """
    Equivale a get_current_user antes de cada operación protegida: valida el
    token contra Supabase Auth y, si expiró, intenta refrescar la sesión.
    Devuelve {"sub", "email"} o None (sesión inválida o validación imposible).
    """
    auth = st.session_state.get("b900_auth")
    if not auth:
        return None
    try:
        if auth.get("expires_at") and time.time() >= auth["expires_at"] - 30:
            auth = _refrescar_sesion(auth)
        return supabase_auth.usuario_desde_token(auth["access_token"])
    except supabase_auth.AuthError as exc:
        if exc.status_code != 401:
            st.error(exc.detail)  # 500/502: no se pudo validar, la sesión se conserva
            return None
    try:
        auth = _refrescar_sesion(auth)
        return supabase_auth.usuario_desde_token(auth["access_token"])
    except supabase_auth.AuthError:
        st.session_state.pop("b900_auth", None)
        st.session_state.b900_admin_error = "Token invalido o expirado, vuelve a iniciar sesion"
        st.rerun()


def _cerrar_sesion():
    auth = st.session_state.pop("b900_auth", None)
    if auth:
        supabase_auth.cerrar_sesion(auth["access_token"], auth["refresh_token"])
    st.session_state.pop("b900_carga_resultado", None)


def _render_login(faltan: list):
    st.subheader("Acceso Ingeniero GIE / Administrador")
    if faltan:
        st.error("Para usar la administración configura: " + ", ".join(f"**{v}**" for v in faltan))
        return
    aviso = st.session_state.pop("b900_admin_error", None)
    if aviso:
        st.warning(aviso)
    with st.form("b900_form_login", clear_on_submit=True):
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Ingresar", type="primary")
    if not entrar:
        return
    if not email or not password:
        st.error("Ingresa el correo y la contraseña.")
        return
    try:
        with st.spinner("Ingresando..."):
            st.session_state.b900_auth = supabase_auth.iniciar_sesion(email, password)
    except supabase_auth.AuthError as exc:
        st.error(exc.detail or "No fue posible iniciar sesión")
        return
    st.rerun()


def _render_admin_manual(Session):
    if "b900_admin_estacion" not in st.session_state:
        st.session_state.b900_admin_estacion = _estacion_vacia()
    est = st.session_state.b900_admin_estacion
    with st.container(border=True):
        _render_estacion(est, mostrar_tipo_estacion=True)
    if not st.button("Guardar estación", type="primary", key="b900_btn_guardar_estacion"):
        return

    datos = _leer_estacion(est)
    faltan = estacion_campos_faltantes(datos)
    if faltan:
        st.error("Completa los campos obligatorios:\n\n" + "\n".join(f"- {f}" for f in faltan))
        return
    try:
        payload = EstacionIn.model_validate(preparar_estacion_para_envio(datos))
    except ValidationError as exc:
        st.error("La estación no es válida:\n\n" + "\n".join(
            f"- {' → '.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        ))
        return
    usuario = _usuario_admin()
    if usuario is None:
        return
    try:
        with st.spinner("Guardando..."):
            with Session() as db:
                estacion_id = services.crear_estacion(db, payload, usuario["sub"]).id
    except Exception as exc:  # noqa: BLE001
        st.error(f"No fue posible guardar la estación: {exc}")
        return
    st.session_state.b900_admin_mensaje = f"Estación #{estacion_id} guardada correctamente."
    st.session_state.b900_admin_estacion = _estacion_vacia()
    st.rerun()


def _render_admin_carga(Session):
    with st.container(border=True):
        st.markdown("**Carga masiva de estaciones (CSV o XLSX)**")
        st.caption(
            f"Columnas requeridas: {', '.join(services.COLUMNAS_REQUERIDAS)}. "
            f"Opcionales: {', '.join(services.COLUMNAS_OPCIONALES)}."
        )
        archivo = st.file_uploader("Archivo", type=["csv", "xlsx", "xls"], key="b900_carga_archivo")
        if st.button("Subir archivo", key="b900_btn_subir", disabled=archivo is None):
            usuario = _usuario_admin()
            if usuario is None:
                return
            st.session_state.pop("b900_carga_resultado", None)
            try:
                with st.spinner("Procesando..."):
                    with Session() as db:
                        st.session_state.b900_carga_resultado = services.procesar_carga_masiva(
                            db, archivo.name, archivo.getvalue(), usuario["sub"]
                        )
            except services.ArchivoInvalido as exc:
                st.error(str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                st.error(f"No fue posible procesar el archivo: {exc}")
                return

        res = st.session_state.get("b900_carga_resultado")
        if res:
            resumen = (f"{res['filas_ok']} fila(s) cargadas correctamente, {res['filas_error']} con "
                       f"errores. Estado: {res['estado']}.")
            (st.success if res["filas_error"] == 0 else st.error)(resumen)
            if res["errores"]:
                st.dataframe(
                    pd.DataFrame([{"Fila": e["fila"], "Errores": ", ".join(e["errores"])} for e in res["errores"]]),
                    hide_index=True, width="stretch",
                )


def _render_admin_listado(Session):
    usuario = _usuario_admin()
    if usuario is None:
        return
    try:
        with Session() as db:
            estaciones = [EstacionOut.model_validate(e) for e in services.listar_estaciones_red(db)]
    except Exception as exc:  # noqa: BLE001
        st.error(f"No fue posible cargar las estaciones: {exc}")
        return
    st.markdown("**Estaciones de red registradas**")
    st.dataframe(
        pd.DataFrame(
            [[e.id, e.latitud, e.longitud, e.departamento, e.municipio, e.cantidad_sectores, e.fuente_carga]
             for e in estaciones],
            columns=["ID", "Lat", "Lon", "Departamento", "Municipio", "Sectores", "Fuente"],
        ),
        hide_index=True, width="stretch",
    )


def _render_admin(Session):
    faltan = _supabase_faltante()
    auth = st.session_state.get("b900_auth")
    if faltan or not auth:
        _render_login(faltan)
        return

    _asegurar_bucket(settings.valor_b900("SUPABASE_URL"))
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    c1.markdown(f"**Panel Ingeniero GIE** · {auth['email']}")
    c2.button("Cerrar sesión", key="b900_btn_logout", on_click=_cerrar_sesion)
    pestana = st.radio("Sección", PESTANAS_ADMIN, horizontal=True, key="b900_admin_pestana",
                       label_visibility="collapsed")
    mensaje = st.session_state.pop("b900_admin_mensaje", None)
    if mensaje:
        st.success(mensaje)

    if pestana == PESTANAS_ADMIN[0]:
        _render_admin_manual(Session)
    elif pestana == PESTANAS_ADMIN[1]:
        _render_admin_carga(Session)
    else:
        _render_admin_listado(Session)


def _aplicar_query_params():
    """?b900_reporte=<id> abre directamente el reporte (equivale a /solicitud/:id/reporte)."""
    valor = st.query_params.get("b900_reporte")
    if valor and valor.isdigit() and st.session_state.get("b900_qp") != valor:
        st.session_state.b900_qp = valor
        _ver_reporte(int(valor))


# ── Punto de entrada ──────────────────────────────────────────────────────────
def main():
    st.title("📋 Formulario Banda 900")
    st.caption("ANE — Solicitud de uso de la banda 900 MHz")

    database_url = settings.valor_b900("DATABASE_URL")
    if not database_url:
        st.error(
            "Falta configurar **B900_DATABASE_URL**: la connection string de Supabase Postgres "
            "(modo *Transaction pooler*) de Banda 900, como variable de entorno o en "
            "`formulario-banda-900/backend/app/.env`."
        )
        return
    try:
        Session = _session_factory(database_url)
    except RuntimeError as exc:
        st.error(str(exc))
        return

    if "b900_estaciones" not in st.session_state:
        st.session_state.b900_estaciones = [_estacion_vacia()]
    _aplicar_query_params()

    vista = st.radio("Vista", [VISTA_FORMULARIO, VISTA_REPORTE, VISTA_ADMIN], horizontal=True,
                     key="b900_vista", label_visibility="collapsed")
    if vista == VISTA_FORMULARIO:
        _render_formulario(Session)
    elif vista == VISTA_REPORTE:
        _render_reporte(Session)
    else:
        _render_admin(Session)


if __name__ == "__main__":
    st.set_page_config(page_title="Formulario Banda 900 — ANE", page_icon="📋", layout="wide")
    main()
