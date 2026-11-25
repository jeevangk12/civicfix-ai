import { useCallback, useState } from 'react'
import { Link, useOutletContext } from 'react-router'
import { data, page } from './api'
import type { InboxContext, Notification } from './notificationModel'
import { Badge, ErrorNotice, Heading, Pagination, Timestamp, message, useResource } from './ui'

export function Inbox({ role }: { role: 'CITIZEN' | 'STAFF' }) {
  const { unread, refreshUnread } = useOutletContext<InboxContext>()
  const [number, setPage] = useState(1)
  const load = useCallback(() => page<Notification>(`/notifications?page=${number}`), [number])
  const inbox = useResource(load)
  const [busy, setBusy] = useState<string>()
  const [error, setError] = useState<string>()
  const [notice, setNotice] = useState<string>()
  const reportBase = role === 'STAFF' ? '/authority/complaints' : '/citizen/complaints'

  async function markRead(id?: string) {
    setBusy(id ?? 'all')
    setError(undefined)
    setNotice(undefined)
    try {
      if (id) {
        await data(`/notifications/${id}/read`, { method: 'PATCH' })
        setNotice('Notification marked as read.')
      } else {
        await data('/notifications/read-all', { method: 'PATCH' })
        setNotice('All notifications marked as read.')
      }
      inbox.retry()
      refreshUnread()
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(undefined)
    }
  }

  return <>
    <Heading title="Notifications">
      <div className="workspace-actions">
        {unread !== undefined && <p>{unread} unread</p>}
        <button className="button button-secondary" disabled={!!busy || unread === 0} onClick={() => void markRead()}>
          Mark all as read
        </button>
      </div>
    </Heading>
    {error && <ErrorNotice error={error} />}
    {notice && <p role="status" className="workspace-success">{notice}</p>}
    {inbox.loading && <p role="status">Loading notifications…</p>}
    {inbox.error && <ErrorNotice error={inbox.error} retry={inbox.retry} />}
    {inbox.value && (inbox.value.meta.total ? <>
      <ul className="workspace-inbox">
        {inbox.value.data.map((item) => <li className="workspace-panel" data-notification-id={item.id} key={item.id}>
          <div className="workspace-inbox-copy">
            <div className="workspace-actions">
              <h2>{item.title}</h2>
              {item.read_at === null && <Badge value="UNREAD" />}
            </div>
            <p>{item.body}</p>
            <Timestamp value={item.created_at} />
          </div>
          <div className="workspace-actions">
            {item.resource_type === 'complaint' && item.resource_id && <Link className="button button-secondary"
              to={`${reportBase}/${item.resource_id}`} aria-label={`Open report · ${item.title}`}>Open report</Link>}
            {item.read_at === null && <button className="button button-secondary" disabled={!!busy}
              aria-label={`Mark as read · ${item.title}`} onClick={() => void markRead(item.id)}>Mark as read</button>}
          </div>
        </li>)}
      </ul>
      <Pagination meta={inbox.value.meta} change={setPage} />
    </> : <div className="workspace-empty">
      <h2>No notifications yet</h2>
      <p>{role === 'CITIZEN' ? 'Updates to your reports will appear here.' : 'New assignments will appear here.'}</p>
    </div>)}
  </>
}
