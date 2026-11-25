import { useEffect, useRef } from 'react'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'

type Point = { latitude: number; longitude: number; title: string }

export default function TileMap({ points, tiles }: { points: Point[]; tiles: string }) {
  const container = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!container.current || !points.length) return
    const map = L.map(container.current, { scrollWheelZoom: false })
    L.tileLayer(tiles, { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(map)
    const markers = L.featureGroup(points.map((point) => {
      const label = document.createElement('span')
      label.textContent = point.title
      return L.circleMarker([point.latitude, point.longitude], {
        radius: 7, color: '#362218', fillColor: '#ff963e', fillOpacity: 0.92, weight: 2,
      }).bindTooltip(label)
    })).addTo(map)
    map.fitBounds(markers.getBounds(), { maxZoom: 14, padding: [32, 32] })
    return () => { map.remove() }
  }, [points, tiles])
  return <div className="workspace-map" ref={container} aria-label="Map of approved civic reports" />
}
