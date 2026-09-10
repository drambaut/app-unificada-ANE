import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSupabase } from '../supabaseClient.js'

export default function AdminLogin() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(false)
  const navigate = useNavigate()

  async function manejarLogin(e) {
    e.preventDefault()
    setError(null)
    setCargando(true)
    try {
      const supabase = await getSupabase()
      const { error: errLogin } = await supabase.auth.signInWithPassword({
        email,
        password,
      })
      if (errLogin) throw errLogin
      navigate('/admin/panel')
    } catch (e2) {
      setError(e2.message || 'No fue posible iniciar sesión')
    } finally {
      setCargando(false)
    }
  }

  return (
    <div>
      <header className="encabezado">
        <h1>ANE — Acceso Ingeniero GIE / Administrador</h1>
      </header>
      <div className="contenedor" style={{ maxWidth: 380 }}>
        <form className="tarjeta" onSubmit={manejarLogin}>
          <div className="campo">
            <label>Correo</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="campo">
            <label>Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <div className="mensaje-error">{error}</div>}
          <button type="submit" disabled={cargando}>
            {cargando ? 'Ingresando...' : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  )
}