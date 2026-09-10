import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import CargaMasiva from '../components/CargaMasiva.jsx'
import EstacionForm from '../components/EstacionForm.jsx'
import { crearEstacion, listarEstaciones, obtenerCamposAntena } from '../api.js'
import { getSupabase } from '../supabaseClient.js'
import { estacionVacia, prepararEstacionParaEnvio } from '../utils.js'

export default function AdminPanel() {
  const navigate = useNavigate()
  const [sesionLista, setSesionLista] = useState(false)
  const [pestana, setPestana] = useState('manual')
  const [camposAntena, setCamposAntena] = useState(null)
  const [estacion, setEstacion] = useState(estacionVacia())
  const [estaciones, setEstaciones] = useState([])
  const [mensaje, setMensaje] = useState(null)
  const [error, setError] = useState(null)
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    ;(async () => {
      const supabase = await getSupabase()
      const {
        data: { session },
      } = await supabase.auth.getSession()
      if (!session) {
        navigate('/admin')
        return
      }
      setSesionLista(true)
    })()
  }, [navigate])

  useEffect(() => {
    if (!sesionLista) return
    obtenerCamposAntena().then(setCamposAntena).catch((e) => setError(e.message))
    cargarEstaciones()
  }, [sesionLista])

  async function cargarEstaciones() {
    try {
      const res = await listarEstaciones()
      setEstaciones(res)
    } catch (e) {
      setError(e.message)
    }
  }

  async function cerrarSesion() {
    const supabase = await getSupabase()
    await supabase.auth.signOut()
    navigate('/admin')
  }

  async function guardarEstacion(e) {
    e.preventDefault()
    setMensaje(null)
    setError(null)
    setGuardando(true)
    try {
      const payload = prepararEstacionParaEnvio(estacion)
      payload.tipo_estacion = estacion.tipo_estacion || null
      const res = await crearEstacion(payload)
      setMensaje(`Estación #${res.id} guardada correctamente.`)
      setEstacion(estacionVacia())
      cargarEstaciones()
    } catch (e2) {
      setError(e2.message)
    } finally {
      setGuardando(false)
    }
  }

  if (!sesionLista) return null

  return (
    <div>
      <header className="encabezado" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Panel Ingeniero GIE</h1>
        <button className="secundario" style={{ background: 'white' }} onClick={cerrarSesion}>
          Cerrar sesión
        </button>
      </header>
      <div className="contenedor">
        <div className="pestanas">
          <button
            className={pestana === 'manual' ? 'activa' : ''}
            onClick={() => setPestana('manual')}
          >
            Nueva estación (manual)
          </button>
          <button
            className={pestana === 'masiva' ? 'activa' : ''}
            onClick={() => setPestana('masiva')}
          >
            Carga masiva
          </button>
          <button
            className={pestana === 'listado' ? 'activa' : ''}
            onClick={() => setPestana('listado')}
          >
            Estaciones cargadas
          </button>
        </div>

        {error && <div className="mensaje-error">{error}</div>}
        {mensaje && <div className="mensaje-ok">{mensaje}</div>}

        {pestana === 'manual' && camposAntena && (
          <form onSubmit={guardarEstacion}>
            <div className="tarjeta">
              <EstacionForm
                estacion={estacion}
                camposAntena={camposAntena}
                onChange={setEstacion}
                mostrarTipoEstacion
              />
            </div>
            <button type="submit" disabled={guardando}>
              {guardando ? 'Guardando...' : 'Guardar estación'}
            </button>
          </form>
        )}

        {pestana === 'masiva' && <CargaMasiva onCargaCompleta={cargarEstaciones} />}

        {pestana === 'listado' && (
          <div className="tarjeta">
            <h2>Estaciones de red registradas</h2>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Lat</th>
                  <th>Lon</th>
                  <th>Departamento</th>
                  <th>Municipio</th>
                  <th>Sectores</th>
                  <th>Fuente</th>
                </tr>
              </thead>
              <tbody>
                {estaciones.map((e) => (
                  <tr key={e.id}>
                    <td>{e.id}</td>
                    <td>{e.latitud}</td>
                    <td>{e.longitud}</td>
                    <td>{e.departamento}</td>
                    <td>{e.municipio}</td>
                    <td>{e.cantidad_sectores}</td>
                    <td>{e.fuente_carga}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}