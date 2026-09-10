import streamlit as st
from google import genai
from docxtpl import DocxTemplate
import datetime
import os
import json
import re
import time
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent

load_dotenv(APP_DIR / ".env", override=True)

# ─────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

st.title("🤖 ANE - PQRs: Asistente de Respuesta")

# ─────────────────────────────────────────────
#  BASE DE CONOCIMIENTO CON ESPERA ACTIVA
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner="Cargando normatividad ANE (Esto toma unos segundos la primera vez)...")
def cargar_base_conocimiento():
    archivos_gemini = []
    rutas_pdfs = [
        APP_DIR / "docs" / "CompilatoriaResANE105_2020_Mod_Marzo_2024_1.pdf",
        APP_DIR / "docs" / "Resolucion_737_de_2022 _Modifica_Res_105_de_2020.pdf",
    ]
    for ruta in rutas_pdfs:
        if ruta.exists():
            archivo_subido = client.files.upload(file=str(ruta))
            
            while archivo_subido.state.name == "PROCESSING":
                time.sleep(2) 
                archivo_subido = client.files.get(name=archivo_subido.name)
                
            archivos_gemini.append(archivo_subido)
        else:
            st.warning(f"⚠️ No se encontró: {ruta}. Crea la carpeta 'docs/' y guarda los PDFs ahí.")
    return archivos_gemini

documentos_ane = cargar_base_conocimiento()

# ─────────────────────────────────────────────
#  INICIALIZACIÓN DE ESTADOS
# ─────────────────────────────────────────────
if "pqrs_messages" not in st.session_state:
    st.session_state.pqrs_messages = []

if "pqrs_doc_data" not in st.session_state:
    st.session_state.pqrs_doc_data = {
        "TRATO": "", "NOMBRE": "", "CORREO": "", "CARGO": "", "EMPRESA": "",
        "CIUDAD": "Bogotá D.C.", "ASUNTO": "", "SALUDO_INICIAL": "", "CUERPO": "",
        "FECHA": datetime.datetime.now().strftime("%d de %B de %Y"),
        "FIRMANTE_NOMBRE": "", "FIRMANTE_CARGO": "", "FIRMANTE_AREA": "",
    }

# ─────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """Eres un experto jurídico de la ANE (Agencia Nacional del Espectro de Colombia).
Tu tarea es ayudar a redactar respuestas formales a PQR (Peticiones, Quejas y Recursos).

TIENES ACCESO A LA NORMATIVIDAD OFICIAL (Res 105 de 2020 y Res 737 de 2022).

REGLAS DE FORMATO Y EXTRACCIÓN (MUY IMPORTANTE):
1. TRATO: Identifica si el destinatario es "Señor" o "Señora".
2. SALUDO INICIAL: Extrae el primer apellido del destinatario. Ej: "Respetado señor Rodríguez:"
3. CORREO: Extrae el correo si lo hay.
4. FIRMANTES: Si no te dicen quién firma, sugiere a Nicolás Silva, Margarita García o Johana Cruz.
5. NO USES NEGRITA: Queda estrictamente prohibido usar negrita (**) en el CUERPO de la respuesta. El formato estándar no lo permite.
6. CURSIVAS: Usa cursiva (*) solo cuando sea estrictamente necesario para términos legales o extranjeros.

REGLAS DEL CUERPO (ESTRICTO PARA USO LIBRE - RES 105):
Si la solicitud trata sobre uso libre, el CUERPO DEBE seguir esta estructura exacta:

Al respecto, inicialmente le informamos que la Agencia Nacional del Espectro (ANE) es la entidad encargada de planear, atribuir, controlar y vigilar el espectro radioeléctrico en el país y brindar la asesoría técnica en la gestión eficiente del mismo al Ministerio de Tecnologías de la Información y las Comunicaciones (MinTIC).

Ahora bien, en respuesta a su consulta y de acuerdo con nuestras competencias le comunicamos que la ANE expidió la Resolución 105 de 2020 de la ANE “Por medio de la cual se planea y atribuye el espectro radioeléctrico en Colombia”, en donde se establecen entre otros aspectos, la reglamentación general, las bandas de frecuencias, los límites de las emisiones no deseadas y las condiciones técnicas y operativas tanto generales como específicas de las aplicaciones permitidas para utilizar el espectro bajo la modalidad de uso libre dentro del territorio nacional.

