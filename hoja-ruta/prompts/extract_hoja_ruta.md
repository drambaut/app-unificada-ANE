Eres un asistente experto en estructuracion de documentos institucionales.

Recibiras el texto extraido de un PDF llamado "Estrategia de gestion de datos SGP_VF.pdf".
Tu tarea es extraer exactamente las 29 actividades de la hoja de ruta SGP.

Devuelve SOLO un CSV valido, sin markdown y sin explicacion, con estas columnas:

id_actividad,linea_hoja_ruta,actividad,horizonte,observaciones

Reglas:

1. Extrae exactamente 29 actividades, una fila por actividad.
2. Las actividades son el universo maestro del analisis; ninguna puede desaparecer.
3. id_actividad debe ser estable, unico y no nulo. Usa A01, A02, ..., A29 en el orden del documento.
4. No resumas varias actividades en una sola.
5. No dividas una actividad salvo que el documento la presente expresamente como actividad diferente.
6. No inventes responsables, horizontes ni informacion ausente.
7. Si horizonte u observaciones no aparecen, escribe "No especificado".
8. Conserva el sentido del texto original.
9. No uses saltos de linea dentro de una celda.
10. Todas las celdas deben estar entre comillas dobles.
11. Si una celda contiene comillas dobles, escapalas duplicandolas.
12. No devuelvas markdown.
13. No agregues texto antes ni despues del CSV.

Texto del PDF:
{pdf_text}
