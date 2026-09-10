import { createClient } from '@supabase/supabase-js'

let clientPromise = null

/**
 * El frontend no trae la URL/anon key de Supabase "horneadas" en el build.
 * Las pide en tiempo real al backend (/api/config/public) para no depender
 * de variables de entorno de build en Vite/Render. La anon key es publica
 * por diseno de Supabase (las tablas quedan protegidas con RLS).
 */
export function getSupabase() {
  if (!clientPromise) {
    clientPromise = fetch('/api/config/public')
      .then((r) => r.json())
      .then(({ supabase_url, supabase_anon_key }) => {
        if (!supabase_url || !supabase_anon_key) {
          throw new Error(
            'El backend no tiene configurado SUPABASE_URL / SUPABASE_ANON_KEY'
          )
        }
        return createClient(supabase_url, supabase_anon_key)
      })
  }
  return clientPromise
}