La versión actualizada de la Resolución 105 de 2020 la puede encontrar en el siguiente enlace: [https://www.ane.gov.co/SitePages/normatividad/index.aspx?p=741](https://www.ane.gov.co/SitePages/normatividad/index.aspx?p=741)

En este sentido, le recomendamos consultar la tabla 1.2 del numeral 2 del Anexo 1 de la Resolución ANE 105 de 2020, en la cual se presentan los rangos de frecuencias, así como las condiciones técnicas y operativas generales de las aplicaciones permitidas para utilizar el espectro bajo la modalidad de uso libre en Colombia. En particular sobre los siguientes rangos de frecuencias que detalla en su comunicación: [AQUÍ MENCIONA LAS FRECUENCIAS CONSULTADAS]. A continuación, a manera de ejemplo se relacionan los fragmentos de la mencionada Tabla 1.2 teniendo en cuenta que corresponden a [AQUÍ MENCIONA EL TIPO DE DISPOSITIVO]:

[AQUÍ INSERTA UNA TABLA EN FORMATO MARKDOWN CON LA INFORMACIÓN EXTRAÍDA DEL PDF]

Como se puede apreciar en la columna “Observaciones” de la tabla anterior, las aplicaciones permitidas requieren condiciones técnicas y operativas específicas las cuales están descritas en la sección 3 del Anexo 1 de la Resolución 105 de 2020 de la ANE. Por lo tanto, le sugerimos consultar al detalle todas las condiciones descritas en la normatividad antes señalada para determinar si los dispositivos que requiere utilizar pueden funcionar bajo la modalidad de uso libre del espectro radioeléctrico.

Es importante mencionar que si los equipos que desea utilizar no cumplen con las condiciones técnicas establecidas en la Resolución 105 de 2020 de la ANE, para su utilización en Colombia es necesario solicitar un permiso ante el MinTIC por el uso del espectro radioeléctrico en el marco de los Procesos de Selección Objetiva (PSO) habilitados, tal como lo establece el artículo 11 de la Ley 1341 de 2009 modificado por el artículo 8 de la ley 1978 de 2019, según el cual “El uso del espectro radioeléctrico requiere permiso previo, expreso y otorgado por el Ministerio de Tecnologías de la Información y las Comunicaciones (...)”, para mayor información acerca de los PSO puede consultar en el siguiente enlace:
[https://www.mintic.gov.co/portal/inicio/Micrositios/Seleccion-Objetiva-Asignacion-de-Espectro/](https://www.mintic.gov.co/portal/inicio/Micrositios/Seleccion-Objetiva-Asignacion-de-Espectro/)

En caso de ser solicitado dicho permiso, también deberá dar cumplimiento a lo dispuesto en el Cuadro Nacional de Atribución de Bandas de Frecuencia (CNABF), el cual puede ser consultado tanto en versión de documento digital como en versión de aplicativo web a través del siguiente enlace:
[https://portalespectro.ane.gov.co/Style%20Library/ane_master/cnabf-tecnico.aspx](https://portalespectro.ane.gov.co/Style%20Library/ane_master/cnabf-tecnico.aspx)

En los anteriores términos y de acuerdo con nuestras competencias damos por atendida su solicitud y quedamos atentos a cualquier aclaración adicional que requiera.

SIEMPRE incluye al final de tu respuesta el JSON exacto (sin bloques de código markdown):
{"TRATO": "...", "NOMBRE": "...", "CORREO": "...", "CARGO": "...", "EMPRESA": "...", "CIUDAD": "...", "ASUNTO": "...", "SALUDO_INICIAL": "...", "CUERPO": "...", "FIRMANTE_NOMBRE": "...", "FIRMANTE_CARGO": "...", "FIRMANTE_AREA": "..."}
"""

# ─────────────────────────────────────────────
#  FUNCIÓN DE LLAMADA A GEMINI CON SEGURO ANTI-FALLOS
# ─────────────────────────────────────────────
def get_ai_response(user_input: str) -> str:
    chat_history = ""
    for msg in st.session_state.pqrs_messages:
        role = "Usuario" if msg["role"] == "user" else "Asistente"
        chat_history += f"{role}: {msg['content']}\n\n"

    full_prompt = f"{SYSTEM_PROMPT}\n\nHistorial de conversación:\n{chat_history}Usuario: {user_input}"
    contenidos = documentos_ane + [full_prompt]

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contenidos,
    )
    
    if response.text is None:
        raise ValueError("La IA devolvió un resultado vacío.")
        
    return response.text

# ─────────────────────────────────────────────
#  CONVERSOR DE MARKDOWN A WORD 
# ─────────────────────────────────────────────
def procesar_cuerpo_a_word(tpl_doc, texto_markdown):
    subdoc = tpl_doc.new_subdoc()
    texto_markdown = texto_markdown.replace("**", "")
    lineas = texto_markdown.split('\n')
    en_tabla = False
    tabla_datos = []
    parrafo_actual = []

    def flush_parrafo():
        if parrafo_actual:
            texto_completo = "\n".join(parrafo_actual).strip()
            if texto_completo:
                p = subdoc.add_paragraph()
                partes = re.split(r'(\*[^*]+\*)', texto_completo)
                for parte in partes:
                    if parte.startswith('*') and parte.endswith('*'):
                        p.add_run(parte[1:-1]).italic = True
                    else:
                        p.add_run(parte)
            parrafo_actual.clear()

    def flush_tabla():
        if tabla_datos:
            num_filas = len(tabla_datos)
            num_cols = max(len(fila) for fila in tabla_datos)
            table = subdoc.add_table(rows=num_filas, cols=num_cols)
            
            estilos_seguros = ['TableGrid', 'Table Grid', 'Cuadrícula de tabla', 'Normal Table']
            for estilo in estilos_seguros:
                try:
                    table.style = estilo
                    break
                except Exception:
                    pass 
            
            for i, fila in enumerate(tabla_datos):
                row_cells = table.rows[i].cells
                for j, celda_texto in enumerate(fila):
                    if j < len(row_cells):
                        row_cells[j].text = celda_texto.strip()
            tabla_datos.clear()

    for linea in lineas:
        linea_limpia = linea.strip()
        if linea_limpia.startswith('|') and linea_limpia.endswith('|'):
            if not en_tabla:
                flush_parrafo()
                en_tabla = True
            if '---' in linea_limpia: 
                continue
            celdas = [c.strip() for c in linea_limpia.strip('|').split('|')]
            tabla_datos.append(celdas)
        else:
            if en_tabla:
                flush_tabla()
                en_tabla = False
            parrafo_actual.append(linea)
            
    flush_parrafo()
    if en_tabla:
        flush_tabla()
        
    return subdoc

# ─────────────────────────────────────────────
#  INTERFAZ PRINCIPAL - CHAT
# ─────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("💬 Chat con el Asistente")

    for message in st.session_state.pqrs_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ej: Generar respuesta para Ana Martínez sobre uso libre en 5150 MHz..."):
        st.session_state.pqrs_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Redactando respuesta y consultando normatividad..."):
                full_res = None
                try:
                    full_res = get_ai_response(prompt)
                except Exception as e:
                    st.error(f"❌ Error al conectar con Gemini: {e}")

            if full_res:
                # 🛡️ NUEVO RADAR DE JSON (Expresión Regular)
                json_match = re.search(r'\{[\s\S]*\}', full_res)
                
                text_part = full_res
                if json_match:
                    json_raw = json_match.group(0)
                    
                    # Limpiamos el texto para que no muestre el código en el chat
                    text_part = full_res[:json_match.start()].replace("JSON_DATA:", "").replace("```json", "").replace("```", "").strip()
                    
                    # Si el bot SOLO mandó el JSON, ponemos un mensaje de éxito genérico
                    if not text_part:
                        text_part = "¡Listo! He procesado la información. Revisa los datos en el panel izquierdo."
                    
                    st.markdown(text_part)
                    
                    try:
                        new_data = json.loads(json_raw)
                        for k, v in new_data.items():
                            if v and k in st.session_state.pqrs_doc_data:
                                st.session_state.pqrs_doc_data[k] = str(v)
                        st.success("✅ Datos extraídos y actualizados correctamente.")
                    except json.JSONDecodeError:
                        st.warning("⚠️ No se pudo procesar el formato de los datos extraídos.")
                else:
                    st.markdown(full_res)

                # Guardamos solo la parte de texto (limpia) en el historial del chat
                st.session_state.pqrs_messages.append({"role": "assistant", "content": text_part})

# ─────────────────────────────────────────────
#  SIDEBAR - DATOS Y DESCARGA
# ─────────────────────────────────────────────
with col2:
    st.header("📋 Datos del Documento")

    st.subheader("Destinatario")
    trato   = st.text_input("Trato (Señor/Señora)", value=st.session_state.pqrs_doc_data["TRATO"])
    nombre  = st.text_input("Nombre",          value=st.session_state.pqrs_doc_data["NOMBRE"])
    correo  = st.text_input("Correo electrónico", value=st.session_state.pqrs_doc_data["CORREO"])
    cargo   = st.text_input("Cargo",           value=st.session_state.pqrs_doc_data["CARGO"])
    empresa = st.text_input("Empresa/Entidad", value=st.session_state.pqrs_doc_data["EMPRESA"])
    ciudad  = st.text_input("Ciudad",          value=st.session_state.pqrs_doc_data["CIUDAD"])
    
    st.subheader("Contenido")
    asunto  = st.text_area("Asunto",           value=st.session_state.pqrs_doc_data["ASUNTO"], height=68)
    saludo  = st.text_input("Saludo Inicial",  value=st.session_state.pqrs_doc_data["SALUDO_INICIAL"])
    cuerpo  = st.text_area("Cuerpo",           value=st.session_state.pqrs_doc_data["CUERPO"], height=300)

    st.subheader("Firmante ANE")
    firmante_nombre = st.text_input("Nombre firmante", value=st.session_state.pqrs_doc_data["FIRMANTE_NOMBRE"])
    firmante_cargo  = st.text_input("Cargo firmante",  value=st.session_state.pqrs_doc_data["FIRMANTE_CARGO"])
    firmante_area   = st.text_input("Área/Dirección",  value=st.session_state.pqrs_doc_data["FIRMANTE_AREA"])

    st.divider()

    if st.button("📄 Generar y Descargar Carta", type="primary", use_container_width=True):
        st.session_state.pqrs_doc_data.update({
            "TRATO": trato, "NOMBRE": nombre, "CORREO": correo, 
            "CARGO": cargo, "EMPRESA": empresa, "CIUDAD": ciudad, 
            "ASUNTO": asunto, "SALUDO_INICIAL": saludo, "CUERPO": cuerpo,
            "FIRMANTE_NOMBRE": firmante_nombre, "FIRMANTE_CARGO": firmante_cargo, "FIRMANTE_AREA": firmante_area,
        })

        try:
            doc = DocxTemplate(str(APP_DIR / "templates" / "plantillaPQR.docx"))
            datos_render = st.session_state.pqrs_doc_data.copy()
            datos_render["CUERPO"] = procesar_cuerpo_a_word(doc, st.session_state.pqrs_doc_data["CUERPO"])
            doc.render(datos_render)

            output = BytesIO()
            doc.save(output)
            output.seek(0)

            safe_name = nombre.replace(" ", "_") if nombre else "destinatario"
            st.download_button(
                label="📥 DESCARGAR CARTA (.docx)",
                data=output,
                file_name=f"Respuesta_ANE_{safe_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except FileNotFoundError:
            st.error("❌ No se encontró 'plantillaPQR.docx'.")
        except Exception as e:
            st.error(f"❌ Error al generar el documento: {e}")

    st.divider()

    if st.button("🗑️ Nueva conversación", use_container_width=True):
        st.session_state.pqrs_messages = []
        st.session_state.pqrs_doc_data = {
            "TRATO": "", "NOMBRE": "", "CORREO": "", "CARGO": "", "EMPRESA": "",
            "CIUDAD": "Bogotá D.C.", "ASUNTO": "", "SALUDO_INICIAL": "", "CUERPO": "",
            "FECHA": datetime.datetime.now().strftime("%d de %B de %Y"),
            "FIRMANTE_NOMBRE": "", "FIRMANTE_CARGO": "", "FIRMANTE_AREA": "",
        }
        st.rerun()