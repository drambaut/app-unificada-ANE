import { getSupabase } from './supabaseClient'

async function authHeader() {
  const supabase = await getSupabase()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  return session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {}
}

async function manejarRespuesta(res) {
  if (!res.ok) {
    let detalle = 'Ocurrio un error'
    try {
      const data = await res.json()
      detalle = data.detail ? JSON.stringify(data.detail) : detalle
    } catch {
      // respuesta sin JSON
    }
    throw new Error(detalle)
  }
  return res.json()
}

export async function obtenerCamposAntena() {
  const res = await fetch('/api/config/campos-antena')
  return manejarRespuesta(res)
}

export async function crearSolicitud(payload) {
  const res = await fetch('/api/solicitudes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return manejarRespuesta(res)
}

export async function obtenerReporte(id) {
  const res = await fetch(`/api/solicitudes/${id}/reporte`)
  return manejarRespuesta(res)
}

export async function listarEstaciones() {
  const res = await fetch('/api/estaciones', { headers: await authHeader() })
  return manejarRespuesta(res)
}

export async function crearEstacion(payload) {
  const res = await fetch('/api/estaciones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(payload),
  })
  return manejarRespuesta(res)
}

export async function subirCargaMasiva(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/estaciones/carga-masiva', {
    method: 'POST',
    headers: await authHeader(),
    body: formData,
  })
  return manejarRespuesta(res)
}