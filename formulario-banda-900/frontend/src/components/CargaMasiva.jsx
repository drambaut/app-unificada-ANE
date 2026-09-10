import { useState } from 'react'
import { subirCargaMasiva } from '../api.js'

export default function CargaMasiva({ onCargaCompleta }) {
  const [archivo, setArchivo] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)

  async function enviar() {
    if (!archivo) return
    setCargando(true)
    setError(null)
    setResultado(null)
    try {
      const res = await subirCargaMasiva(archivo)
      setResultado(res)
      if (onCargaCompleta) onCargaCompleta()
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="tarjeta">
      <h2>Carga masiva de estaciones (CSV o XLSX)</h2>
      <p style={{ fontSize: '0.85rem', color: '#555' }}>
        Columnas requeridas: latitud, longitud, numero_sector, acimut, tilt,
        ganancia, angulo_apertura, altura_suelo. Opcionales:
        direccion_estacion, departamento, municipio, ganancia_unidad,
        potencia_transmision, tipo_estacion.
      </p>
      <input
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={(e) => setArchivo(e.target.files[0])}
      />
      <div style={{ marginTop: 10 }}>
        <button type="button" onClick={enviar} disabled={!archivo || cargando}>
          {cargando ? 'Procesando...' : 'Subir archivo'}
        </button>
      </div>

      {error && <div className="mensaje-error" style={{ marginTop: 12 }}>{error}</div>}

      {resultado && (
        <div style={{ marginTop: 16 }}>
          <div
            className={resultado.filas_error === 0 ? 'mensaje-ok' : 'mensaje-error'}
          >
            {resultado.filas_ok} fila(s) cargadas correctamente, {resultado.filas_error} con
            errores. Estado: {resultado.estado}.
          </div>
          {resultado.errores?.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Fila</th>
                  <th>Errores</th>
                </tr>
              </thead>
              <tbody>
                {resultado.errores.map((e) => (
                  <tr key={e.fila}>
                    <td>{e.fila}</td>
                    <td>{e.errores.join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
