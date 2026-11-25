import { data } from './api'

export type Notification = {
  id: string; type: string; title: string; body: string; resource_type: string | null;
  resource_id: string | null; read_at: string | null; created_at: string
}

export type InboxContext = { unread: number | undefined; refreshUnread: () => void }

export const getUnread = () => data<{ count: number }>('/notifications/unread-count')
