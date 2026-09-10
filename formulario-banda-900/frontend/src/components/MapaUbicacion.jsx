import { MapContainer, Marker, TileLayer, useMap } from 'react-leaflet'
import { useEffect } from 'react'
import L from 'leaflet'

// Ajuste necesario porque Vite no resuelve los iconos default de Leaflet.
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

function Recentrar({ lat, lon }) {
  const map = useMap()
  useEffect(() => {
    if (!Number.isNaN(lat) && !Number.isNaN(lon)) {
      map.setView([lat, lon], map.getZoom())
    }
  }, [lat, lon, map])
  return null
}

export default function MapaUbicacion({ latitud, longitud }) {
  const lat = Number(latitud)
  const lon = Number(longitud)
  const posicionValida = !Number.isNaN(lat) && !Number.isNaN(lon) && (lat !== 0 || lon !== 0)
  const centro = posicionValida ? [lat, lon] : [4.6097, -74.0817] // Bogota por defecto

  return (
    <div className="mapa">
      <MapContainer center={centro} zoom={posicionValida ? 13 : 5} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {posicionValida && <Marker position={centro} />}
        <Recentrar lat={lat} lon={lon} />
      </MapContainer>
    </div>
  )
}