import CoordenadasInput from './CoordenadasInput.jsx'
import MapaUbicacion from './MapaUbicacion.jsx'
import SectoresEditor from './SectoresEditor.jsx'
import UbicacionSelect from './UbicacionSelect.jsx'

export default function EstacionForm({
  estacion,
  camposAntena,
  onChange,
  mostrarTipoEstacion = false,
}) {
  function set(campo, valor) {
    onChange({ ...estacion, [campo]: valor })
  }

  function actualizarCoordenadas(patch) {
    onChange({ ...estacion, ...patch })
  }

  return (
    <div>
      <CoordenadasInput
        latitud={estacion.latitud}
        longitud={estacion.longitud}
        formatoCoordenadas={estacion.formato_coordenadas}
        onChange={actualizarCoordenadas}
      />

      <MapaUbicacion latitud={estacion.latitud} longitud={estacion.longitud} />

      <div className="fila" style={{ marginTop: 12 }}>
        <div className="campo">
          <label>Dirección de la estación</label>
          <input
            value={estacion.direccion_estacion}
            onChange={(e) => set('direccion_estacion', e.target.value)}
          />
        </div>
        <UbicacionSelect
          departamento={estacion.departamento}
          municipio={estacion.municipio}
          onChange={(patch) => onChange({ ...estacion, ...patch })}
        />
      </div>

      {mostrarTipoEstacion && (
        <div className="campo">
          <label>Tipo de estación</label>
          <select
            value={estacion.tipo_estacion || ''}
            onChange={(e) => set('tipo_estacion', e.target.value)}
          >
            <option value="">Seleccione...</option>
            <option value="nueva">Nueva</option>
            <option value="repetidora">Repetidora</option>
          </select>
        </div>
      )}

      <h2 style={{ marginTop: 16 }}>Sectores y antenas</h2>
      <SectoresEditor
        camposAntena={camposAntena}
        sectores={estacion.sectores}
        onChange={(sectores) => onChange({ ...estacion, sectores })}
      />
    </div>
  )
}