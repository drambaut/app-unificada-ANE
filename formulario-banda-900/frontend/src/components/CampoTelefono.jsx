/**
 * Campo de telefono con el prefijo +57 fijo (no editable) y un input que
 * solo acepta digitos, maximo 10. El valor que se le entrega al padre via
 * onChange ya viene con el prefijo pegado (ej: "+573001234567"), listo para
 * enviar al backend.
 */
export default function CampoTelefono({ valor, onChange }) {
  const soloDigitos = (valor || '').replace(/^\+57/, '')

  function manejarCambio(e) {
    const digitos = e.target.value.replace(/\D/g, '').slice(0, 10)
    onChange(`+57${digitos}`)
  }

  return (
    <div className="campo">
      <label>Teléfono</label>
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          value="+57"
          disabled
          style={{ width: 60, textAlign: 'center', background: '#eee', flex: 'none' }}
        />
        <input
          type="text"
          inputMode="numeric"
          placeholder="3001234567"
          value={soloDigitos}
          onChange={manejarCambio}
          maxLength={10}
          required
        />
      </div>
      {soloDigitos.length > 0 && soloDigitos.length < 7 && (
        <div className="error-texto">Debe tener al menos 7 dígitos</div>
      )}
    </div>
  )
}