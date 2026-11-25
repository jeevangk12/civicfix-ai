import { lazy, Suspense, useCallback, useState } from 'react'
import { publicPage } from './api'
import { statuses, type Status } from './reportModel'
import { Badge, ErrorNotice, Heading, Pagination, readable, useResource } from './ui'

const TileMap = lazy(() => import('./TileMap'))
type Marker = {
  public_reference: string; title: string; category: { name: string } | null; status: Status;
  latitude: number; longitude: number; location_precision: 'approximate' | 'approved'; updated_on: string
}

export default function PublicMap() {
  const [number, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const load = useCallback(() => publicPage<Marker>(`/public/complaints/map?page=${number}${status ? `&status=${status}` : ''}`), [number, status])
  const markers = useResource(load)
  const tiles = import.meta.env.VITE_MAP_TILE_URL
  return <>
    <Heading title="Public complaint map"><p>Browse reports approved for public display. Some locations are approximate.</p></Heading>
    <div className="workspace-filters">
      <label>Status<select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}>
        <option value="">All statuses</option>
        {statuses.map((value) => <option value={value} key={value}>{readable(value)}</option>)}
      </select></label>
    </div>
    {markers.loading && <p role="status">Loading public reports…</p>}
    {markers.error && <ErrorNotice error={markers.error} retry={markers.retry} />}
    {markers.value && (markers.value.data.length ? <>
      {tiles && <Suspense fallback={<p role="status">Loading map tiles…</p>}><TileMap points={markers.value.data} tiles={tiles} /></Suspense>}
      <ul className="workspace-inbox">
        {markers.value.data.map((item) => <li className="workspace-panel" key={item.public_reference}>
          <div className="workspace-inbox-copy">
            <h2>{item.title}</h2><p>{item.public_reference} · {item.category?.name ?? 'Uncategorized'}</p>
            <p className="workspace-muted">{readable(item.location_precision)} location · {item.latitude}, {item.longitude}</p>
          </div>
          <div className="workspace-report-meta">
            <Badge value={item.status} /><time dateTime={item.updated_on}>{item.updated_on}</time>
          </div>
        </li>)}
      </ul>
      <Pagination meta={markers.value.meta} change={setPage} />
    </> : <div className="workspace-empty"><h2>No public reports match this view</h2></div>)}
  </>
}
