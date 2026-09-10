import CampoAntena from './CampoAntena.jsx'
import { antenaVacia, sectorVacio } from '../utils.js'

const CAMPOS_ORDEN = ['acimut', 'tilt', 'ganancia', 'angulo_apertura', 'altura_suelo']

export default function SectoresEditor({ camposAntena, sectores, onChange }) {
  function actualizarAntena(idxSector, idxAntena, campo, valor) {
    const nuevo = sectores.map((s, i) => {
      if (i !== idxSector) return s
      const antenas = s.antenas.map((a, j) =>
        j === idxAntena ? { ...a, [campo]: valor } : a
      )
      return { ...s, antenas }
    })
    onChange(nuevo)
  }

  function agregarSector() {
    onChange([...sectores, sectorVacio(sectores.length + 1)])
  }

  function quitarSector(idx) {
    onChange(
      sectores
        .filter((_, i) => i !== idx)
        .map((s, i) => ({ ...s, numero_sector: i + 1 }))
    )
  }

  function agregarAntena(idxSector) {
    onChange(
      sectores.map((s, i) =>
        i === idxSector ? { ...s, antenas: [...s.antenas, antenaVacia()] } : s
      )
    )
  }

  function quitarAntena(idxSector, idxAntena) {
    onChange(
      sectores.map((s, i) =>
        i === idxSector
          ? { ...s, antenas: s.antenas.filter((_, j) => j !== idxAntena) }
          : s
      )
    )
  }

  return (
    <div>
      {sectores.map((sector, idxSector) => (
        <div key={idxSector} className="tarjeta">
          <h2>Sector {sector.numero_sector}</h2>
          {sector.antenas.map((antena, idxAntena) => (
            <div
              key={idxAntena}
              style={{
                marginBottom: 12,
                paddingBottom: 12,
                borderBottom: '1px dashed #ccc',
              }}
            >
              <div className="fila">
                {CAMPOS_ORDEN.map((campo) => (
                  <CampoAntena
                    key={campo}
                    nombreCampo={campo}
                    config={camposAntena[campo]}
                    valor={antena[campo]}
                    onChange={(c, v) => actualizarAntena(idxSector, idxAntena, c, v)}
                  />
                ))}
              </div>
              {sector.antenas.length > 1 && (
                <button
                  type="button"
                  className="secundario"
                  onClick={() => quitarAntena(idxSector, idxAntena)}
                >
                  Quitar antena
                </button>
              )}
            </div>
          ))}
          <button type="button" className="secundario" onClick={() => agregarAntena(idxSector)}>
            + Agregar antena a este sector
          </button>
          {sectores.length > 1 && (
            <div style={{ marginTop: 8 }}>
              <button
                type="button"
                className="secundario"
                onClick={() => quitarSector(idxSector)}
              >
                Quitar sector
              </button>
            </div>
          )}
        </div>
      ))}
      <button type="button" className="secundario" onClick={agregarSector}>
        + Agregar sector
      </button>
    </div>
  )
}