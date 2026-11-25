import { page } from './api'

export const statuses = ['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'REJECTED'] as const
export type Status = typeof statuses[number]
export type Category = { id: string; name: string; code: string }
export type ReportSummary = {
  id: string; public_reference: string; title: string; status: Status; category_id: string | null; created_at: string
}

export async function getCategories() {
  const endpoint = '/public/categories?page_size=100'
  const first = await page<Category>(endpoint)
  const remaining = Math.ceil(first.meta.total / first.meta.page_size) - 1
  const results = await Promise.all(Array.from({ length: Math.max(0, remaining) }, (_, index) =>
    page<Category>(`${endpoint}&page=${index + 2}`),
  ))
  return first.data.concat(results.flatMap((result) => result.data))
}
