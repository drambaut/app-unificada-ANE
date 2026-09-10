import { useEffect, useState } from 'react'
import CampoTelefono from '../components/CampoTelefono.jsx'
import EstacionForm from '../components/EstacionForm.jsx'
import { crearSolicitud, obtenerCamposAntena } from '../api.js'
import { estacionVacia, prepararEstacionParaEnvio } from '../utils.js'

const SOLICITUD_VACIA = {
  razon_social: '',
  nit: '',
  representante_legal: '',
  telefono: '+57',
  direccion: '',
  correo_electronico: '',
  radicado_mintic: '',
}

const REGEX_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function FormularioComunidad() {
  const [camposAntena, setCamposAntena] = useState(null)
  const [solicitud, setSolicitud] = useState(SOLICITUD_VACIA)
  const [estaciones, setEstaciones] = useState([estacionVacia()])
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const [confirmacion, setConfirmacion] = useState(null)

  useEffect(() => {
    obtenerCamposAntena().then(setCamposAntena).catch((e) => setError(e.message))
  }, [])

  function setCampoSolicitud(campo, valor) {
    setSolicitud((s) => ({ ...s, [campo]: valor }))
  }

  function manejarCambioNit(e) {
    // Solo digitos, sin signo ni flechas de incremento (por eso es type="text").
    const soloDigitos = e.target.value.replace(/\D/g, '').slice(0, 15)
    setCampoSolicitud('nit', soloDigitos)
  }

  function manejarCambioCorreo(e) {
    setCampoSolicitud('correo_electronico', e.target.value)
  }

  const correoValido =
    solicitud.correo_electronico === '' || REGEX_CORREO.test(solicitud.correo_electronico)

  function actualizarEstacion(idx, nuevaEstacion) {
    setEstaciones((prev) => prev.map((e, i) => (i === idx ? nuevaEstacion : e)))
  }

  function agregarEstacion() {
    setEstaciones((prev) => [...prev, estacionVacia()])
  }

  function quitarEstacion(idx) {
    setEstaciones((prev) => prev.filter((_, i) => i !== idx))
  }

  async function manejarEnvio(e) {
    e.preventDefault()
    setError(null)

    if (!REGEX_CORREO.test(solicitud.correo_electronico)) {
      setError('El correo electrónico no tiene un formato válido (ej: nombre@dominio.com)')
      return
    }
    if (solicitud.telefono.replace('+57', '').length < 7) {
      setError('El teléfono debe tener entre 7 y 10 dígitos')
      return
    }

    setEnviando(true)
    try {
      const payload = {
        ...solicitud,
        radicado_mintic: solicitud.radicado_mintic || null,
        estaciones: estaciones.map(prepararEstacionParaEnvio),
      }
      const res = await crearSolicitud(payload)
      setConfirmacion(res)
    } catch (e2) {
      setError(e2.message)
    } finally {
      setEnviando(false)
    }
  }

  if (confirmacion) {
    return (
      <div>
        <header className="encabezado">
          <h1>ANE — Solicitud banda 900 MHz</h1>
        </header>
        <div className="contenedor">
          <div className="mensaje-ok">
            Solicitud #{confirmacion.id} enviada correctamente. Estado: {confirmacion.estado}.
          </div>
          <button onClick={() => window.open(`/solicitud/${confirmacion.id}/reporte`, '_blank')}>
            Ver reporte de la solicitud
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <header className="encabezado">
        <h1>ANE — Formulario de solicitud banda 900 MHz</h1>
      </header>
      <div className="contenedor">
        {!camposAntena && !error && <p>Cargando formulario...</p>}
        {error && <div className="mensaje-error">{error}</div>}

        {camposAntena && (
          <form onSubmit={manejarEnvio}>
            <div className="tarjeta">
              <h2>Información de contacto</h2>
              <div className="fila">
                <div className="campo">
                  <label>Comunidad (Razón social)</label>
                  <input
                    value={solicitud.razon_social}
                    onChange={(e) => setCampoSolicitud('razon_social', e.target.value)}
                    required
                  />
                </div>
                <div className="campo">
                  <label>NIT</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    value={solicitud.nit}
                    onChange={manejarCambioNit}
                    placeholder="Solo números"
                    required
                  />
                </div>
              </div>
              <div className="fila">
                <div className="campo">
                  <label>Representante legal</label>
                  <input
                    value={solicitud.representante_legal}
                    onChange={(e) => setCampoSolicitud('representante_legal', e.target.value)}
                    required
                  />
                </div>
                <CampoTelefono
                  valor={solicitud.telefono}
                  onChange={(v) => setCampoSolicitud('telefono', v)}
                />
              </div>
              <div className="campo">
                <label>Dirección</label>
                <input
                  maxLength={43}
                  value={solicitud.direccion}
                  onChange={(e) => setCampoSolicitud('direccion', e.target.value)}
                  required
                />
              </div>
              <div className="fila">
                <div className="campo">
                  <label>Correo electrónico</label>
                  <input
                    type="email"
                    value={solicitud.correo_electronico}
                    onChange={manejarCambioCorreo}
                    required
                  />
                  {!correoValido && (
                    <div className="error-texto">
                      Formato inválido, debe ser como nombre@dominio.com
                    </div>
                  )}
                </div>
                <div className="campo">
                  <label>Radicado de solicitud MinTIC</label>
                  <input
                    value={solicitud.radicado_mintic}
                    onChange={(e) => setCampoSolicitud('radicado_mintic', e.target.value)}
                  />
                </div>
              </div>
            </div>

            <h2>Estaciones</h2>
            {estaciones.map((estacion, idx) => (
              <div key={idx} className="tarjeta">
                <h2>Estación {idx + 1}</h2>
                <EstacionForm
                  estacion={estacion}
                  camposAntena={camposAntena}
                  onChange={(nueva) => actualizarEstacion(idx, nueva)}
                />
                {estaciones.length > 1 && (
                  <button type="button" className="secundario" onClick={() => quitarEstacion(idx)}>
                    Quitar esta estación
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="secundario" onClick={agregarEstacion}>
              + Agregar otra estación
            </button>

            <div style={{ marginTop: 20 }}>
              <button type="submit" disabled={enviando}>
                {enviando ? 'Enviando...' : 'Enviar solicitud'}
              </button>
            </div>
          </form>
        )}

        <p className="pie-politica">
          Al enviar este formulario aceptas nuestra política de tratamiento de
          datos personales. [Enlace pendiente de definir por la entidad]
        </p>
      </div>
    </div>
  )
}