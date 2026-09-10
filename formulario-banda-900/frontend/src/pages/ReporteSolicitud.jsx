import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { obtenerReporte } from '../api.js'

export default function ReporteSolicitud() {
  const { id } = useParams()
  const [reporte, setReporte] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    obtenerReporte(id).then(setReporte).catch((e) => setError(e.message))
  }, [id])

  if (error) {
    return (
      <div>
        <header className="encabezado">
          <h1>ANE — Reporte de solicitud</h1>
        </header>
        <div className="contenedor">
          <div className="mensaje-error">{error}</div>
        </div>
      </div>
    )
  }

  if (!reporte) {
    return (
      <div className="contenedor">
        <p>Cargando reporte...</p>
      </div>
    )
  }

  return (
    <div>
      <header className="encabezado">
        <h1>ANE — Reporte de solicitud</h1>
      </header>
      <div className="contenedor">
        <div className="no-imprimir" style={{ marginBottom: 16 }}>
          <button onClick={() => window.print()}>Imprimir / Guardar como PDF</button>
        </div>

        <div className="tarjeta">
          <h2>Información de contacto</h2>
          <table>
            <tbody>
              <tr>
                <th>Comunidad (Razón social)</th>
                <td>{reporte.razon_social}</td>
              </tr>
              <tr>
                <th>NIT</th>
                <td>{reporte.nit}</td>
              </tr>
              <tr>
                <th>Representante legal</th>
                <td>{reporte.representante_legal}</td>
              </tr>
              <tr>
                <th>Teléfono</th>
                <td>{reporte.telefono}</td>
              </tr>
              <tr>
                <th>Dirección</th>
                <td>{reporte.direccion}</td>
              </tr>
              <tr>
                <th>Correo electrónico</th>
                <td>{reporte.correo_electronico}</td>
              </tr>
              <tr>
                <th>Radicado MinTIC</th>
                <td>{reporte.radicado_mintic || '—'}</td>
              </tr>
              <tr>
                <th>Estado</th>
                <td>{reporte.estado}</td>
              </tr>
              <tr>
                <th>Fecha de envío</th>
                <td>{new Date(reporte.created_at).toLocaleString('es-CO')}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {reporte.estaciones.map((estacion, idx) => (
          <div key={estacion.id} className="tarjeta">
            <h2>Estación {idx + 1}</h2>
            <table style={{ marginBottom: 12 }}>
              <tbody>
                <tr>
                  <th>Coordenadas</th>
                  <td>
                    {estacion.latitud}, {estacion.longitud}
                  </td>
                </tr>
                <tr>
                  <th>Dirección</th>
                  <td>{estacion.direccion_estacion || '—'}</td>
                </tr>
                <tr>
                  <th>Departamento</th>
                  <td>{estacion.departamento || '—'}</td>
                </tr>
                <tr>
                  <th>Municipio</th>
                  <td>{estacion.municipio || '—'}</td>
                </tr>
              </tbody>
            </table>

            {estacion.sectores.map((sector) => (
              <div key={sector.numero_sector} style={{ marginBottom: 12 }}>
                <h3 style={{ fontSize: '0.95rem', color: 'var(--azul-ane)' }}>
                  Sector {sector.numero_sector}
                </h3>
                <table>
                  <thead>
                    <tr>
                      <th>ACIMUT</th>
                      <th>TILT</th>
                      <th>Ganancia</th>
                      <th>Ángulo de apertura</th>
                      <th>Altura al suelo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sector.antenas.map((antena, i) => (
                      <tr key={i}>
                        <td>{antena.acimut}</td>
                        <td>{antena.tilt}</td>
                        <td>{antena.ganancia}</td>
                        <td>{antena.angulo_apertura}</td>
                        <td>{antena.altura_suelo}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}