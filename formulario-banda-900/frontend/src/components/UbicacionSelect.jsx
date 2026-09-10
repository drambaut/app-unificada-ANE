import { DEPARTAMENTOS, DEPARTAMENTOS_MUNICIPIOS } from '../data/colombiaDivipola.js'

/**
 * Departamento y Municipio como selects en cascada (no texto libre), para
 * que "Bogota", "bogota" y "Bogota DC" no queden como 3 valores distintos
 * en la base, y para que un municipio no pueda quedar asociado al
 * departamento equivocado.
 */
export default function UbicacionSelect({ departamento, municipio, onChange }) {
  const municipios = DEPARTAMENTOS_MUNICIPIOS[departamento] || []

  function cambiarDepartamento(nuevoDepartamento) {
    // al cambiar de departamento se limpia el municipio para no dejar
    // combinaciones invalidas (ej. Maicao con departamento Amazonas)
    onChange({ departamento: nuevoDepartamento, municipio: '' })
  }

  return (
    <>
      <div className="campo">
        <label>Departamento</label>
        <select value={departamento || ''} onChange={(e) => cambiarDepartamento(e.target.value)} required>
          <option value="">Seleccione...</option>
          {DEPARTAMENTOS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>
      <div className="campo">
        <label>Municipio</label>
        <select
          value={municipio || ''}
          onChange={(e) => onChange({ municipio: e.target.value })}
          disabled={!departamento}
          required
        >
          <option value="">{departamento ? 'Seleccione...' : 'Primero elige el departamento'}</option>
          {municipios.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
    </>
  )
}