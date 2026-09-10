import { useState } from 'react'

function gmsADecimal(grados, minutos, segundos, negativo) {
  const g = Number(grados) || 0
  const m = Number(minutos) || 0
  const s = Number(segundos) || 0
  const decimal = g + m / 60 + s / 3600
  return negativo ? -decimal : decimal
}

const GMS_VACIO = {
  latGrados: '',
  latMinutos: '',
  latSegundos: '',
  latHemisferio: 'N',
  lonGrados: '',
  lonMinutos: '',
  lonSegundos: '',
  lonHemisferio: 'E',
}

/**
 * Toggle Decimal / GMS para latitud y longitud. En modo Decimal se editan
 * directamente los dos numeros; en modo GMS se editan grados/minutos/segundos
 * + hemisferio y aqui mismo se convierten a decimal, que es lo unico que
 * guarda el backend (columna numeric en Supabase).
 */
export default function CoordenadasInput({ latitud, longitud, formatoCoordenadas, onChange }) {
  const [gms, setGms] = useState(GMS_VACIO)

  function actualizarGms(campo, valor) {
    const nuevo = { ...gms, [campo]: valor }
    setGms(nuevo)
    onChange({
      latitud: gmsADecimal(nuevo.latGrados, nuevo.latMinutos, nuevo.latSegundos, nuevo.latHemisferio === 'S'),
      longitud: gmsADecimal(nuevo.lonGrados, nuevo.lonMinutos, nuevo.lonSegundos, nuevo.lonHemisferio === 'O'),
    })
  }

  return (
    <div>
      <div className="pestanas">
        <button
          type="button"
          className={formatoCoordenadas === 'decimal' ? 'activa' : ''}
          onClick={() => onChange({ formato_coordenadas: 'decimal' })}
        >
          Decimal
        </button>
        <button
          type="button"
          className={formatoCoordenadas === 'gms' ? 'activa' : ''}
          onClick={() => onChange({ formato_coordenadas: 'gms' })}
        >
          GMS (grados, minutos, segundos)
        </button>
      </div>

      {formatoCoordenadas === 'gms' ? (
        <div>
          <label style={{ fontWeight: 600, fontSize: '0.9rem' }}>Latitud</label>
          <div className="fila">
            <div className="campo" style={{ maxWidth: 70 }}>
              <label>N/S</label>
              <select value={gms.latHemisferio} onChange={(e) => actualizarGms('latHemisferio', e.target.value)}>
                <option value="N">N</option>
                <option value="S">S</option>
              </select>
            </div>
            <div className="campo" style={{ maxWidth: 90 }}>
              <label>Grados °</label>
              <input type="number" value={gms.latGrados} onChange={(e) => actualizarGms('latGrados', e.target.value)} />
            </div>
            <div className="campo" style={{ maxWidth: 90 }}>
              <label>Minutos '</label>
              <input type="number" value={gms.latMinutos} onChange={(e) => actualizarGms('latMinutos', e.target.value)} />
            </div>
            <div className="campo" style={{ maxWidth: 90 }}>
              <label>Segundos "</label>
              <input type="number" value={gms.latSegundos} onChange={(e) => actualizarGms('latSegundos', e.target.value)} />
            </div>
          </div>

          <label style={{ fontWeight: 600, fontSize: '0.9rem' }}>Longitud</label>
          <div className="fila">
            <div className="campo" style={{ maxWidth: 70 }}>
              <label>E/O</label>
              <select value={gms.lonHemisferio} onChange={(e) => actualizarGms('lonHemisferio', e.target.value)}>
                <option value="E">E</option>
                <option value="O">O</option>
              </select>
            </div>
            <div className="campo" style={{ maxWidth: 90 }}>
              <label>Grados °</label>
              <input type="number" value={gms.lonGrados} onChange={(e) => actualizarGms('lonGrados', e.target.value)} />
            </div>
            <div className="campo" style={{ maxWidth: 90 }}>
              <label>Minutos '</label>
              <input type="number" value={gms.lonMinutos} onChange={(e) => actualizarGms('lonMinutos', e.target.value)} />
            </div>
            <div className="campo" style={{ maxWidth: 90 }}>
              <label>Segundos "</label>
              <input type="number" value={gms.lonSegundos} onChange={(e) => actualizarGms('lonSegundos', e.target.value)} />
            </div>
          </div>

          <div style={{ fontSize: '0.8rem', color: '#555' }}>
            Equivalente decimal: {Number(latitud || 0).toFixed(6)}, {Number(longitud || 0).toFixed(6)}
          </div>
        </div>
      ) : (
        <div className="fila">
          <div className="campo">
            <label>Latitud</label>
            <input
              type="number"
              step="any"
              value={latitud}
              onChange={(e) => onChange({ latitud: e.target.value })}
              required
            />
          </div>
          <div className="campo">
            <label>Longitud</label>
            <input
              type="number"
              step="any"
              value={longitud}
              onChange={(e) => onChange({ longitud: e.target.value })}
              required
            />
          </div>
        </div>
      )}
    </div>
  )
}